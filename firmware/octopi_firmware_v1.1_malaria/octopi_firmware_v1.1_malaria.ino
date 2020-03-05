#include <TMCStepper.h>
#include <TMCStepper_UTILITY.h>

static inline int sgn(int val) {
 if (val < 0) return -1;
 if (val==0) return 0;
 return 1;
}

// byte[0]: which motor to move: 0 x, 1 y, 2 z, 3 LED, 4 Laser
// byte[1]: what direction: 1 forward, 0 backward
// byte[2]: how many micro steps - upper 8 bits
// byte[3]: how many micro steps - lower 8 bits

static const int CMD_LENGTH = 4;
static const int MSG_LENGTH = 9;
byte buffer_rx[500];
byte buffer_tx[MSG_LENGTH];
volatile int buffer_rx_ptr;
static const int N_BYTES_POS = 3;

// v0.1.0 pin def
/*
static const int X_dir  = 36;
static const int X_step = 37;
static const int X_driver_uart = 24;
static const int X_en = 45;

static const int Y_dir = 30;
static const int Y_step = 31;
static const int Y_driver_uart = 25;
static const int Y_en = 49;

static const int Z_dir = 27;
static const int Z_step = 28;
static const int Z_driver_uart = 23;
static const int Z_en = 51;

static const int LED = 38;
static const int LASER = 39;
static const int SHUTTER = 40;
*/

// v0.1.1 pin def
static const int X1_dir  = 36;
static const int X1_step = 37;
static const int X1_driver_uart = 24;
static const int X1_en = 41;

static const int X2_dir  = 33;
static const int X2_step = 34;
static const int X2_driver_uart = 22;
static const int X2_en = 40;

static const int Y_dir = 30;
static const int Y_step = 31;
static const int Y_driver_uart = 25;
static const int Y_en = 39;

static const int Z_dir = 27;
static const int Z_step = 28;
static const int Z_driver_uart = 23;
static const int Z_en = 38;

static const int LED = 48;
static const int LASER = 49;
static const int SHUTTER = 50;

#define STEPPER_SERIAL Serial1 
static const uint8_t X_driver_ADDRESS = 0b00;
static const float R_SENSE = 0.11f;
TMC2209Stepper X1_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);
TMC2209Stepper X2_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);
TMC2209Stepper Y_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);
TMC2209Stepper Z_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);

#include <AccelStepper.h>
#include <MultiStepper.h>
AccelStepper stepper_X1 = AccelStepper(AccelStepper::DRIVER, X1_step, X1_dir);
AccelStepper stepper_X2 = AccelStepper(AccelStepper::DRIVER, X2_step, X2_dir);
MultiStepper stepper_X;
AccelStepper stepper_Y = AccelStepper(AccelStepper::DRIVER, Y_step, Y_dir);
AccelStepper stepper_Z = AccelStepper(AccelStepper::DRIVER, Z_step, Z_dir);
static const long steps_per_mm_XY = 40*8;
static const long steps_per_mm_Z = 5333;
//constexpr float MAX_VELOCITY_X_mm = 7;
//constexpr float MAX_VELOCITY_Y_mm = 7;
constexpr float MAX_VELOCITY_X_mm = 10;
constexpr float MAX_VELOCITY_Y_mm = 10;
constexpr float MAX_VELOCITY_Z_mm = 2;
constexpr float MAX_ACCELERATION_X_mm = 200; 
constexpr float MAX_ACCELERATION_Y_mm = 200;
constexpr float MAX_ACCELERATION_Z_mm = 10;
static const long X_NEG_LIMIT_MM = 0;
static const long X_POS_LIMIT_MM = 25;
static const long Y_NEG_LIMIT_MM = 0;
static const long Y_POS_LIMIT_MM = 50;
static const long Z_NEG_LIMIT_MM = -1;
static const long Z_POS_LIMIT_MM = 1;

bool runSpeed_flag_X = false;
bool runSpeed_flag_Y = false;
bool runSpeed_flag_Z = false;
long X_commanded_target_position = 0;
long Y_commanded_target_position = 0;
long Z_commanded_target_position = 0;
bool X_commanded_movement_in_progress = false;
bool Y_commanded_movement_in_progress = false;
bool Z_commanded_movement_in_progress = false;

long X_pos = 0;
long Y_pos = 0;
long Z_pos = 0;
long target_position;

// encoder
bool X_use_encoder = false;
bool Y_use_encoder = false;
bool Z_use_encoder = false;

#include <DueTimer.h>
static const int TIMER_PERIOD = 500; // in us
static const int interval_read_joystick = 10000; // in us
static const int interval_send_pos_update = 50000; // in us
volatile int counter_read_joystick = 0;
volatile int counter_send_pos_update = 0;
volatile bool flag_read_joystick = false;
volatile bool flag_send_pos_update = false;
int joystick_offset_x = 512;
int joystick_offset_y = 512;
constexpr int joystickSensitivity = 10; // range from 5 to 100 (for comparison with number in the range of 0-512)

/*
#include <Wire.h>
#include "SparkFun_Qwiic_Joystick_Arduino_Library.h" //Click here to get the library: http://librarymanager/All#SparkFun_joystick
JOYSTICK joystick; //Create instance of this object
#include "SparkFun_Qwiic_Twist_Arduino_Library.h" //Click here to get the library: http://librarymanager/All#SparkFun_Twist
TWIST twist; //Create instance of this object
*/


// joystick
volatile int deltaX = 0;
volatile int deltaY = 0;
volatile float deltaX_float = 0;
volatile float deltaY_float = 0;


// focus
static const int focusWheel_A  = 4;
static const int focusWheel_B  = 3;
static const int focusWheel_CS  = 2;
static const int focusWheel_IDX  = 5;
volatile long focusPosition = 0;

//#include <Adafruit_ADS1015.h>
//Adafruit_ADS1115 ads1115(0x48);

void setup() {

  // Initialize Native USB port
  //SerialUSB.begin(2000000);     
  //while(!SerialUSB);            // Wait until connection is established
  buffer_rx_ptr = 0;

  pinMode(13, OUTPUT);
  digitalWrite(13,LOW);
  
  // enable pins
  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);
  
  pinMode(LASER, OUTPUT);
  digitalWrite(LED, LOW);

  pinMode(SHUTTER, OUTPUT);
  digitalWrite(LED, LOW);
  
  pinMode(X1_driver_uart, OUTPUT);
  pinMode(X1_dir, OUTPUT);
  pinMode(X1_step, OUTPUT);

  pinMode(X2_driver_uart, OUTPUT);
  pinMode(X2_dir, OUTPUT);
  pinMode(X2_step, OUTPUT);

  pinMode(Y_driver_uart, OUTPUT);
  pinMode(Y_dir, OUTPUT);
  pinMode(Y_step, OUTPUT);

  pinMode(Z_driver_uart, OUTPUT);
  pinMode(Z_dir, OUTPUT);
  pinMode(Z_step, OUTPUT);

  pinMode(LED, OUTPUT);
  pinMode(LASER, OUTPUT);
  digitalWrite(LED, LOW);
  digitalWrite(LASER, LOW);

  // initialize stepper driver
  STEPPER_SERIAL.begin(115200);
  
  digitalWrite(X1_driver_uart, true);
  while(!STEPPER_SERIAL);
  X1_driver.begin();
  X1_driver.I_scale_analog(false);
  X1_driver.rms_current(250,0.1); //I_run and holdMultiplier
  X1_driver.microsteps(8);
  X1_driver.TPOWERDOWN(2);
  X1_driver.pwm_autoscale(true);
  X1_driver.en_spreadCycle(false);
  X1_driver.toff(4);
  digitalWrite(X1_driver_uart, false);

  digitalWrite(X2_driver_uart, true);
  while(!STEPPER_SERIAL);
  X2_driver.begin();
  X2_driver.I_scale_analog(false);
  X2_driver.rms_current(250,0.1); //I_run and holdMultiplier
  X2_driver.microsteps(8);
  X2_driver.TPOWERDOWN(2);
  X2_driver.pwm_autoscale(true);
  X2_driver.en_spreadCycle(false);
  X2_driver.toff(4);
  digitalWrite(X2_driver_uart, false);

  stepper_X.addStepper(stepper_X1);
  stepper_X.addStepper(stepper_X2);
  
  digitalWrite(Y_driver_uart, true);
  while(!STEPPER_SERIAL);
  Y_driver.begin();
  Y_driver.I_scale_analog(false);
  Y_driver.rms_current(250,0.1); //I_run and holdMultiplier
  Y_driver.microsteps(8);
  Y_driver.pwm_autoscale(true);
  Y_driver.TPOWERDOWN(2);
  Y_driver.en_spreadCycle(false);
  Y_driver.toff(4);
  digitalWrite(Y_driver_uart, false);

  digitalWrite(Z_driver_uart, true);
  while(!STEPPER_SERIAL);
  Z_driver.I_scale_analog(false);
  Z_driver.begin();
  Z_driver.rms_current(500,0.4); //I_run and holdMultiplier
  Z_driver.microsteps(8);
  Z_driver.TPOWERDOWN(2);
  Z_driver.pwm_autoscale(true);
  Z_driver.toff(4);
  digitalWrite(Z_driver_uart, false);

  stepper_X1.setEnablePin(X1_en);
  stepper_X2.setEnablePin(X2_en);
  stepper_Y.setEnablePin(Y_en);
  stepper_Z.setEnablePin(Z_en);
  
  stepper_X1.setPinsInverted(true, false, true);
  stepper_X2.setPinsInverted(true, false, true);
  stepper_Y.setPinsInverted(true, false, true);
  stepper_Z.setPinsInverted(false, false, true);
  
  stepper_X1.setMaxSpeed(MAX_VELOCITY_X_mm*steps_per_mm_XY);
  stepper_X2.setMaxSpeed(MAX_VELOCITY_X_mm*steps_per_mm_XY);
  stepper_Y.setMaxSpeed(MAX_VELOCITY_Y_mm*steps_per_mm_XY);
  stepper_Z.setMaxSpeed(MAX_VELOCITY_Z_mm*steps_per_mm_Z);
  
  stepper_X1.setAcceleration(MAX_ACCELERATION_X_mm*steps_per_mm_XY);
  stepper_X2.setAcceleration(MAX_ACCELERATION_X_mm*steps_per_mm_XY);
  stepper_Y.setAcceleration(MAX_ACCELERATION_Y_mm*steps_per_mm_XY);
  stepper_Z.setAcceleration(MAX_ACCELERATION_Z_mm*steps_per_mm_Z);

  stepper_X1.enableOutputs();
  stepper_X2.enableOutputs();
  stepper_Y.enableOutputs();
  stepper_Z.enableOutputs();

  /*
  joystick.begin(Wire1);
  twist.begin(Wire1);
  twist.setCount(0);
  */

  // focus
  pinMode(focusWheel_A,INPUT);
  pinMode(focusWheel_B,INPUT);
  pinMode(focusWheel_IDX,INPUT);
  pinMode(focusWheel_CS,OUTPUT);
  digitalWrite(focusWheel_CS,LOW);
  attachInterrupt(digitalPinToInterrupt(focusWheel_A), ISR_focusWheel_A, RISING);
  attachInterrupt(digitalPinToInterrupt(focusWheel_B), ISR_focusWheel_B, RISING);

  // joystick
  analogReadResolution(10);
  joystick_offset_x = analogRead(A0);
  joystick_offset_y = analogRead(A1);
  
  Timer3.attachInterrupt(timer_interruptHandler);
  Timer3.start(TIMER_PERIOD); // Calls every 500 us

  //ADC
  //ads1115.begin();
}

void loop() {

  // read one meesage from the buffer
  while (SerialUSB.available()) { 
    buffer_rx[buffer_rx_ptr] = SerialUSB.read();
    buffer_rx_ptr = buffer_rx_ptr + 1;
    if (buffer_rx_ptr == CMD_LENGTH) {
      buffer_rx_ptr = 0;
      if(buffer_rx[0]==0)
      {
        long relative_position = long(buffer_rx[1]*2-1)*(long(buffer_rx[2])*256 + long(buffer_rx[3]));
        X_commanded_target_position = ( relative_position>0?min(stepper_X1.currentPosition()+relative_position,X_POS_LIMIT_MM*steps_per_mm_XY):max(stepper_X1.currentPosition()+relative_position,X_NEG_LIMIT_MM*steps_per_mm_XY) );
        long target_positions[2];
        target_positions[0] = X_commanded_target_position;
        target_positions[1] = X_commanded_target_position;
        stepper_X.moveTo(target_positions);
        X_commanded_movement_in_progress = true;
      }
      else if(buffer_rx[0]==1)
      {
        long relative_position = long(buffer_rx[1]*2-1)*(long(buffer_rx[2])*256 + long(buffer_rx[3]));
        Y_commanded_target_position = ( relative_position>0?min(stepper_Y.currentPosition()+relative_position,Y_POS_LIMIT_MM*steps_per_mm_XY):max(stepper_Y.currentPosition()+relative_position,Y_NEG_LIMIT_MM*steps_per_mm_XY) );
        stepper_Y.moveTo(Y_commanded_target_position);
        Y_commanded_movement_in_progress = true;
      }
      else if(buffer_rx[0]==2)
      {
        long relative_position = long(buffer_rx[1]*2-1)*(long(buffer_rx[2])*256 + long(buffer_rx[3]));
        Z_commanded_target_position = ( relative_position>0?min(stepper_Z.currentPosition()+relative_position,Z_POS_LIMIT_MM*steps_per_mm_Z):max(stepper_Z.currentPosition()+relative_position,Z_NEG_LIMIT_MM*steps_per_mm_Z) );
        stepper_Z.runToNewPosition(Z_commanded_target_position);
        focusPosition = Z_commanded_target_position;
        //stepper_Z.moveTo(Z_commanded_target_position);
        Z_commanded_movement_in_progress = true;
      }
      else if(buffer_rx[0]==3)
        led_switch(buffer_rx[1]);
      else if(buffer_rx[0]==4)
        laser_switch(buffer_rx[1]);
      else if(buffer_rx[0]==5)
        shutter_switch(buffer_rx[1]);
      else if(buffer_rx[0]==6){
        // read ADC
        // int16_t adc0 = ads1115.readADC_SingleEnded(0);
        // SerialUSB.write(byte(adc0 >> 8));
        // SerialUSB.write(byte(adc0 & 255));
      }
      
      /*
      SerialUSB.print(buffer_rx[0]);
      SerialUSB.print(buffer_rx[1]);
      SerialUSB.print(buffer_rx[2]);
      SerialUSB.print(buffer_rx[3]);
      SerialUSB.print('#');
      */
      
      //break; // exit the while loop after reading one message
    }
  }

  if(flag_read_joystick) 
  {
    // read x joystick
    if(!X_commanded_movement_in_progress) //if(stepper_X1.distanceToGo()==0) // only read joystick when computer commanded travel has finished - doens't work
    {
      deltaX = analogRead(A0) - joystick_offset_x;
      deltaX_float = -deltaX;
      if(abs(deltaX_float)>joystickSensitivity)
      {
        stepper_X1.setSpeed(sgn(deltaX_float)*((abs(deltaX_float)-joystickSensitivity)/512.0)*MAX_VELOCITY_X_mm*steps_per_mm_XY);
        stepper_X2.setSpeed(sgn(deltaX_float)*((abs(deltaX_float)-joystickSensitivity)/512.0)*MAX_VELOCITY_X_mm*steps_per_mm_XY);
        runSpeed_flag_X = true;
        if(stepper_X1.currentPosition()>=X_POS_LIMIT_MM*steps_per_mm_XY && deltaX_float>0)
        {
          runSpeed_flag_X = false;
          stepper_X1.setSpeed(0);
          stepper_X2.setSpeed(0);
        }
        if(stepper_X1.currentPosition()<=X_NEG_LIMIT_MM*steps_per_mm_XY && deltaX_float<0)
          {
          runSpeed_flag_X = false;
          stepper_X1.setSpeed(0);
          stepper_X2.setSpeed(0);
        }
      }
      else
      {
        runSpeed_flag_X = false;
        stepper_X1.setSpeed(0);
        stepper_X2.setSpeed(0);
      }
    }
    else
      runSpeed_flag_X = false;

    // read y joystick
    if(!Y_commanded_movement_in_progress)
    {
      deltaY = analogRead(A1) - joystick_offset_y;
      deltaY_float = deltaY;
      if(abs(deltaY)>joystickSensitivity)
      {
        stepper_Y.setSpeed(sgn(deltaY_float)*((abs(deltaY_float)-joystickSensitivity)/512.0)*MAX_VELOCITY_Y_mm*steps_per_mm_XY);
        runSpeed_flag_Y = true;
        if(stepper_Y.currentPosition()>=Y_POS_LIMIT_MM*steps_per_mm_XY && deltaY_float>0)
        {
          runSpeed_flag_Y = false;
          stepper_Y.setSpeed(0);
        }
        if(stepper_Y.currentPosition()<=Y_NEG_LIMIT_MM*steps_per_mm_XY && deltaY_float<0)
        {
          runSpeed_flag_Y = false;
          stepper_Y.setSpeed(0);
        }
      }
      else
      {
        runSpeed_flag_Y = false;
        stepper_Y.setSpeed(0);
      }
    }
    else
      runSpeed_flag_Y = false;

    // focus control
    stepper_Z.moveTo(focusPosition);
    
    flag_read_joystick = false;
  }

  // send position update to computer
  if(flag_send_pos_update)
  {
    long X_pos_NBytesUnsigned = ( X_use_encoder?signed2NBytesUnsigned(X_pos,N_BYTES_POS):signed2NBytesUnsigned(stepper_X1.currentPosition(),N_BYTES_POS) );
    buffer_tx[0] = byte(X_pos_NBytesUnsigned>>16);
    buffer_tx[1] = byte((X_pos_NBytesUnsigned>>8)%256);
    buffer_tx[2] = byte(X_pos_NBytesUnsigned%256);
    
    long Y_pos_NBytesUnsigned = ( Y_use_encoder?signed2NBytesUnsigned(Y_pos,N_BYTES_POS):signed2NBytesUnsigned(stepper_Y.currentPosition(),N_BYTES_POS) );
    buffer_tx[3] = byte(Y_pos_NBytesUnsigned>>16);
    buffer_tx[4] = byte((Y_pos_NBytesUnsigned>>8)%256);
    buffer_tx[5] = byte(Y_pos_NBytesUnsigned%256);

    long Z_pos_NBytesUnsigned = ( Z_use_encoder?signed2NBytesUnsigned(Z_pos,N_BYTES_POS):signed2NBytesUnsigned(stepper_Z.currentPosition(),N_BYTES_POS) );
    buffer_tx[6] = byte(Z_pos_NBytesUnsigned>>16);
    buffer_tx[7] = byte((Z_pos_NBytesUnsigned>>8)%256);
    buffer_tx[8] = byte(Z_pos_NBytesUnsigned%256);
    
    SerialUSB.write(buffer_tx,MSG_LENGTH);
    flag_send_pos_update = false;
  }

  // encoded movement
  if(X_use_encoder)
  {
    stepper_X1.setCurrentPosition(X_pos);
    stepper_X2.setCurrentPosition(X_pos);
  }
  if(Y_use_encoder)
    stepper_Y.setCurrentPosition(Y_pos);
  if(Z_use_encoder)
    stepper_Z.setCurrentPosition(Z_pos);

  // check if commanded position has been reached
  if(X_commanded_movement_in_progress && stepper_X1.currentPosition()==X_commanded_target_position)
    X_commanded_movement_in_progress = false;
  if(Y_commanded_movement_in_progress && stepper_Y.currentPosition()==Y_commanded_target_position)
    Y_commanded_movement_in_progress = false;
  if(Z_commanded_movement_in_progress && stepper_Z.currentPosition()==Z_commanded_target_position)
    Z_commanded_movement_in_progress = false;

  // move motors
  if(X_commanded_movement_in_progress)
    stepper_X.run();
  else if(runSpeed_flag_X)
  {
    stepper_X1.runSpeed();
    stepper_X2.runSpeed();
  }
    
  if(Y_commanded_movement_in_progress)
    stepper_Y.run();
  else if(runSpeed_flag_Y)
    stepper_Y.runSpeed();
  
  stepper_Z.run();
}

////////////////////////////////// LED/LASER/SHUTTER switches ////////////////////////////
void led_switch(int state)
{
  if(state>0)
  {
    digitalWrite(LED, HIGH);
    digitalWrite(13, HIGH);
  }
  else
  {
    digitalWrite(LED, LOW);
    digitalWrite(13, LOW);
  }
}

void laser_switch(int state)
{
  if(state>0)
    digitalWrite(LASER, HIGH);
  else
    digitalWrite(LASER, LOW);
}

void shutter_switch(int state)
{
  if(state>0)
    digitalWrite(SHUTTER, HIGH);
  else
    digitalWrite(SHUTTER, LOW);
}

// timer interrupt
void timer_interruptHandler(){
  counter_read_joystick = counter_read_joystick + 1;
  if(counter_read_joystick==interval_read_joystick/TIMER_PERIOD)
  {
    flag_read_joystick = true;
    counter_read_joystick = 0;
  }
  counter_send_pos_update = counter_send_pos_update + 1;
  if(counter_send_pos_update==interval_send_pos_update/TIMER_PERIOD)
  {
    flag_send_pos_update = true;
    counter_send_pos_update = 0;
  }
}

void ISR_focusWheel_A(){
  if(digitalRead(focusWheel_B)==1)
  {
    focusPosition = focusPosition + 1;
    digitalWrite(13,HIGH);
  }
  else
  {
    focusPosition = focusPosition - 1;
    digitalWrite(13,LOW);
  }
}

void ISR_focusWheel_B(){
  if(digitalRead(focusWheel_A)==1)
  {
    focusPosition = focusPosition - 1;
  }
  else
  {
    focusPosition = focusPosition + 1;
  }
}

// utils
long signed2NBytesUnsigned(long signedLong,int N)
{
  long NBytesUnsigned = signedLong + pow(256L,N)/2;
  //long NBytesUnsigned = signedLong + 8388608L;
  return NBytesUnsigned;
}
