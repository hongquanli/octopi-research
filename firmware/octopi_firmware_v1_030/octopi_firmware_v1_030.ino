#include <TMCStepper.h>
#include <TMCStepper_UTILITY.h>
#include <DueTimer.h>
#include <AccelStepper.h>
#include <Adafruit_DotStar.h>
#include <SPI.h>
#include "def.h"
//#include "def_gravitymachine.h"
//#include "def_squid.h"
//#include "def_platereader.h"
//#include "def_squid_vertical.h"

/***************************************************************************************************/
/***************************************** Communications ******************************************/
/***************************************************************************************************/
// byte[0]: which motor to move: 0 x, 1 y, 2 z, 3 LED, 4 Laser
// byte[1]: what direction: 1 forward, 0 backward
// byte[2]: how many micro steps - upper 8 bits
// byte[3]: how many micro steps - lower 8 bits

static const int CMD_LENGTH = 8;
static const int MSG_LENGTH = 24;
byte buffer_rx[512];
byte buffer_tx[MSG_LENGTH];
volatile int buffer_rx_ptr;
static const int N_BYTES_POS = 4;
byte cmd_id = 0;
bool mcu_cmd_execution_in_progress = false;

// command sets
static const int MOVE_X = 0;
static const int MOVE_Y = 1;
static const int MOVE_Z = 2;
static const int MOVE_THETA = 3;
static const int HOME_OR_ZERO = 5;
static const int MOVETO_X = 6;
static const int MOVETO_Y = 7;
static const int MOVETO_Z = 8;
static const int TURN_ON_ILLUMINATION = 10;
static const int TURN_OFF_ILLUMINATION = 11;
static const int SET_ILLUMINATION = 12;
static const int SET_ILLUMINATION_LED_MATRIX = 13;
static const int ACK_JOYSTICK_BUTTON_PRESSED = 14;

static const int COMPLETED_WITHOUT_ERRORS = 0;
static const int IN_PROGRESS = 1;
static const int CMD_CHECKSUM_ERROR = 2;
static const int CMD_INVALID = 3;
static const int CMD_EXECUTION_ERROR = 4;

static const int HOME_NEGATIVE = 1;
static const int HOME_POSITIVE = 0;
static const int HOME_OR_ZERO_ZERO = 2;

static const int AXIS_X = 0;
static const int AXIS_Y = 1;
static const int AXIS_Z = 2;
static const int AXIS_THETA = 3;
static const int AXES_XY = 4;

static const int BIT_POS_JOYSTICK_BUTTON = 0;

/***************************************************************************************************/
/**************************************** Pin definations ******************************************/
/***************************************************************************************************/
// v0.2.1 pin def

// linear actuators
static const int X_dir  = 28;
static const int X_step = 26;
static const int Y_dir = 24;
static const int Y_step = 22;
static const int Z_dir = 27;
static const int Z_step = 29;

// illumination
static const int LED = 30;
static const int LASER_405nm = 31;
static const int LASER_488nm = 32;
static const int LASER_638nm = 33;
static const int LASER_561nm = 34;

// encoders and limit switches
static const int X_encoder_A = 4;
static const int X_encoder_B = 5;
static const int X_LIM = 2;
static const int Y_encoder_A = 8;
static const int Y_encoder_B = 9;
static const int Y_LIM = 6;
static const int Z_encoder_A = 12;
static const int Z_encoder_B = 13;
static const int Z_LIM = 10;

// focus wheel
static const int focusWheel_A  = 41;
static const int focusWheel_B  = 42;
static const int focusWheel_IDX  = 43;
volatile long focusPosition = 0;

// joystick button
static const int joystick_button  = 44;

// analog input
#define analog_in_0 A6
#define analog_in_1 A7
bool joystick_not_connected = false;

// joy stick
#define joystick_X A4
#define joystick_Y A5

// rocker switch
#define rocker 40

/***************************************************************************************************/
/******************************************* steppers **********************************************/
/***************************************************************************************************/
#define STEPPER_SERIAL Serial3
static const uint8_t X_driver_ADDRESS = 0b00;
static const uint8_t Y_driver_ADDRESS = 0b01;
static const uint8_t Z_driver_ADDRESS = 0b11;
static const float R_SENSE = 0.11f;
TMC2209Stepper X_driver(&STEPPER_SERIAL, R_SENSE, X_driver_ADDRESS);
TMC2209Stepper Y_driver(&STEPPER_SERIAL, R_SENSE, Y_driver_ADDRESS);
TMC2209Stepper Z_driver(&STEPPER_SERIAL, R_SENSE, Z_driver_ADDRESS);

AccelStepper stepper_X = AccelStepper(AccelStepper::DRIVER, X_step, X_dir);
AccelStepper stepper_Y = AccelStepper(AccelStepper::DRIVER, Y_step, Y_dir);
AccelStepper stepper_Z = AccelStepper(AccelStepper::DRIVER, Z_step, Z_dir);

volatile bool runSpeed_flag_X = false;
volatile bool runSpeed_flag_Y = false;
volatile bool runSpeed_flag_Z = false;
volatile long X_commanded_target_position = 0;
volatile long Y_commanded_target_position = 0;
volatile long Z_commanded_target_position = 0;
volatile bool X_commanded_movement_in_progress = false;
volatile bool Y_commanded_movement_in_progress = false;
volatile bool Z_commanded_movement_in_progress = false;

long target_position;

volatile int32_t X_pos = 0;
volatile int32_t Y_pos = 0;
volatile int32_t Z_pos = 0;

bool closed_loop_position_control = false;

// limit swittch
bool is_homing_X = false;
bool is_homing_Y = false;
bool is_homing_Z = false;
bool is_homing_XY = false;
volatile bool home_X_found = false;
volatile bool home_Y_found = false;
volatile bool home_Z_found = false;
bool is_preparing_for_homing_X = false;
bool is_preparing_for_homing_Y = false;
bool is_preparing_for_homing_Z = false;
bool homing_direction_X;
bool homing_direction_Y;
bool homing_direction_Z;
/* to do: move the movement direction sign from configuration.txt (python) to the firmware (with 
 * setPinsInverted() so that homing_direction_X, homing_direction_Y, homing_direction_Z will no 
 * longer be needed. This way the home switches can act as limit switches - right now because 
 * homing_direction_ needs be set by the computer, before they're set, the home switches cannot be
 * used as limit switches. Alternatively, add homing_direction_set variables.
 */


/***************************************************************************************************/
/******************************************* joystick **********************************************/
/***************************************************************************************************/
static const int TIMER_PERIOD = 500; // in us
static const int interval_read_joystick = 10000; // in us
static const int interval_send_pos_update = 10000; // in us
volatile int counter_read_joystick = 0;
volatile int counter_send_pos_update = 0;
volatile bool flag_read_joystick = false;
volatile bool flag_send_pos_update = false;
int joystick_offset_x = 512;
int joystick_offset_y = 512;

// joystick
int deltaX = 0;
int deltaY = 0;
float deltaX_float = 0;
float deltaY_float = 0;
float speed_XY_factor = 0;

// joystick button
volatile bool joystick_button_pressed = false;
volatile long joystick_button_pressed_timestamp = 0;

// rocker
bool rocker_state = false;

/***************************************************************************************************/
/***************************************** illumination ********************************************/
/***************************************************************************************************/
int illumination_source = 0;
uint16_t illumination_intensity = 65535;
uint8_t led_matrix_r = 0;
uint8_t led_matrix_g = 0;
uint8_t led_matrix_b = 0;
static const int LED_MATRIX_MAX_INTENSITY = 100;
static const float GREEN_ADJUSTMENT_FACTOR = 2.5;
static const float RED_ADJUSTMENT_FACTOR = 0.7;
static const float BLUE_ADJUSTMENT_FACTOR = 1;
bool illumination_is_on = false;
void turn_on_illumination();
void turn_off_illumination();

static const int ILLUMINATION_SOURCE_LED_ARRAY_FULL = 0;
static const int ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF = 1;
static const int ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF = 2;
static const int ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR = 3;
static const int ILLUMINATION_SOURCE_LED_EXTERNAL_FET = 5;
static const int ILLUMINATION_SOURCE_405NM = 11;
static const int ILLUMINATION_SOURCE_488NM = 12;
static const int ILLUMINATION_SOURCE_638NM = 13;
static const int ILLUMINATION_SOURCE_561NM = 14;

Adafruit_DotStar matrix(DOTSTAR_NUM_LEDS, DOTSTAR_BRG);
void set_all(Adafruit_DotStar & matrix, int r, int g, int b);
void set_left(Adafruit_DotStar & matrix, int r, int g, int b);
void set_right(Adafruit_DotStar & matrix, int r, int g, int b);
void clear_matrix(Adafruit_DotStar & matrix);
void turn_on_LED_matrix_pattern(Adafruit_DotStar & matrix, int pattern, uint8_t led_matrix_r, uint8_t led_matrix_g, uint8_t led_matrix_b);

void turn_on_illumination()
{
  illumination_is_on = true;
  switch(illumination_source)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,led_matrix_r,led_matrix_g,led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF,led_matrix_r,led_matrix_g,led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF,led_matrix_r,led_matrix_g,led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR,led_matrix_r,led_matrix_g,led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_EXTERNAL_FET:
      digitalWrite(LED,HIGH);
      break;
    case ILLUMINATION_SOURCE_405NM:
      digitalWrite(LASER_405nm,HIGH);
      break;
    case ILLUMINATION_SOURCE_488NM:
      digitalWrite(LASER_488nm,HIGH);
      break;
    case ILLUMINATION_SOURCE_638NM:
      digitalWrite(LASER_638nm,HIGH);
      break;
    case ILLUMINATION_SOURCE_561NM:
      digitalWrite(LASER_561nm,HIGH);
      break;
  }
}

void turn_off_illumination()
{
  switch(illumination_source)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_EXTERNAL_FET:
      digitalWrite(LED,LOW);
      break;
    case ILLUMINATION_SOURCE_405NM:
      digitalWrite(LASER_405nm,LOW);
      break;
    case ILLUMINATION_SOURCE_488NM:
      digitalWrite(LASER_488nm,LOW);
      break;
    case ILLUMINATION_SOURCE_638NM:
      digitalWrite(LASER_638nm,LOW);
      break;
    case ILLUMINATION_SOURCE_561NM:
      digitalWrite(LASER_561nm,LOW);
      break;
  }
  illumination_is_on = false;
}

void set_illumination(int source, uint16_t intensity)
{
  illumination_source = source;
  illumination_intensity = intensity;
  if(illumination_is_on)
    turn_on_illumination(); //update the illumination
}

void set_illumination_led_matrix(int source, uint8_t r, uint8_t g, uint8_t b)
{
  illumination_source = source;
  led_matrix_r = r;
  led_matrix_g = g;
  led_matrix_b = b;
  if(illumination_is_on)
    turn_on_illumination(); //update the illumination
}

/***************************************************************************************************/
/********************************************* setup ***********************************************/
/***************************************************************************************************/

void setup() {

  // Initialize Native USB port
  //SerialUSB.begin(2000000);     
  //while(!SerialUSB);            // Wait until connection is established
  buffer_rx_ptr = 0;

//  pinMode(13, OUTPUT);
//  digitalWrite(13,LOW);
  
  // enable pins
  pinMode(LED, OUTPUT);
  digitalWrite(LED, LOW);

  pinMode(LASER_405nm, OUTPUT);
  digitalWrite(LASER_405nm, LOW);

  pinMode(LASER_488nm, OUTPUT);
  digitalWrite(LASER_488nm, LOW);

  pinMode(LASER_638nm, OUTPUT);
  digitalWrite(LASER_638nm, LOW);

  pinMode(LASER_561nm, OUTPUT);
  digitalWrite(LASER_561nm, LOW);

  digitalWrite(LED, LOW);
  
  pinMode(X_dir, OUTPUT);
  pinMode(X_step, OUTPUT);

  pinMode(Y_dir, OUTPUT);
  pinMode(Y_step, OUTPUT);

  pinMode(Z_dir, OUTPUT);
  pinMode(Z_step, OUTPUT);

  pinMode(X_LIM, INPUT_PULLUP);
  pinMode(Y_LIM, INPUT_PULLUP);
  pinMode(Z_LIM, INPUT_PULLUP);

  pinMode(rocker,INPUT);

  // initialize stepper driver
  STEPPER_SERIAL.begin(115200);
  
  while(!STEPPER_SERIAL);
  X_driver.begin();
  X_driver.I_scale_analog(false);
  X_driver.rms_current(500); //I_run and holdMultiplier
  X_driver.microsteps(8);
  X_driver.TPOWERDOWN(2);
  X_driver.pwm_autoscale(true);
  X_driver.en_spreadCycle(false);
  X_driver.toff(4);
  
  while(!STEPPER_SERIAL);
  Y_driver.begin();
  Y_driver.I_scale_analog(false);  
  Y_driver.rms_current(500); //I_run and holdMultiplier
  Y_driver.microsteps(8);
  Y_driver.pwm_autoscale(true);
  Y_driver.TPOWERDOWN(2);
  Y_driver.en_spreadCycle(false);
  Y_driver.toff(4);

  while(!STEPPER_SERIAL);
  Z_driver.begin();
  Z_driver.I_scale_analog(false);  
  Z_driver.rms_current(500,0.5); //I_run and holdMultiplier
  Z_driver.microsteps(8);
  Z_driver.TPOWERDOWN(2);
  Z_driver.pwm_autoscale(true);
  Z_driver.toff(4);
  
  stepper_X.setPinsInverted(false, false, true);
  stepper_Y.setPinsInverted(false, false, true);
  stepper_Z.setPinsInverted(false, false, true);
  
  stepper_X.setMaxSpeed(MAX_VELOCITY_X_mm*steps_per_mm_X);
  stepper_Y.setMaxSpeed(MAX_VELOCITY_Y_mm*steps_per_mm_Y);
  stepper_Z.setMaxSpeed(MAX_VELOCITY_Z_mm*steps_per_mm_Z);
  
  stepper_X.setAcceleration(MAX_ACCELERATION_X_mm*steps_per_mm_X);
  stepper_Y.setAcceleration(MAX_ACCELERATION_Y_mm*steps_per_mm_Y);
  stepper_Z.setAcceleration(MAX_ACCELERATION_Z_mm*steps_per_mm_Z);

  stepper_X.enableOutputs();
  stepper_Y.enableOutputs();
  stepper_Z.enableOutputs();

  // xyz encoder
  pinMode(X_encoder_A,INPUT_PULLUP);
  pinMode(X_encoder_B,INPUT_PULLUP);
  pinMode(Y_encoder_A,INPUT_PULLUP);
  pinMode(Y_encoder_B,INPUT_PULLUP);
  pinMode(Z_encoder_A,INPUT_PULLUP);
  pinMode(Z_encoder_B,INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(X_encoder_A), ISR_X_encoder_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(X_encoder_B), ISR_X_encoder_B, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Y_encoder_A), ISR_Y_encoder_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Y_encoder_B), ISR_Y_encoder_B, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Z_encoder_A), ISR_Z_encoder_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Z_encoder_B), ISR_Z_encoder_B, CHANGE);

  X_pos = 0;
  Y_pos = 0;
  Z_pos = 0;

  // limit switch
  attachInterrupt(digitalPinToInterrupt(X_LIM), ISR_limit_switch_X, FALLING);
  attachInterrupt(digitalPinToInterrupt(Y_LIM), ISR_limit_switch_Y, FALLING);
  attachInterrupt(digitalPinToInterrupt(Z_LIM), ISR_limit_switch_Z, FALLING);

  // focus
  pinMode(focusWheel_A,INPUT_PULLUP);
  pinMode(focusWheel_B,INPUT_PULLUP);
  pinMode(focusWheel_IDX,INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(focusWheel_A), ISR_focusWheel_A, RISING);
  attachInterrupt(digitalPinToInterrupt(focusWheel_B), ISR_focusWheel_B, RISING);
  
  // joystick
  analogReadResolution(10);
  joystick_offset_x = analogRead(joystick_X);
  joystick_offset_y = analogRead(joystick_Y);
  if(joystick_offset_x<400 && joystick_offset_y<400)
    joystick_not_connected = true;

  // joystick button
  pinMode(joystick_button,INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(joystick_button), ISR_joystick_button_pressed, RISING);

  Timer3.attachInterrupt(timer_interruptHandler);
  Timer3.start(TIMER_PERIOD); 

  //ADC
  //ads1115.begin();

  // led matrix
  matrix.begin();
  
}

/***************************************************************************************************/
/********************************************** loop ***********************************************/
/***************************************************************************************************/

void loop() {

  // read one meesage from the buffer
  while (SerialUSB.available()) 
  { 
    buffer_rx[buffer_rx_ptr] = SerialUSB.read();
    buffer_rx_ptr = buffer_rx_ptr + 1;
    if (buffer_rx_ptr == CMD_LENGTH) 
    {
      buffer_rx_ptr = 0;
      cmd_id = buffer_rx[0];
      switch(buffer_rx[1])
      {
        case MOVE_X:
        {
          long relative_position = int32_t(uint32_t(buffer_rx[2])*16777216 + uint32_t(buffer_rx[3])*65536 + uint32_t(buffer_rx[4])*256 + uint32_t(buffer_rx[5]));
          X_commanded_target_position = ( relative_position>0?min(stepper_X.currentPosition()+relative_position,X_POS_LIMIT_MM*steps_per_mm_X):max(stepper_X.currentPosition()+relative_position,X_NEG_LIMIT_MM*steps_per_mm_X) );
          stepper_X.moveTo(X_commanded_target_position);
          X_commanded_movement_in_progress = true;
          runSpeed_flag_X = false;
          mcu_cmd_execution_in_progress = true;
          break;
        }
        case MOVE_Y:
        {
          long relative_position = int32_t(uint32_t(buffer_rx[2])*16777216 + uint32_t(buffer_rx[3])*65536 + uint32_t(buffer_rx[4])*256 + uint32_t(buffer_rx[5]));
          Y_commanded_target_position = ( relative_position>0?min(stepper_Y.currentPosition()+relative_position,Y_POS_LIMIT_MM*steps_per_mm_Y):max(stepper_Y.currentPosition()+relative_position,Y_NEG_LIMIT_MM*steps_per_mm_Y) );
          stepper_Y.moveTo(Y_commanded_target_position);
          Y_commanded_movement_in_progress = true;
          runSpeed_flag_Y = false;
          mcu_cmd_execution_in_progress = true;
          break;
        }
        case MOVE_Z:
        {
          long relative_position = int32_t(uint32_t(buffer_rx[2])*16777216 + uint32_t(buffer_rx[3])*65536 + uint32_t(buffer_rx[4])*256 + uint32_t(buffer_rx[5]));
          Z_commanded_target_position = ( relative_position>0?min(stepper_Z.currentPosition()+relative_position,Z_POS_LIMIT_MM*steps_per_mm_Z):max(stepper_Z.currentPosition()+relative_position,Z_NEG_LIMIT_MM*steps_per_mm_Z) );
          /*
          // mcu_cmd_execution_in_progress = true; // because runToNewPosition is blocking, changing this flag is not needed
          stepper_Z.runToNewPosition(Z_commanded_target_position);
          focusPosition = Z_commanded_target_position;
          //stepper_Z.moveTo(Z_commanded_target_position);
          Z_commanded_movement_in_progress = false;
          // mcu_cmd_execution_in_progress = false; // because runToNewPosition is blocking, changing this flag is not needed
          */
          focusPosition = Z_commanded_target_position;
          stepper_Z.moveTo(Z_commanded_target_position);
          Z_commanded_movement_in_progress = true;
          runSpeed_flag_Z = false;
          mcu_cmd_execution_in_progress = true;
          break;
        }
        case MOVETO_X:
        {
          long absolute_position = int32_t(uint32_t(buffer_rx[2])*16777216 + uint32_t(buffer_rx[3])*65536 + uint32_t(buffer_rx[4])*256 + uint32_t(buffer_rx[5]));
          X_commanded_target_position = absolute_position;
          stepper_X.moveTo(absolute_position);
          X_commanded_movement_in_progress = true;
          runSpeed_flag_X = false;
          mcu_cmd_execution_in_progress = true;
          break;
        }
        case MOVETO_Y:
        {
          long absolute_position = int32_t(uint32_t(buffer_rx[2])*16777216 + uint32_t(buffer_rx[3])*65536 + uint32_t(buffer_rx[4])*256 + uint32_t(buffer_rx[5]));
          Y_commanded_target_position = absolute_position;
          stepper_Y.moveTo(absolute_position);
          Y_commanded_movement_in_progress = true;
          runSpeed_flag_Y = false;
          mcu_cmd_execution_in_progress = true;
          break;
        }
        case MOVETO_Z:
        {
          long absolute_position = int32_t(uint32_t(buffer_rx[2])*16777216 + uint32_t(buffer_rx[3])*65536 + uint32_t(buffer_rx[4])*256 + uint32_t(buffer_rx[5]));
          // mcu_cmd_execution_in_progress = true; // because runToNewPosition is blocking, changing this flag is not needed
          Z_commanded_target_position = absolute_position;
          stepper_Z.moveTo(absolute_position);
          focusPosition = absolute_position;
          Z_commanded_movement_in_progress = true;
          runSpeed_flag_Z = false;
          mcu_cmd_execution_in_progress = true;
          break;
        }
        case HOME_OR_ZERO:
        {
          // zeroing
          if(buffer_rx[3]==HOME_OR_ZERO_ZERO)
          {
            switch(buffer_rx[2])
            {
              case AXIS_X:
                stepper_X.setCurrentPosition(0);
                X_pos = 0;
                break;
              case AXIS_Y:
                stepper_Y.setCurrentPosition(0);
                Y_pos = 0;
                break;
              case AXIS_Z:
                stepper_Z.setCurrentPosition(0);
                Z_pos = 0;
                focusPosition = 0;
                break;
            }
            // atomic operation, no need to change mcu_cmd_execution_in_progress flag
          }
          // homing
          else if(buffer_rx[3]==HOME_NEGATIVE || buffer_rx[3]==HOME_POSITIVE)
          {
            switch(buffer_rx[2])
            {
              case AXIS_X:
                homing_direction_X = buffer_rx[3];
                home_X_found = false;
                if(digitalRead(X_LIM)==HIGH)
                {
                  is_homing_X = true;
                  runSpeed_flag_X = true;
                  if(homing_direction_X==HOME_NEGATIVE)
                    stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                  else
                    stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                }
                else
                {
                  // get out of the hysteresis zone
                  is_preparing_for_homing_X = true;
                  runSpeed_flag_X = true;
                  if(homing_direction_X==HOME_NEGATIVE)
                    stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                  else
                    stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                }
                break;
              case AXIS_Y:
                homing_direction_Y = buffer_rx[3];
                home_Y_found = false;
                if(digitalRead(Y_LIM)==HIGH)
                {
                  is_homing_Y = true;
                  runSpeed_flag_Y = true;
                  if(homing_direction_Y==HOME_NEGATIVE)
                    stepper_Y.setSpeed(-HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                  else
                    stepper_Y.setSpeed(HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                }
                else
                {
                  // get out of the hysteresis zone
                  is_preparing_for_homing_Y = true;
                  runSpeed_flag_Y = true;
                  if(homing_direction_Y==HOME_NEGATIVE)
                    stepper_Y.setSpeed(HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                  else
                    stepper_Y.setSpeed(-HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                }
                break;
              case AXIS_Z:
                homing_direction_Z = buffer_rx[3];
                home_Z_found = false;
                if(digitalRead(Z_LIM)==HIGH)
                {
                  is_homing_Z = true;
                  runSpeed_flag_Z = true;
                  if(homing_direction_Z==HOME_NEGATIVE)
                    stepper_Z.setSpeed(-HOMING_VELOCITY_Z*MAX_VELOCITY_Z_mm*steps_per_mm_Z);
                  else
                    stepper_Z.setSpeed(HOMING_VELOCITY_Z*MAX_VELOCITY_Z_mm*steps_per_mm_Z);
                }
                else
                {
                  // get out of the hysteresis zone
                  is_preparing_for_homing_Z = true;
                  runSpeed_flag_Z = true;
                  if(homing_direction_Z==HOME_NEGATIVE)
                    stepper_Z.setSpeed(HOMING_VELOCITY_Z*MAX_VELOCITY_Z_mm*steps_per_mm_Z);
                  else
                    stepper_Z.setSpeed(-HOMING_VELOCITY_Z*MAX_VELOCITY_Z_mm*steps_per_mm_Z);
                }
                break;
              case AXES_XY:
                is_homing_XY = true;
                home_X_found = false;
                home_Y_found = false;
                // homing x 
                homing_direction_X = buffer_rx[3];
                if(digitalRead(X_LIM)==HIGH)
                {
                  is_homing_X = true;
                  runSpeed_flag_X = true;
                  if(homing_direction_X==HOME_NEGATIVE)
                    stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                  else
                    stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                }
                else
                {
                  // get out of the hysteresis zone
                  is_preparing_for_homing_X = true;
                  runSpeed_flag_X = true;
                  if(homing_direction_X==HOME_NEGATIVE)
                    stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                  else
                    stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                }
                // homing y
                homing_direction_Y = buffer_rx[4];
                if(digitalRead(Y_LIM)==HIGH)
                {
                  is_homing_Y = true;
                  runSpeed_flag_Y = true;
                  if(homing_direction_Y==HOME_NEGATIVE)
                    stepper_Y.setSpeed(-HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                  else
                    stepper_Y.setSpeed(HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                }
                else
                {
                  // get out of the hysteresis zone
                  is_preparing_for_homing_Y = true;
                  runSpeed_flag_Y = true;
                  if(homing_direction_Y==HOME_NEGATIVE)
                    stepper_Y.setSpeed(HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                  else
                    stepper_Y.setSpeed(-HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
                }
                break;
            }
            mcu_cmd_execution_in_progress = true;
          }
          break;
        }
        case TURN_ON_ILLUMINATION:
        {
          // mcu_cmd_execution_in_progress = true;
          turn_on_illumination();
          // mcu_cmd_execution_in_progress = false;
          // these are atomic operations - do not change the mcu_cmd_execution_in_progress flag
          break;
        }
        case TURN_OFF_ILLUMINATION:
        {
          turn_off_illumination();
          break;
        }
        case SET_ILLUMINATION:
        {
          set_illumination(buffer_rx[2],(uint16_t(buffer_rx[2])<<8) + uint16_t(buffer_rx[3])); //important to have "<<8" with in "()"
          break;
        }
        case SET_ILLUMINATION_LED_MATRIX:
        {
          set_illumination_led_matrix(buffer_rx[2],buffer_rx[3],buffer_rx[4],buffer_rx[5]);
          break;
        }
        case ACK_JOYSTICK_BUTTON_PRESSED:
        {
          joystick_button_pressed = false;
          break;
        }
        default:
          break;
      }
      //break; // exit the while loop after reading one message
    }
  }

  // homing - preparing for homing
  if(is_preparing_for_homing_X)
  {
    if(digitalRead(X_LIM)==HIGH)
    {
      is_preparing_for_homing_X = false;
      is_homing_X = true;
      runSpeed_flag_X = true;
      if(homing_direction_X==HOME_NEGATIVE)
        stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
      else
        stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
    }
  }
  if(is_preparing_for_homing_Y)
  {
    if(digitalRead(Y_LIM)==HIGH)
    {
      is_preparing_for_homing_Y = false;
      is_homing_Y = true;
      runSpeed_flag_Y = true;
      if(homing_direction_Y==HOME_NEGATIVE)
        stepper_Y.setSpeed(-HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
      else
        stepper_Y.setSpeed(HOMING_VELOCITY_Y*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
    }
  }
  if(is_preparing_for_homing_Z)
  {
    if(digitalRead(Z_LIM)==HIGH)
    {
      is_preparing_for_homing_Z = false;
      is_homing_Z = true;
      runSpeed_flag_Z = true;
      if(homing_direction_Z==HOME_NEGATIVE)
        stepper_Z.setSpeed(-HOMING_VELOCITY_Z*MAX_VELOCITY_X_mm*steps_per_mm_Z);
      else
        stepper_Z.setSpeed(HOMING_VELOCITY_Z*MAX_VELOCITY_X_mm*steps_per_mm_Z);
    }
  }
  
  // homing - software limit reached
  if(is_homing_X || is_preparing_for_homing_X)
  {
    if(stepper_X.currentPosition()<=X_NEG_LIMIT_MM*steps_per_mm_X || stepper_X.currentPosition()>=X_POS_LIMIT_MM*steps_per_mm_X)
    {
      stepper_X.setSpeed(0);
      runSpeed_flag_X = false;
      is_preparing_for_homing_X = false;
      is_homing_X = false;
      mcu_cmd_execution_in_progress = false; // to do: return an error: mcu_cmd_execution_in_progress = 2 [first change the variable type from int to uint8]
    }
  }
  if(is_homing_Y || is_preparing_for_homing_Y)
  {
    if(stepper_Y.currentPosition()<=Y_NEG_LIMIT_MM*steps_per_mm_Y || stepper_Y.currentPosition()>=Y_POS_LIMIT_MM*steps_per_mm_Y)
    {
      stepper_Y.setSpeed(0);
      runSpeed_flag_Y = false;
      is_preparing_for_homing_Y = false;
      is_homing_Y = false;
      mcu_cmd_execution_in_progress = false; // to do: return an error: mcu_cmd_execution_in_progress = 2 [first change the variable type from int to uint8]
    }
  }
  if(is_homing_Z || is_preparing_for_homing_Z)
  {
    if(stepper_Z.currentPosition()<=Z_NEG_LIMIT_MM*steps_per_mm_Z || stepper_Z.currentPosition()>=Z_POS_LIMIT_MM*steps_per_mm_Z)
    {
      stepper_Z.setSpeed(0);
      runSpeed_flag_Z = false;
      is_preparing_for_homing_Z = false;
      is_homing_Z = false;
      mcu_cmd_execution_in_progress = false; // to do: return an error: mcu_cmd_execution_in_progress = 2 [first change the variable type from int to uint8]
    }
  }

  // finish homing
  if(is_homing_X && home_X_found && stepper_X.distanceToGo() == 0)
  {
    stepper_X.setCurrentPosition(0);
    X_pos = 0;
    is_homing_X = false;
    X_commanded_movement_in_progress = false;
    if(is_homing_XY==false)
      mcu_cmd_execution_in_progress = false;
  }
  if(is_homing_Y && home_Y_found && stepper_Y.distanceToGo() == 0)
  {
    stepper_Y.setCurrentPosition(0);
    Y_pos = 0;
    is_homing_Y = false;
    Y_commanded_movement_in_progress = false;
    if(is_homing_XY==false)
      mcu_cmd_execution_in_progress = false;
  }
  if(is_homing_Z && home_Z_found && stepper_Z.distanceToGo() == 0)
  {
    stepper_Z.setCurrentPosition(0);
    Z_pos = 0;
    is_homing_Z = false;
    Z_commanded_movement_in_progress = false;
    mcu_cmd_execution_in_progress = false;
  }

  // homing complete
  if(is_homing_XY && home_X_found && !is_homing_X && home_Y_found && !is_homing_Y)
  {
    is_homing_XY = false;
    mcu_cmd_execution_in_progress = false;
  }
  
  // handle control panel input
  if(flag_read_joystick && joystick_not_connected == false) 
  {
    // read rocker state (may be moved)
    rocker_state = digitalRead(rocker);
    
    // read speed_XY_factor (range 0-1)
    speed_XY_factor = float(analogRead(analog_in_1))/1023;
    // speed_XY_factor = rocker_state ? speed_XY_factor : 0; // for testing the rocker
    
    // read x joystick
    if(!X_commanded_movement_in_progress && !is_homing_X && !is_preparing_for_homing_X) //if(stepper_X.distanceToGo()==0) // only read joystick when computer commanded travel has finished - doens't work
    {
      deltaX = analogRead(joystick_X) - joystick_offset_x;
      deltaX_float = deltaX;
      if(abs(deltaX_float)>joystickSensitivity)
      {
        stepper_X.setSpeed(sgn(deltaX_float)*((abs(deltaX_float)-joystickSensitivity)/512.0)*speed_XY_factor*MAX_VELOCITY_X_mm*steps_per_mm_X);
        runSpeed_flag_X = true;
        if(stepper_X.currentPosition()>=X_POS_LIMIT_MM*steps_per_mm_X && deltaX_float>0)
        {
          runSpeed_flag_X = false;
          stepper_X.setSpeed(0);
        }
        if(stepper_X.currentPosition()<=X_NEG_LIMIT_MM*steps_per_mm_X && deltaX_float<0)
          {
          runSpeed_flag_X = false;
          stepper_X.setSpeed(0);
        }
      }
      else
      {
        runSpeed_flag_X = false;
        stepper_X.setSpeed(0);
      }
    }

    // read y joystick
    if(!Y_commanded_movement_in_progress && !is_homing_Y && !is_preparing_for_homing_Y)
    {
      deltaY = analogRead(joystick_Y) - joystick_offset_y;
      deltaY_float = -deltaY;
      if(abs(deltaY)>joystickSensitivity)
      {
        stepper_Y.setSpeed(sgn(deltaY_float)*((abs(deltaY_float)-joystickSensitivity)/512.0)*speed_XY_factor*MAX_VELOCITY_Y_mm*steps_per_mm_Y);
        runSpeed_flag_Y = true;
        if(stepper_Y.currentPosition()>=Y_POS_LIMIT_MM*steps_per_mm_Y && deltaY_float>0)
        {
          runSpeed_flag_Y = false;
          stepper_Y.setSpeed(0);
        }
        if(stepper_Y.currentPosition()<=Y_NEG_LIMIT_MM*steps_per_mm_Y && deltaY_float<0)
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
    flag_read_joystick = false;
  }
  
  // focus control
  stepper_Z.moveTo(focusPosition);

  // send position update to computer
  if(flag_send_pos_update)
  {

    buffer_tx[0] = cmd_id;
    buffer_tx[1] = mcu_cmd_execution_in_progress; // cmd_execution_status
    
    uint32_t X_pos_int32t = uint32_t( X_use_encoder?X_pos:int32_t(stepper_X.currentPosition()) );
    buffer_tx[2] = byte(X_pos_int32t>>24);
    buffer_tx[3] = byte((X_pos_int32t>>16)%256);
    buffer_tx[4] = byte((X_pos_int32t>>8)%256);
    buffer_tx[5] = byte((X_pos_int32t)%256);
    
    uint32_t Y_pos_int32t = uint32_t( Y_use_encoder?Y_pos:int32_t(stepper_Y.currentPosition()) );
    buffer_tx[6] = byte(Y_pos_int32t>>24);
    buffer_tx[7] = byte((Y_pos_int32t>>16)%256);
    buffer_tx[8] = byte((Y_pos_int32t>>8)%256);
    buffer_tx[9] = byte((Y_pos_int32t)%256);

    uint32_t Z_pos_int32t = uint32_t( Z_use_encoder?Z_pos:int32_t(stepper_Z.currentPosition()) );
    buffer_tx[10] = byte(Z_pos_int32t>>24);
    buffer_tx[11] = byte((Z_pos_int32t>>16)%256);
    buffer_tx[12] = byte((Z_pos_int32t>>8)%256);
    buffer_tx[13] = byte((Z_pos_int32t)%256);

    // fail-safe clearing of the joystick_button_pressed bit (in case the ack is not received)
    if(joystick_button_pressed && millis() - joystick_button_pressed_timestamp > 1000)
      joystick_button_pressed = false;

    buffer_tx[18] &= ~ (1 << BIT_POS_JOYSTICK_BUTTON); // clear the joystick button bit
    buffer_tx[18] = buffer_tx[18] | joystick_button_pressed << BIT_POS_JOYSTICK_BUTTON;
    
    SerialUSB.write(buffer_tx,MSG_LENGTH);
    flag_send_pos_update = false;
    
  }

  // encoded movement
  if(X_use_encoder && closed_loop_position_control)
    stepper_X.setCurrentPosition(X_pos);
  if(Y_use_encoder && closed_loop_position_control)
    stepper_Y.setCurrentPosition(Y_pos);
  if(Z_use_encoder && closed_loop_position_control)
    stepper_Z.setCurrentPosition(Z_pos);

  // check if commanded position has been reached
  if(X_commanded_movement_in_progress && stepper_X.currentPosition()==X_commanded_target_position && !is_homing_X) // homing is handled separately
  {
    X_commanded_movement_in_progress = false;
    mcu_cmd_execution_in_progress = false || Y_commanded_movement_in_progress || Z_commanded_movement_in_progress;
  }
  if(Y_commanded_movement_in_progress && stepper_Y.currentPosition()==Y_commanded_target_position && !is_homing_Y)
  {
    Y_commanded_movement_in_progress = false;
    mcu_cmd_execution_in_progress = false || X_commanded_movement_in_progress || Z_commanded_movement_in_progress;
  }
  if(Z_commanded_movement_in_progress && stepper_Z.currentPosition()==Z_commanded_target_position && !is_homing_Z)
  {
    Z_commanded_movement_in_progress = false;
    mcu_cmd_execution_in_progress = false || X_commanded_movement_in_progress || Y_commanded_movement_in_progress;
  }
    
  // move motors
  if(X_commanded_movement_in_progress)
    stepper_X.run();
  else if(runSpeed_flag_X)
    stepper_X.runSpeed();
    
  if(Y_commanded_movement_in_progress)
    stepper_Y.run();
  else if(runSpeed_flag_Y)
    stepper_Y.runSpeed();

  stepper_Z.run();
}

/***************************************************
 *  
 *                  timer interrupt 
 *  
 ***************************************************/
 
// timer interrupt
void timer_interruptHandler(){
  counter_read_joystick = counter_read_joystick + 1;
  if(counter_read_joystick==interval_read_joystick/TIMER_PERIOD)
  {
    if(ENABLE_JOYSTICK)
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

/***************************************************
 *  
 *                     limit switch 
 *  
 ***************************************************/
 void ISR_limit_switch_X()
 {
  if(is_homing_X)
  {
    home_X_found = true;
    long home_X_pos = stepper_X.currentPosition(); // to add: case for using encoders
    runSpeed_flag_X = false;
    stepper_X.moveTo(home_X_pos); // move to the home position
    X_commanded_movement_in_progress = true;
    X_commanded_target_position = home_X_pos;
  }
 }

 void ISR_limit_switch_Y()
 {
  if(is_homing_Y)
  {
    home_Y_found = true;
    long home_Y_pos = stepper_Y.currentPosition();
    runSpeed_flag_Y = false;
    stepper_Y.moveTo(home_Y_pos); // move to the home position
    Y_commanded_movement_in_progress = true;
    Y_commanded_target_position = home_Y_pos;
  }
 }

  void ISR_limit_switch_Z()
 {
  if(is_homing_Z)
  {
    home_Z_found = true;
    long home_Z_pos = stepper_Z.currentPosition();
    runSpeed_flag_Z = false;
    stepper_Z.moveTo(home_Z_pos); // move tY_commanded_movement_in_progress = true;
    Z_commanded_movement_in_progress = true;
    Z_commanded_target_position = home_Z_pos;
  }
 }
/***************************************************
 *  
 *                        encoder 
 *  
 ***************************************************/
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

void ISR_X_encoder_A(){
  if(digitalRead(X_encoder_B)==0 && digitalRead(X_encoder_A)==1)
    X_pos = X_pos + 1;
  else if (digitalRead(X_encoder_B)==1 && digitalRead(X_encoder_A)==0)
    X_pos = X_pos + 1;
  else
    X_pos = X_pos - 1;
}
void ISR_X_encoder_B(){
  if(digitalRead(X_encoder_B)==0 && digitalRead(X_encoder_A)==1 )
    X_pos = X_pos - 1;
  else if (digitalRead(X_encoder_B)==1 && digitalRead(X_encoder_A)==0)
    X_pos = X_pos - 1;
  else
    X_pos = X_pos + 1;
}

void ISR_Y_encoder_A(){
  if(digitalRead(Y_encoder_B)==0 && digitalRead(Y_encoder_A)==1)
    Y_pos = Y_pos + 1;
  else if (digitalRead(Y_encoder_B)==1 && digitalRead(Y_encoder_A)==0)
    Y_pos = Y_pos + 1;
  else
    Y_pos = Y_pos - 1;
}
void ISR_Y_encoder_B(){
  if(digitalRead(Y_encoder_B)==0 && digitalRead(Y_encoder_A)==1 )
    Y_pos = Y_pos - 1;
  else if (digitalRead(Y_encoder_B)==1 && digitalRead(Y_encoder_A)==0)
    Y_pos = Y_pos - 1;
  else
    Y_pos = Y_pos + 1;
}

void ISR_Z_encoder_A(){
  if(digitalRead(Z_encoder_B)==0 && digitalRead(Z_encoder_A)==1 )
    Z_pos = Z_pos + 1;
  else if (digitalRead(Z_encoder_B)==1 && digitalRead(Z_encoder_A)==0)
    Z_pos = Z_pos + 1;
  else
    Z_pos = Z_pos - 1;
}
void ISR_Z_encoder_B(){
  if(digitalRead(Z_encoder_B)==0 && digitalRead(Z_encoder_A)==1 )
    Z_pos = Z_pos - 1;
  else if (digitalRead(Z_encoder_B)==1 && digitalRead(Z_encoder_A)==0)
    Z_pos = Z_pos - 1;
  else
    Z_pos = Z_pos + 1;
}

/***************************************************
 *  
 *              joy stick button pressed 
 *  
 ***************************************************/
void ISR_joystick_button_pressed()
{
  joystick_button_pressed = true;
  joystick_button_pressed_timestamp = millis();
}

/***************************************************************************************************/
/*********************************************  utils  *********************************************/
/***************************************************************************************************/
long signed2NBytesUnsigned(long signedLong,int N)
{
  long NBytesUnsigned = signedLong + pow(256L,N)/2;
  //long NBytesUnsigned = signedLong + 8388608L;
  return NBytesUnsigned;
}

static inline int sgn(int val) {
 if (val < 0) return -1;
 if (val==0) return 0;
 return 1;
}

/***************************************************************************************************/
/*******************************************  LED Array  *******************************************/
/***************************************************************************************************/
void set_all(Adafruit_DotStar & matrix, int r, int g, int b)
{
  for (int i = 0; i < DOTSTAR_NUM_LEDS; i++)
    matrix.setPixelColor(i,r,g,b);
}

void set_left(Adafruit_DotStar & matrix, int r, int g, int b)
{
  for (int i = 0; i < DOTSTAR_NUM_LEDS/2; i++)
    matrix.setPixelColor(i,r,g,b);
}

void set_right(Adafruit_DotStar & matrix, int r, int g, int b)
{
  for (int i = DOTSTAR_NUM_LEDS/2; i < DOTSTAR_NUM_LEDS; i++)
    matrix.setPixelColor(i,r,g,b);
}

void clear_matrix(Adafruit_DotStar & matrix)
{
  for (int i = 0; i < DOTSTAR_NUM_LEDS; i++)
    matrix.setPixelColor(i,0,0,0);
  matrix.show();
}

void turn_on_LED_matrix_pattern(Adafruit_DotStar & matrix, int pattern, uint8_t led_matrix_r, uint8_t led_matrix_g, uint8_t led_matrix_b)
{

  led_matrix_r = (float(led_matrix_r)/255)*LED_MATRIX_MAX_INTENSITY;
  led_matrix_g = (float(led_matrix_g)/255)*LED_MATRIX_MAX_INTENSITY;
  led_matrix_b = (float(led_matrix_b)/255)*LED_MATRIX_MAX_INTENSITY;

  // clear matrix
  set_all(matrix, 0, 0, 0);
    
  switch(pattern)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      set_all(matrix, led_matrix_g*GREEN_ADJUSTMENT_FACTOR, led_matrix_b*BLUE_ADJUSTMENT_FACTOR, led_matrix_r*RED_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      set_left(matrix, led_matrix_g*GREEN_ADJUSTMENT_FACTOR, led_matrix_b*BLUE_ADJUSTMENT_FACTOR, led_matrix_r*RED_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      set_right(matrix, led_matrix_g*GREEN_ADJUSTMENT_FACTOR, led_matrix_b*BLUE_ADJUSTMENT_FACTOR, led_matrix_r*RED_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      set_left(matrix,0,led_matrix_b*BLUE_ADJUSTMENT_FACTOR,0);
      set_right(matrix,0,0,led_matrix_r*RED_ADJUSTMENT_FACTOR);
  }
  matrix.show();
}
