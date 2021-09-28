#include <TMCStepper.h>
#include <TMCStepper_UTILITY.h>
#include <DueTimer.h>
#include <AccelStepper.h>
#include <Adafruit_DotStar.h>
#include <SPI.h>

/***************************************************************************************************/
/***************************************** Communications ******************************************/
/***************************************************************************************************/

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

// command sets
static const int MOVE_X = 0;
static const int MOVE_Y = 1;
static const int MOVE_Z = 2;
static const int TURN_ON_ILLUMINATION = 5;
static const int TURN_OFF_ILLUMINATION = 6;
static const int SET_ILLUMINATION = 7;

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
static const int X_encoder_A = 2;
static const int X_encoder_B = 3;
static const int X_LIM = 4;
static const int Y_encoder_A = 5;
static const int Y_encoder_B = 6;
static const int Y_LIM = 7;
static const int Z_encoder_A = 8;
static const int Z_encoder_B = 9;

// focus wheel
static const int focusWheel_A  = 41;
static const int focusWheel_B  = 42;
static const int focusWheel_IDX  = 43;
volatile long focusPosition = 0;

// analog input
#define analog_in_0 A7
#define analog_in_1 A8

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
static const long steps_per_mm_XY = 1600;
static const long steps_per_mm_Z = 5333;
//constexpr float MAX_VELOCITY_X_mm = 7;
//constexpr float MAX_VELOCITY_Y_mm = 7;
constexpr float MAX_VELOCITY_X_mm = 20;
constexpr float MAX_VELOCITY_Y_mm = 20;
constexpr float MAX_VELOCITY_Z_mm = 2;
constexpr float MAX_ACCELERATION_X_mm = 200;  // 50 mm/s/s
constexpr float MAX_ACCELERATION_Y_mm = 200;  // 50 mm/s/s
constexpr float MAX_ACCELERATION_Z_mm = 20;   // 20 mm/s/s
static const long X_NEG_LIMIT_MM = -12;
static const long X_POS_LIMIT_MM = 12;
static const long Y_NEG_LIMIT_MM = -12;
static const long Y_POS_LIMIT_MM = 12;
static const long Z_NEG_LIMIT_MM = -5;
static const long Z_POS_LIMIT_MM = 5;

bool runSpeed_flag_X = false;
bool runSpeed_flag_Y = false;
bool runSpeed_flag_Z = false;
long X_commanded_target_position = 0;
long Y_commanded_target_position = 0;
long Z_commanded_target_position = 0;
bool X_commanded_movement_in_progress = false;
bool Y_commanded_movement_in_progress = false;
bool Z_commanded_movement_in_progress = false;

long target_position;

volatile long X_pos = 0;
volatile long Y_pos = 0;
volatile long Z_pos = 0;

// encoder
bool X_use_encoder = false;
bool Y_use_encoder = false;
bool Z_use_encoder = false;

/***************************************************************************************************/
/******************************************* joystick **********************************************/
/***************************************************************************************************/
static const int TIMER_PERIOD = 500; // in us
static const int interval_read_joystick = 10000; // in us
static const int interval_send_pos_update = 50000; // in us
volatile int counter_read_joystick = 0;
volatile int counter_send_pos_update = 0;
volatile bool flag_read_joystick = false;
volatile bool flag_send_pos_update = false;
int joystick_offset_x = 512;
int joystick_offset_y = 512;
constexpr int joystickSensitivity = 50; // for comparison with number in the range of 0-512

// joystick
int deltaX = 0;
int deltaY = 0;
float deltaX_float = 0;
float deltaY_float = 0;
float speed_XY_factor = 0;

// rocker
bool rocker_state = false;

/***************************************************************************************************/
/***************************************** illumination ********************************************/
/***************************************************************************************************/
int illumination_source = 0;
uint16_t illumination_intensity = 65535;
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

Adafruit_DotStar matrix(64, DOTSTAR_BRG);
void set_all(Adafruit_DotStar & matrix, int r, int g, int b);
void set_left(Adafruit_DotStar & matrix, int r, int g, int b);
void set_right(Adafruit_DotStar & matrix, int r, int g, int b);
void clear_matrix(Adafruit_DotStar & matrix);
void turn_on_LED_matrix_pattern(Adafruit_DotStar & matrix, int pattern, uint16_t intensity);

void turn_on_illumination()
{
  illumination_is_on = true;
  switch(illumination_source)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF,illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF,illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR,illumination_intensity);
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


/***************************************************************************************************/
/********************************************* setup ***********************************************/
/***************************************************************************************************/

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
  
  stepper_X.setMaxSpeed(MAX_VELOCITY_X_mm*steps_per_mm_XY);
  stepper_Y.setMaxSpeed(MAX_VELOCITY_Y_mm*steps_per_mm_XY);
  stepper_Z.setMaxSpeed(MAX_VELOCITY_Z_mm*steps_per_mm_Z);
  
  stepper_X.setAcceleration(MAX_ACCELERATION_X_mm*steps_per_mm_XY);
  stepper_Y.setAcceleration(MAX_ACCELERATION_Y_mm*steps_per_mm_XY);
  stepper_Z.setAcceleration(MAX_ACCELERATION_Z_mm*steps_per_mm_Z);

  stepper_X.enableOutputs();
  stepper_Y.enableOutputs();
  stepper_Z.enableOutputs();

  // xyz encoder
  pinMode(X_encoder_A,INPUT);
  pinMode(X_encoder_B,INPUT);
  pinMode(Y_encoder_A,INPUT);
  pinMode(Y_encoder_B,INPUT);
  pinMode(Z_encoder_A,INPUT);
  pinMode(Z_encoder_B,INPUT);
  attachInterrupt(digitalPinToInterrupt(X_encoder_A), ISR_X_encoder_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(X_encoder_B), ISR_X_encoder_B, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Y_encoder_A), ISR_Y_encoder_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Y_encoder_B), ISR_Y_encoder_B, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Z_encoder_A), ISR_Z_encoder_A, CHANGE);
  attachInterrupt(digitalPinToInterrupt(Z_encoder_B), ISR_Z_encoder_B, CHANGE);

  X_pos = 0;
  Y_pos = 0;
  Z_pos = 0;

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
  while (SerialUSB.available()) { 
    buffer_rx[buffer_rx_ptr] = SerialUSB.read();
    buffer_rx_ptr = buffer_rx_ptr + 1;
    if (buffer_rx_ptr == CMD_LENGTH) {
      buffer_rx_ptr = 0;
      switch(buffer_rx[0])
      {
        case MOVE_X:
        {
          long relative_position = long(buffer_rx[1]*2-1)*(long(buffer_rx[2])*256 + long(buffer_rx[3]));
          X_commanded_target_position = ( relative_position>0?min(stepper_X.currentPosition()+relative_position,X_POS_LIMIT_MM*steps_per_mm_XY):max(stepper_X.currentPosition()+relative_position,X_NEG_LIMIT_MM*steps_per_mm_XY) );
          stepper_X.moveTo(X_commanded_target_position);
          X_commanded_movement_in_progress = true;
          break;
        }
        case MOVE_Y:
        {
          long relative_position = long(buffer_rx[1]*2-1)*(long(buffer_rx[2])*256 + long(buffer_rx[3]));
          Y_commanded_target_position = ( relative_position>0?min(stepper_Y.currentPosition()+relative_position,Y_POS_LIMIT_MM*steps_per_mm_XY):max(stepper_Y.currentPosition()+relative_position,Y_NEG_LIMIT_MM*steps_per_mm_XY) );
          stepper_Y.moveTo(Y_commanded_target_position);
          Y_commanded_movement_in_progress = true;
          break;
        }
        case MOVE_Z:
        {
          long relative_position = long(buffer_rx[1]*2-1)*(long(buffer_rx[2])*256 + long(buffer_rx[3]));
          Z_commanded_target_position = ( relative_position>0?min(stepper_Z.currentPosition()+relative_position,Z_POS_LIMIT_MM*steps_per_mm_Z):max(stepper_Z.currentPosition()+relative_position,Z_NEG_LIMIT_MM*steps_per_mm_Z) );
          stepper_Z.runToNewPosition(Z_commanded_target_position);
          focusPosition = Z_commanded_target_position;
          //stepper_Z.moveTo(Z_commanded_target_position);
          Z_commanded_movement_in_progress = true;
          break;
        }
        case TURN_ON_ILLUMINATION:
        {
          turn_on_illumination();
          break;
        }
        case TURN_OFF_ILLUMINATION:
        {
          turn_off_illumination();
          break;
        }
        case SET_ILLUMINATION:
        {
          set_illumination(buffer_rx[1],(uint16_t(buffer_rx[2])<<8) + uint16_t(buffer_rx[3])); //important to have "<<8" with in "()"
          break;
        }
        default:
          break;
      }
      //break; // exit the while loop after reading one message
    }
  }

  if(flag_read_joystick) 
  {
    // read rocker state (may be moved)
    rocker_state = digitalRead(rocker);
    
    // read speed_XY_factor (range 0-1)
    speed_XY_factor = float(analogRead(analog_in_1))/1023;
    // speed_XY_factor = rocker_state ? speed_XY_factor : 0; // for testing the rocker
    
    // read x joystick
    if(!X_commanded_movement_in_progress) //if(stepper_X.distanceToGo()==0) // only read joystick when computer commanded travel has finished - doens't work
    {
      deltaX = analogRead(joystick_X) - joystick_offset_x;
      deltaX_float = -deltaX;
      if(abs(deltaX_float)>joystickSensitivity)
      {
        stepper_X.setSpeed(sgn(deltaX_float)*((abs(deltaX_float)-joystickSensitivity)/512.0)*speed_XY_factor*MAX_VELOCITY_X_mm*steps_per_mm_XY);
        runSpeed_flag_X = true;
        if(stepper_X.currentPosition()>=X_POS_LIMIT_MM*steps_per_mm_XY && deltaX_float>0)
        {
          runSpeed_flag_X = false;
          stepper_X.setSpeed(0);
        }
        if(stepper_X.currentPosition()<=X_NEG_LIMIT_MM*steps_per_mm_XY && deltaX_float<0)
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
    else
      runSpeed_flag_X = false;

    // read y joystick
    if(!Y_commanded_movement_in_progress)
    {
      deltaY = analogRead(joystick_Y) - joystick_offset_y;
      deltaY_float = -deltaY;
      if(abs(deltaY)>joystickSensitivity)
      {
        stepper_Y.setSpeed(sgn(deltaY_float)*((abs(deltaY_float)-joystickSensitivity)/512.0)*speed_XY_factor*MAX_VELOCITY_Y_mm*steps_per_mm_XY);
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
    long X_pos_NBytesUnsigned = ( X_use_encoder?signed2NBytesUnsigned(X_pos,N_BYTES_POS):signed2NBytesUnsigned(stepper_X.currentPosition(),N_BYTES_POS) );
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
    stepper_X.setCurrentPosition(X_pos);
  if(Y_use_encoder)
    stepper_Y.setCurrentPosition(Y_pos);
  if(Z_use_encoder)
    stepper_Z.setCurrentPosition(Z_pos);

  // check if commanded position has been reached
  if(X_commanded_movement_in_progress && stepper_X.currentPosition()==X_commanded_target_position)
    X_commanded_movement_in_progress = false;
  if(Y_commanded_movement_in_progress && stepper_Y.currentPosition()==Y_commanded_target_position)
    Y_commanded_movement_in_progress = false;
  if(Z_commanded_movement_in_progress && stepper_Z.currentPosition()==Z_commanded_target_position)
    Z_commanded_movement_in_progress = false;

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
  for (int i = 0; i < 64; i++)
    matrix.setPixelColor(i,r,g,b);
}

void set_left(Adafruit_DotStar & matrix, int r, int g, int b)
{
  for (int i = 0; i < 32; i++)
    matrix.setPixelColor(i,r,g,b);
}

void set_right(Adafruit_DotStar & matrix, int r, int g, int b)
{
  for (int i = 32; i < 64; i++)
    matrix.setPixelColor(i,r,g,b);
}

void clear_matrix(Adafruit_DotStar & matrix)
{
  for (int i = 0; i < 64; i++)
    matrix.setPixelColor(i,0,0,0);
  matrix.show();
}

void turn_on_LED_matrix_pattern(Adafruit_DotStar & matrix, int pattern, uint16_t intensity_uint16)
{

  uint8_t intensity = (float(intensity_uint16)/65535)*LED_MATRIX_MAX_INTENSITY;

  // clear matrix
  set_all(matrix, 0, 0, 0);
    
  switch(pattern)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      set_all(matrix, intensity*GREEN_ADJUSTMENT_FACTOR, intensity*BLUE_ADJUSTMENT_FACTOR, intensity*RED_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      set_left(matrix, intensity*GREEN_ADJUSTMENT_FACTOR, intensity*BLUE_ADJUSTMENT_FACTOR, intensity*RED_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      set_right(matrix, intensity*GREEN_ADJUSTMENT_FACTOR, intensity*BLUE_ADJUSTMENT_FACTOR, intensity*RED_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      set_left(matrix,0,intensity*BLUE_ADJUSTMENT_FACTOR,0);
      set_right(matrix,0,0,intensity*RED_ADJUSTMENT_FACTOR);
  }
  matrix.show();
}
