#include <PacketSerial.h>
#include <Wire.h>
#include "TM1650.h"

PacketSerial packetSerial;
TM1650 d;

// pin defination
static const int pin_LED[6] = {9,10,11,12,13,14};
static const int pin_joystick_x = 17;
static const int pin_joystick_y = 16;
static const int pin_joystick_btn = 15;
static const int pin_pot1 = 21;
static const int pin_pot2 = 20;
static const int pin_key1 = 22;
static const int pin_key2 = 23;
static const int pin_encoder_1_A = 4;
static const int pin_encoder_1_B = 3;
static const int pin_encoder_2_A = 6;
static const int pin_encoder_2_B = 5;
static const int pin_encoder_3_A = 8;
static const int pin_encoder_3_B = 7;

// state variables
bool joystick_button_pressed = false;
bool key_pressed[6] = {false};
// wait for ack bit to be set; until it's set, keep sending btn pressed msg
// on the controller, finish the cycle when the btn pressed bit is cleared.
// repeat the same between the host computer and the main controller

// joystick
int joystick_offset_x = 338;
int joystick_offset_y = 339;
int joystick_delta_x = 0;
int joystick_delta_y = 0;
int joystick_deadband = 25;

// input related
volatile long encoder_pos = 0; // encoder pos >> 4 is the focus position
int input_sensitivity_xy = 0;
int input_sensitivity_z = 0;
int encoder_step_size = 1;

// communication
static const int JOYSTICK_MSG_LENGTH = 10;// 4 bytes for encoder, 2 bytes for joystick x, 2 bytes for joystick y, 1 byte for buttons, 1 byte CRC
uint8_t packet[JOYSTICK_MSG_LENGTH] = {};
uint16_t tmp_uint16;
uint32_t tmp_uint32;

// display
char display_str[] = "0088";

// testing
int i_testing = 0;

// other settings
int focus_encoder_sensitivity_division = 4;

void setup() 
{

  // I2C for seven segment display
  Wire.begin(); 
  delay(200);
  d.init();
  display_str[2] = '0' + 10;
  display_str[3] = '0' + 10;
    
  // pin init.
  for(int i=0;i<6;i++)
  {
    pinMode(pin_LED[i],OUTPUT);
    digitalWrite(pin_LED[i],HIGH);
  }
  pinMode(pin_encoder_1_A,INPUT_PULLUP);
  pinMode(pin_encoder_1_B,INPUT_PULLUP);
  pinMode(pin_encoder_2_A,INPUT_PULLUP);
  pinMode(pin_encoder_2_B,INPUT_PULLUP);
  pinMode(pin_encoder_3_A,INPUT_PULLUP);
  pinMode(pin_encoder_3_B,INPUT_PULLUP);
  
  pinMode(pin_joystick_btn,INPUT_PULLUP);

  // encoder interrupt
  attachInterrupt(digitalPinToInterrupt(pin_encoder_1_A), ISR_encoder_1_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(pin_encoder_1_B), ISR_encoder_1_B, CHANGE);

  // set up the packet serial 
  Serial1.begin(115200);
  packetSerial.setStream(&Serial1);
  packetSerial.setPacketHandler(&onPacketReceived);

  // for debugging 
  Serial.begin(20000000);

  // get joystick offset
  delayMicroseconds(5000);
  joystick_offset_x = analogRead(pin_joystick_x);
  joystick_offset_y = analogRead(pin_joystick_y);
  
}

void loop() 
{
  
  // update input sensitivity
  input_sensitivity_xy = (1023-analogRead(pin_pot2))/100; // sensitivity 0-10;
  if(input_sensitivity_xy>9)
    input_sensitivity_xy = 9;
  
  input_sensitivity_z = (1023-analogRead(pin_pot1))/100; // sensitivity 0-10;
  if(input_sensitivity_z>8)
    input_sensitivity_z = 8;
    
  encoder_step_size = min(pow(2,input_sensitivity_z),256); // cap the max z_step_size

  // display input sensitivity
  display_str[0] = '0' + input_sensitivity_xy;
  display_str[1] = '0' + input_sensitivity_z;
  d.displayString(display_str);

  // read joystick
  joystick_delta_x = analogRead(pin_joystick_x) - joystick_offset_x;
  joystick_delta_x = sgn(joystick_delta_x)*max(abs(joystick_delta_x)-joystick_deadband,0)*pow(2,input_sensitivity_xy)/8;
  joystick_delta_x = sgn(joystick_delta_x)*min(abs(joystick_delta_x),32767);
  joystick_delta_y = analogRead(pin_joystick_y) - joystick_offset_y;
  joystick_delta_y = sgn(joystick_delta_y)*max(abs(joystick_delta_y)-joystick_deadband,0)*pow(2,input_sensitivity_xy)/8;
  joystick_delta_y = sgn(joystick_delta_y)*min(abs(joystick_delta_y),32767);

  // read key
  // debouncing to be added

  // send to controller
  encoder_pos = encoder_pos;
  int32_t encoder_pos_ = encoder_pos/4; // artificially descrease the resolution to make it less sensitive
  encoder_pos_ = (encoder_pos_/16)*16;  // make the number integer multiple of 16 (16 microstepping)
  tmp_uint32 = twos_complement(encoder_pos_,4); 
  packet[0] = byte(tmp_uint32>>24);
  packet[1] = byte((tmp_uint32>>16)%256);
  packet[2] = byte((tmp_uint32>>8)%256);
  packet[3] = byte(tmp_uint32%256);
  tmp_uint16 = twos_complement(joystick_delta_x,2); 
  packet[4] = byte((tmp_uint16>>8)%256);
  packet[5] = byte(tmp_uint16%256);
  tmp_uint16 = twos_complement(joystick_delta_y,2); 
  packet[6] = byte((tmp_uint16>>8)%256);
  packet[7] = byte(tmp_uint16%256);
  packet[8] = byte(digitalRead(pin_joystick_btn)); // for testing only, to be replaced with joystick_button_pressed

  //  // testing
  //  packet[8] = i_testing++;
  //  if(i_testing==255)
  //    i_testing = 0;
  
  // CRC to be added
  packet[9] = 0;
  packetSerial.send(packet, JOYSTICK_MSG_LENGTH);

  // process incoming packets
  packetSerial.update();

  // delay
  delayMicroseconds(2000);

  // debug
  Serial.print(encoder_pos_);
  //Serial.print("\t");
  //Serial.print(tmp_uint32);
  Serial.print("\t dx:");
  Serial.print(joystick_delta_x);
  Serial.print("\t dy:");
  Serial.print(joystick_delta_y);
  Serial.print("\t btn:");
  Serial.print(digitalRead(pin_joystick_btn));
  Serial.println("\t");
  // uint64_t tmp = pow(256,4); print does not work
  // Serial.println( tmp );
  
}

// handling packest from the controller
void onPacketReceived(const uint8_t* buffer, size_t size)
{
  
}

// interrupts
void ISR_encoder_1_A()
{
  if(digitalRead(pin_encoder_1_B)==0 && digitalRead(pin_encoder_1_A)==1)
    encoder_pos = encoder_pos + encoder_step_size;
  else if (digitalRead(pin_encoder_1_B)==1 && digitalRead(pin_encoder_1_A)==0)
    encoder_pos = encoder_pos + encoder_step_size;
  else
    encoder_pos = encoder_pos - encoder_step_size;
}

void ISR_encoder_1_B()
{
  if(digitalRead(pin_encoder_1_B)==0 && digitalRead(pin_encoder_1_A)==1 )
    encoder_pos = encoder_pos - encoder_step_size;
  else if (digitalRead(pin_encoder_1_B)==1 && digitalRead(pin_encoder_1_A)==0)
    encoder_pos = encoder_pos - encoder_step_size;
  else
    encoder_pos = encoder_pos + encoder_step_size;
}

// utils
uint32_t twos_complement(long signedLong,int N)
{
  uint32_t NBytesUnsigned = 0;
  if(signedLong>=0)
    NBytesUnsigned = signedLong;
  else
    NBytesUnsigned = signedLong + uint64_t(pow(256,N));
  return NBytesUnsigned;
}

static inline int sgn(int val) {
 if (val < 0) return -1;
 if (val==0) return 0;
 return 1;
}
