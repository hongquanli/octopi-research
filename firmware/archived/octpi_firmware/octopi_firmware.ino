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
byte buffer_rx[500];
volatile int buffer_rx_ptr;

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

#define STEPPER_SERIAL Serial1 
static const uint8_t X_driver_ADDRESS = 0b00;
static const float R_SENSE = 0.11f;
TMC2209Stepper X_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);
TMC2209Stepper Y_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);
TMC2209Stepper Z_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);

#include <AccelStepper.h>
AccelStepper stepper_X = AccelStepper(AccelStepper::DRIVER, X_step, X_dir);
AccelStepper stepper_Y = AccelStepper(AccelStepper::DRIVER, Y_step, Y_dir);
AccelStepper stepper_Z = AccelStepper(AccelStepper::DRIVER, Z_step, Z_dir);
constexpr uint32_t steps_per_mm_XY = 1600;
constexpr uint32_t steps_per_mm_Z = 5333;
//constexpr float MAX_VELOCITY_X_mm = 7;
//constexpr float MAX_VELOCITY_Y_mm = 7;
constexpr float MAX_VELOCITY_X_mm = 4;
constexpr float MAX_VELOCITY_Y_mm = 4;
constexpr float MAX_VELOCITY_Z_mm = 2;
constexpr float MAX_ACCELERATION_X_mm = 200;  // 50 mm/s/s
constexpr float MAX_ACCELERATION_Y_mm = 200;  // 50 mm/s/s
constexpr float MAX_ACCELERATION_Z_mm = 10;   // 20 mm/s/s
bool runSpeed_flag_X = false;
bool runSpeed_flag_Y = false;
bool runSpeed_flag_Z = false;


#include <DueTimer.h>
int timerPeriod = 10000; // in us
volatile bool readJoyStickAndEncoder = false;
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

long x_pos = 0;
long y_pos = 0;
long z_pos = 0;

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
  SerialUSB.begin(2000000);     
  while(!SerialUSB);            // Wait until connection is established
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
  
  pinMode(X_driver_uart, OUTPUT);
  pinMode(X_dir, OUTPUT);
  pinMode(X_step, OUTPUT);

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
  
  digitalWrite(X_driver_uart, true);
  while(!STEPPER_SERIAL);
  X_driver.begin();
  X_driver.rms_current(1000); //I_run and holdMultiplier
  X_driver.microsteps(8);
  //X_driver.TPOWERDOWN(2);
  X_driver.pwm_autoscale(true);
  X_driver.en_spreadCycle(false);
  X_driver.toff(4);
  digitalWrite(X_driver_uart, false);
  
  digitalWrite(Y_driver_uart, true);
  while(!STEPPER_SERIAL);
  Y_driver.begin();
  Y_driver.rms_current(1000); //I_run and holdMultiplier
  Y_driver.microsteps(8);
  Y_driver.pwm_autoscale(true);
  //Y_driver.TPOWERDOWN(2);
  Y_driver.en_spreadCycle(false);
  Y_driver.toff(4);
  digitalWrite(Y_driver_uart, false);

  digitalWrite(Z_driver_uart, true);
  while(!STEPPER_SERIAL);
  Z_driver.begin();
  Z_driver.rms_current(500,0.5); //I_run and holdMultiplier
  Z_driver.microsteps(8);
  Z_driver.TPOWERDOWN(2);
  Z_driver.pwm_autoscale(true);
  Z_driver.toff(4);
  digitalWrite(Z_driver_uart, false);

  stepper_X.setEnablePin(X_en);
  stepper_Y.setEnablePin(Y_en);
  stepper_Z.setEnablePin(Z_en);
  
  stepper_X.setPinsInverted(false, false, true);
  stepper_Y.setPinsInverted(false, false, true);
  stepper_Z.setPinsInverted(false, false, true);
  
  stepper_X.setMaxSpeed(MAX_VELOCITY_X_mm*steps_per_mm_XY);
  stepper_Y.setMaxSpeed(MAX_VELOCITY_Y_mm*steps_per_mm_XY);
  stepper_Z.setMaxSpeed(MAX_VELOCITY_Z_mm*steps_per_mm_Z);
  
  stepper_X.setAcceleration(MAX_ACCELERATION_X_mm*steps_per_mm_XY);
  stepper_Y.setAcceleration(MAX_ACCELERATION_Y_mm*steps_per_mm_XY);
  stepper_Z.setAcceleration(MAX_ACCELERATION_Z_mm*steps_per_mm_Z);

  stepper_X.enableOutputs();
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
  
  // joystick
  analogReadResolution(10);
  joystick_offset_x = analogRead(A0);
  joystick_offset_y = analogRead(A1);
  
  
  Timer3.attachInterrupt(timer_interruptHandler);
  Timer3.start(timerPeriod); // Calls every 500 us

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
        stepper_X.runToNewPosition(stepper_X.targetPosition() + int(buffer_rx[1]*2-1)*(int(buffer_rx[2])*256 + int(buffer_rx[3])));
      else if(buffer_rx[0]==1)
        stepper_Y.runToNewPosition(stepper_Y.targetPosition() + int(buffer_rx[1]*2-1)*(int(buffer_rx[2])*256 + int(buffer_rx[3])));
      else if(buffer_rx[0]==2){
        stepper_Z.runToNewPosition(stepper_Z.targetPosition() + int(buffer_rx[1]*2-1)*(int(buffer_rx[2])*256 + int(buffer_rx[3])));
        focusPosition = focusPosition + int(buffer_rx[1]*2-1)*(int(buffer_rx[2])*256 + int(buffer_rx[3]));
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

  if(readJoyStickAndEncoder) {
    //float deltaX = joystick.getHorizontal() - 512;
    deltaX = analogRead(A0) - joystick_offset_x;
    deltaX_float = deltaX;
    if(abs(deltaX_float)>joystickSensitivity){
      stepper_X.setSpeed(sgn(deltaX_float)*((abs(deltaX_float)-joystickSensitivity)/512.0)*MAX_VELOCITY_X_mm*steps_per_mm_XY);
      runSpeed_flag_X = true;
    }
    else {
    //if(stepper_X.distanceToGo()==0)
      stepper_X.setSpeed(0);
      runSpeed_flag_X = false;
    }

    //float deltaY = joystick.getVertical() - 512;
    deltaY = analogRead(A1) - joystick_offset_y;
    deltaY_float = deltaY;
    if(abs(deltaY)>joystickSensitivity){
      stepper_Y.setSpeed(sgn(deltaY_float)*((abs(deltaY_float)-joystickSensitivity)/512.0)*MAX_VELOCITY_Y_mm*steps_per_mm_XY);
      runSpeed_flag_Y = true;
    }
    else {
    //if(stepper_Y.distanceToGo()==0)
      stepper_Y.setSpeed(0);
      runSpeed_flag_Y = false;
    }

    stepper_Z.moveTo(focusPosition);
    //@@@@@@
    
    readJoyStickAndEncoder = false;
  }


  // move motors
  if(runSpeed_flag_X)
    stepper_X.runSpeed();
  else
    stepper_X.run();

  if(runSpeed_flag_Y)
    stepper_Y.runSpeed();
  else
    stepper_Y.run();
    
  //stepper_X.runSpeed();
  //stepper_Y.runSpeed();
  
  stepper_Z.run();
}

////////////////////////////////// LED/LASER/SHUTTER switches ////////////////////////////
void led_switch(int state)
{
  if(state>0)
    digitalWrite(LED, HIGH);
  else
    digitalWrite(LED, LOW);
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
  readJoyStickAndEncoder = true;
}

void ISR_focusWheel_A(){
  if(digitalRead(focusWheel_B)==1)
    focusPosition = focusPosition + 4;
  else
    focusPosition = focusPosition - 4;
}
