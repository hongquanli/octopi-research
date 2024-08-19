#include <PacketSerial.h>
#include <FastLED.h>
#include <SPI.h>
#include "TMC4361A.h"
#include "TMC4361A_TMC2660_Utils.h"
#include "crc8.h"

//#include "def_octopi.h"
#include "def_octopi_80120.h"
//#include "def_gravitymachine.h"
//#include "def_squid.h"
//#include "def_platereader.h"
//#include "def_squid_vertical.h"

#define N_MOTOR 3

#define DEBUG_MODE false

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
bool checksum_error = false;

// command sets
static const int MOVE_X = 0;
static const int MOVE_Y = 1;
static const int MOVE_Z = 2;
static const int MOVE_THETA = 3;
static const int HOME_OR_ZERO = 5;
static const int MOVETO_X = 6;
static const int MOVETO_Y = 7;
static const int MOVETO_Z = 8;
static const int SET_LIM = 9;
static const int TURN_ON_ILLUMINATION = 10;
static const int TURN_OFF_ILLUMINATION = 11;
static const int SET_ILLUMINATION = 12;
static const int SET_ILLUMINATION_LED_MATRIX = 13;
static const int ACK_JOYSTICK_BUTTON_PRESSED = 14;
static const int ANALOG_WRITE_ONBOARD_DAC = 15;
static const int SET_DAC80508_REFDIV_GAIN = 16;
static const int SET_ILLUMINATION_INTENSITY_FACTOR = 17;
static const int SET_LIM_SWITCH_POLARITY = 20;
static const int CONFIGURE_STEPPER_DRIVER = 21;
static const int SET_MAX_VELOCITY_ACCELERATION = 22;
static const int SET_LEAD_SCREW_PITCH = 23;
static const int SET_OFFSET_VELOCITY = 24;
static const int CONFIGURE_STAGE_PID = 25;
static const int ENABLE_STAGE_PID = 26;
static const int DISABLE_STAGE_PID = 27;
static const int SET_HOME_SAFETY_MERGIN = 28;
static const int SET_PID_ARGUMENTS = 29;
static const int SEND_HARDWARE_TRIGGER = 30;
static const int SET_STROBE_DELAY = 31;
static const int SET_PIN_LEVEL = 41;
static const int INITIALIZE = 254;
static const int RESET = 255;

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

static const int LIM_CODE_X_POSITIVE = 0;
static const int LIM_CODE_X_NEGATIVE = 1;
static const int LIM_CODE_Y_POSITIVE = 2;
static const int LIM_CODE_Y_NEGATIVE = 3;
static const int LIM_CODE_Z_POSITIVE = 4;
static const int LIM_CODE_Z_NEGATIVE = 5;

static const int ACTIVE_LOW = 0;
static const int ACTIVE_HIGH = 1;
static const int DISABLED = 2;

/***************************************************************************************************/
/**************************************** Pin definations ******************************************/
/***************************************************************************************************/
// Teensy4.1 board v1 def

// illumination
static const int LASER_405nm = 5;   // to rename
static const int LASER_488nm = 4;   // to rename
static const int LASER_561nm = 22;   // to rename
static const int LASER_638nm = 3;  // to rename
static const int LASER_730nm = 23;  // to rename
// PWM6 2
// PWM7 1
// PWM8 0

// output pins
//static const int digitial_output_pins = {2,1,6,7,8,9,10,15,24,25} // PWM 6-7, 9-16
//static const int num_digital_pins = 10;
// pin 7,8 (PWM 10, 11) may be used for UART, pin 24,25 (PWM 15, 16) may be used for UART
static const int num_digital_pins = 6;
static const int digitial_output_pins[num_digital_pins] = {2, 1, 6, 9, 10, 15}; // PWM 6-7, 9, 12-14

// camera trigger
static const int camera_trigger_pins[] = {29, 30, 31, 32, 16, 28}; // trigger 1-6

// motors
const uint8_t pin_TMC4361_CS[4] = {41, 36, 35, 34};
const uint8_t pin_TMC4361_CLK = 37;

// DAC
const int DAC8050x_CS_pin = 33;

// LED driver
const int pin_LT3932_SYNC = 25;

// power good
const int pin_PG = 0;

/***************************************************************************************************/
/************************************ camera trigger and strobe ************************************/
/***************************************************************************************************/
static const int TRIGGER_PULSE_LENGTH_us = 50;
bool trigger_output_level[6] = {HIGH, HIGH, HIGH, HIGH, HIGH, HIGH};
bool control_strobe[6] = {false, false, false, false, false, false};
bool strobe_output_level[6] = {LOW, LOW, LOW, LOW, LOW, LOW};
bool strobe_on[6] = {false, false, false, false, false, false};
int strobe_delay[6] = {0, 0, 0, 0, 0, 0};
long illumination_on_time[6] = {0, 0, 0, 0, 0, 0};
long timestamp_trigger_rising_edge[6] = {0, 0, 0, 0, 0, 0};
IntervalTimer strobeTimer;
static const int strobeTimer_interval_us = 100;

/***************************************************************************************************/
/******************************************* DAC80508 **********************************************/
/***************************************************************************************************/
const uint8_t DAC8050x_DAC_ADDR = 0x08;
const uint8_t DAC8050x_GAIN_ADDR = 0x04;
const uint8_t DAC8050x_CONFIG_ADDR = 0x03;

void set_DAC8050x_gain(uint8_t div, uint8_t gains) 
{
  uint16_t value = 0;
  value = (div << 8) + gains; 
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE2));
  digitalWrite(DAC8050x_CS_pin, LOW);
  SPI.transfer(DAC8050x_GAIN_ADDR);
  SPI.transfer16(value);
  digitalWrite(DAC8050x_CS_pin, HIGH);
  SPI.endTransaction();
}

// REFDIV-E = 0 (no div), BUFF7-GAIN = 0 (no gain) 1 for channel 0-6, 2 for channel 7
void set_DAC8050x_default_gain()
{
  set_DAC8050x_gain(0x00, 0x80);
}

void set_DAC8050x_config()
{
  uint16_t value = 0;
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE2));
  digitalWrite(DAC8050x_CS_pin, LOW);
  SPI.transfer(DAC8050x_CONFIG_ADDR);
  SPI.transfer16(value);
  digitalWrite(DAC8050x_CS_pin, HIGH);
  SPI.endTransaction();
}

void set_DAC8050x_output(int channel, uint16_t value)
{
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE2));
  digitalWrite(DAC8050x_CS_pin, LOW);
  SPI.transfer(DAC8050x_DAC_ADDR + channel);
  SPI.transfer16(value);
  digitalWrite(DAC8050x_CS_pin, HIGH);
  SPI.endTransaction();
}

/***************************************************************************************************/
/******************************************* steppers **********************************************/
/***************************************************************************************************/
const uint32_t clk_Hz_TMC4361 = 16000000;
const uint8_t lft_sw_pol[4] = {0, 0, 0, 1};
const uint8_t rht_sw_pol[4] = {0, 0, 0, 1};
const uint8_t TMC4361_homing_sw[4] = {LEFT_SW, LEFT_SW, RGHT_SW, LEFT_SW};
const int32_t vslow = 0x04FFFC00;

ConfigurationTypeDef tmc4361_configs[N_MOTOR];
TMC4361ATypeDef tmc4361[N_MOTOR];

volatile long X_commanded_target_position = 0;
volatile long Y_commanded_target_position = 0;
volatile long Z_commanded_target_position = 0;
volatile bool X_commanded_movement_in_progress = false;
volatile bool Y_commanded_movement_in_progress = false;
volatile bool Z_commanded_movement_in_progress = false;
int X_direction;
int Y_direction;
int Z_direction;

int32_t focusPosition = 0;

long target_position;

volatile int32_t X_pos = 0;
volatile int32_t Y_pos = 0;
volatile int32_t Z_pos = 0;

float offset_velocity_x = 0;
float offset_velocity_y = 0;

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
elapsedMicros us_since_x_home_found;
elapsedMicros us_since_y_home_found;
elapsedMicros us_since_z_home_found;
/* to do: move the movement direction sign from configuration.txt (python) to the firmware (with
   setPinsInverted() so that homing_direction_X, homing_direction_Y, homing_direction_Z will no
   longer be needed. This way the home switches can act as limit switches - right now because
   homing_direction_ needs be set by the computer, before they're set, the home switches cannot be
   used as limit switches. Alternatively, add homing_direction_set variables.
*/

long X_POS_LIMIT = X_POS_LIMIT_MM * steps_per_mm_X;
long X_NEG_LIMIT = X_NEG_LIMIT_MM * steps_per_mm_X;
long Y_POS_LIMIT = Y_POS_LIMIT_MM * steps_per_mm_Y;
long Y_NEG_LIMIT = Y_NEG_LIMIT_MM * steps_per_mm_Y;
long Z_POS_LIMIT = Z_POS_LIMIT_MM * steps_per_mm_Z;
long Z_NEG_LIMIT = Z_NEG_LIMIT_MM * steps_per_mm_Z;

// PID
bool stage_PID_enabled[N_MOTOR];

// PID arguments
typedef struct pid_arguments {
	uint16_t 	p;
	uint8_t 	i; 
	uint8_t 	d; 
} PID_ARGUMENTS;
PID_ARGUMENTS axis_pid_arg[N_MOTOR];

// home safety margin
uint16_t home_safety_margin[4] = {4, 4, 4, 4};

/***************************************************************************************************/
/******************************************** timing ***********************************************/
/***************************************************************************************************/
// IntervalTimer does not work on teensy with SPI, the below lines are to be removed
static const int TIMER_PERIOD = 500; // in us
volatile int counter_send_pos_update = 0;
volatile bool flag_send_pos_update = false;

static const int interval_send_pos_update = 10000; // in us
elapsedMicros us_since_last_pos_update;

static const int interval_check_position = 10000; // in us
elapsedMicros us_since_last_check_position;

static const int interval_send_joystick_update = 30000; // in us
elapsedMicros us_since_last_joystick_update;

static const int interval_check_limit = 20000; // in us
elapsedMicros us_since_last_check_limit;
/***************************************************************************************************/
/******************************************* joystick **********************************************/
/***************************************************************************************************/
PacketSerial joystick_packetSerial;
static const int JOYSTICK_MSG_LENGTH = 10;
bool flag_read_joystick = false;

// joystick xy
int16_t joystick_delta_x = 0;
int16_t joystick_delta_y = 0;

// joystick button
bool joystick_button_pressed = false;
long joystick_button_pressed_timestamp = 0;

// focus
int32_t focuswheel_pos = 0;
bool first_packet_from_joystick_panel = true;

// btns
uint8_t btns;

void onJoystickPacketReceived(const uint8_t* buffer, size_t size)
{

  if (size != JOYSTICK_MSG_LENGTH)
  {
    if (DEBUG_MODE)
      Serial.println("! wrong number of bytes received !");
    return;
  }

  //  focuswheel_pos = uint32_t(buffer[0])*16777216 + uint32_t(buffer[1])*65536 + uint32_t(buffer[2])*256 + uint32_t(buffer[3]);
  //  focusPosition = focuswheel_pos;

  if (first_packet_from_joystick_panel)
  {
    focuswheel_pos = int32_t(uint32_t(buffer[0]) * 16777216 + uint32_t(buffer[1]) * 65536 + uint32_t(buffer[2]) * 256 + uint32_t(buffer[3]));
    first_packet_from_joystick_panel = false;
  }
  else
  {
    focusPosition = focusPosition + ( int32_t(uint32_t(buffer[0]) * 16777216 + uint32_t(buffer[1]) * 65536 + uint32_t(buffer[2]) * 256 + uint32_t(buffer[3])) - focuswheel_pos );
    focuswheel_pos = int32_t(uint32_t(buffer[0]) * 16777216 + uint32_t(buffer[1]) * 65536 + uint32_t(buffer[2]) * 256 + uint32_t(buffer[3]));
  }

  joystick_delta_x = JOYSTICK_SIGN_X * int16_t( uint16_t(buffer[4]) * 256 + uint16_t(buffer[5]) );
  joystick_delta_y = JOYSTICK_SIGN_Y * int16_t( uint16_t(buffer[6]) * 256 + uint16_t(buffer[7]) );
  btns = buffer[8];

  // temporary
  /*
    if(btns & 0x01)
    {
    joystick_button_pressed = true;
    joystick_button_pressed_timestamp = millis();
    // to add: ACK for the joystick panel
    }
  */

  flag_read_joystick = true;

}

/***************************************************************************************************/
/***************************************** illumination ********************************************/
/***************************************************************************************************/
int illumination_source = 0;
uint16_t illumination_intensity = 65535;
float illumination_intensity_factor = 0.6;
uint8_t led_matrix_r = 0;
uint8_t led_matrix_g = 0;
uint8_t led_matrix_b = 0;
static const int LED_MATRIX_MAX_INTENSITY = 100;
static const float GREEN_ADJUSTMENT_FACTOR = 1;
static const float RED_ADJUSTMENT_FACTOR = 1;
static const float BLUE_ADJUSTMENT_FACTOR = 1;
bool illumination_is_on = false;
void turn_on_illumination();
void turn_off_illumination();

static const int ILLUMINATION_SOURCE_LED_ARRAY_FULL = 0;
static const int ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF = 1;
static const int ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF = 2;
static const int ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR = 3;
static const int ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA = 4;
static const int ILLUMINATION_SOURCE_LED_EXTERNAL_FET = 20;
static const int ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT = 5;
static const int ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT = 6;
static const int ILLUMINATION_SOURCE_LED_ARRAY_TOP_HALF = 7;
static const int ILLUMINATION_SOURCE_LED_ARRAY_BOTTOM_HALF = 8;
static const int ILLUMINATION_SOURCE_405NM = 11;
static const int ILLUMINATION_SOURCE_488NM = 12;
static const int ILLUMINATION_SOURCE_638NM = 13;
static const int ILLUMINATION_SOURCE_561NM = 14;
static const int ILLUMINATION_SOURCE_730NM = 15;

#define NUM_LEDS DOTSTAR_NUM_LEDS
#define LED_MATRIX_DATA_PIN 26
#define LED_MATRIX_CLOCK_PIN 27
CRGB matrix[NUM_LEDS];

void set_all(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_left(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_right(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_top(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_bottom(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_low_na(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_left_dot(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void set_right_dot(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b);
void clear_matrix(CRGB * matrix);
void turn_on_LED_matrix_pattern(CRGB * matrix, int pattern, uint8_t led_matrix_r, uint8_t led_matrix_g, uint8_t led_matrix_b);

void turn_on_illumination()
{
  illumination_is_on = true;
  switch (illumination_source)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_FULL, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT:
      turn_on_LED_matrix_pattern(matrix, ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT, led_matrix_r, led_matrix_g, led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_TOP_HALF:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_TOP_HALF,led_matrix_r,led_matrix_g,led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_BOTTOM_HALF:
      turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_BOTTOM_HALF,led_matrix_r,led_matrix_g,led_matrix_b);
      break;
    case ILLUMINATION_SOURCE_LED_EXTERNAL_FET:
      break;
    case ILLUMINATION_SOURCE_405NM:
      digitalWrite(LASER_405nm, HIGH);
      break;
    case ILLUMINATION_SOURCE_488NM:
      digitalWrite(LASER_488nm, HIGH);
      break;
    case ILLUMINATION_SOURCE_638NM:
      digitalWrite(LASER_638nm, HIGH);
      break;
    case ILLUMINATION_SOURCE_561NM:
      digitalWrite(LASER_561nm, HIGH);
      break;
    case ILLUMINATION_SOURCE_730NM:
      digitalWrite(LASER_730nm, HIGH);
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
    case ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_TOP_HALF:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_BOTTOM_HALF:
      clear_matrix(matrix);
      break;
    case ILLUMINATION_SOURCE_LED_EXTERNAL_FET:
      break;
    case ILLUMINATION_SOURCE_405NM:
      digitalWrite(LASER_405nm, LOW);
      break;
    case ILLUMINATION_SOURCE_488NM:
      digitalWrite(LASER_488nm, LOW);
      break;
    case ILLUMINATION_SOURCE_638NM:
      digitalWrite(LASER_638nm, LOW);
      break;
    case ILLUMINATION_SOURCE_561NM:
      digitalWrite(LASER_561nm, LOW);
      break;
    case ILLUMINATION_SOURCE_730NM:
      digitalWrite(LASER_730nm, LOW);
      break;
  }
  illumination_is_on = false;
}

void set_illumination(int source, uint16_t intensity)
{
  illumination_source = source;
  illumination_intensity = intensity * illumination_intensity_factor;
  switch (source)
  {
    case ILLUMINATION_SOURCE_405NM:
      set_DAC8050x_output(0, illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_488NM:
      set_DAC8050x_output(1, illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_638NM:
      set_DAC8050x_output(3, illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_561NM:
      set_DAC8050x_output(2, illumination_intensity);
      break;
    case ILLUMINATION_SOURCE_730NM:
      set_DAC8050x_output(4, illumination_intensity);
      break;
  }
  if (illumination_is_on)
    turn_on_illumination(); //update the illumination
}

void set_illumination_led_matrix(int source, uint8_t r, uint8_t g, uint8_t b)
{
  illumination_source = source;
  led_matrix_r = r;
  led_matrix_g = g;
  led_matrix_b = b;
  if (illumination_is_on)
    turn_on_illumination(); //update the illumination
}

void ISR_strobeTimer()
{
  for (int camera_channel = 0; camera_channel < 6; camera_channel++)
  {
    // strobe pulse
    if (control_strobe[camera_channel])
    {
      if (illumination_on_time[camera_channel] <= 30000)
      {
        // if the illumination on time is smaller than 30 ms, use delayMicroseconds to control the pulse length to avoid pulse length jitter
        if ( ((micros() - timestamp_trigger_rising_edge[camera_channel]) >= strobe_delay[camera_channel]) && strobe_output_level[camera_channel] == LOW )
        {
          turn_on_illumination();
          delayMicroseconds(illumination_on_time[camera_channel]);
          turn_off_illumination();
          control_strobe[camera_channel] = false;
        }
      }
      else
      {
        // start the strobe
        if ( ((micros() - timestamp_trigger_rising_edge[camera_channel]) >= strobe_delay[camera_channel]) && strobe_output_level[camera_channel] == LOW )
        {
          turn_on_illumination();
          strobe_output_level[camera_channel] = HIGH;
        }
        // end the strobe
        if (((micros() - timestamp_trigger_rising_edge[camera_channel]) >= strobe_delay[camera_channel] + illumination_on_time[camera_channel]) && strobe_output_level[camera_channel] == HIGH)
        {
          turn_off_illumination();
          strobe_output_level[camera_channel] = LOW;
          control_strobe[camera_channel] = false;
        }
      }
    }
  }
}

/***************************************************************************************************/
/********************************************* setup ***********************************************/
/***************************************************************************************************/
void setup() {

  // Initialize Native USB port
  SerialUSB.begin(2000000);
  delay(500);
  SerialUSB.setTimeout(200);
  //while(!SerialUSB);            // Wait until connection is established
  buffer_rx_ptr = 0;

  // Joystick packet serial
  Serial5.begin(115200);
  joystick_packetSerial.setStream(&Serial5);
  joystick_packetSerial.setPacketHandler(&onJoystickPacketReceived);

  // power good pin
  pinMode(pin_PG, INPUT_PULLUP);

  // camera trigger pins
  for (int i = 0; i < 6; i++)
  {
    pinMode(camera_trigger_pins[i], OUTPUT);
    digitalWrite(camera_trigger_pins[i], HIGH);
  }

  // enable pins
  pinMode(LASER_405nm, OUTPUT);
  digitalWrite(LASER_405nm, LOW);

  pinMode(LASER_488nm, OUTPUT);
  digitalWrite(LASER_488nm, LOW);

  pinMode(LASER_638nm, OUTPUT);
  digitalWrite(LASER_638nm, LOW);

  pinMode(LASER_561nm, OUTPUT);
  digitalWrite(LASER_561nm, LOW);

  pinMode(LASER_730nm, OUTPUT);
  digitalWrite(LASER_730nm, LOW);

  for (int i = 0; i < num_digital_pins; i++)
  {
    pinMode(digitial_output_pins[i], OUTPUT);
    digitalWrite(digitial_output_pins[i], LOW);
  }

  // steppers pins
  for (int i = 0; i < 4; i++)
  {
    pinMode(pin_TMC4361_CS[i], OUTPUT);
    digitalWrite(pin_TMC4361_CS[i], HIGH);
  }

  // LED drivers
  pinMode(pin_LT3932_SYNC, OUTPUT);
  analogWriteFrequency(pin_LT3932_SYNC, 2000000);
  analogWrite(pin_LT3932_SYNC, 128);

  // timer - does not work with SPI
  /*
    IntervalTimer systemTimer;
    systemTimer.begin(timer_interruptHandler, TIMER_PERIOD);
  */

  // DAC pins
  pinMode(DAC8050x_CS_pin, OUTPUT);
  digitalWrite(DAC8050x_CS_pin, HIGH);

  // wait for PG to turn high
  delay(100);
  while (!digitalRead(pin_PG))
  {
    delay(50);
  }

  /*********************************************************************************************************
   ************************************** TMC4361A + TMC2660 beginning *************************************
   *********************************************************************************************************/
  // PID
  for (int i = 0; i < N_MOTOR; i++) {
    stage_PID_enabled[i] = 0;

	axis_pid_arg[i].p = (1<<12);
	axis_pid_arg[i].i = 0;
	axis_pid_arg[i].d = 0;
  }

  // clock
  pinMode(pin_TMC4361_CLK, OUTPUT);
  analogWriteFrequency(pin_TMC4361_CLK, clk_Hz_TMC4361);
  analogWrite(pin_TMC4361_CLK, 128); // 50% duty

  // initialize TMC4361 structs with default values and initialize CS pins
  for (int i = 0; i < N_MOTOR; i++)
  {
    // initialize the tmc4361 with their channel number and default configuration
    tmc4361A_init(&tmc4361[i], pin_TMC4361_CS[i], &tmc4361_configs[i], tmc4361A_defaultRegisterResetState);
    // set the chip select pins
    pinMode(pin_TMC4361_CS[i], OUTPUT);
    digitalWrite(pin_TMC4361_CS[i], HIGH);
  }

  // motor configurations
  tmc4361A_tmc2660_config(&tmc4361[x], (X_MOTOR_RMS_CURRENT_mA / 1000)*R_sense_xy / 0.2298, X_MOTOR_I_HOLD, 1, 1, 1, SCREW_PITCH_X_MM, FULLSTEPS_PER_REV_X, MICROSTEPPING_X);
  tmc4361A_tmc2660_config(&tmc4361[y], (Y_MOTOR_RMS_CURRENT_mA / 1000)*R_sense_xy / 0.2298, Y_MOTOR_I_HOLD, 1, 1, 1, SCREW_PITCH_Y_MM, FULLSTEPS_PER_REV_Y, MICROSTEPPING_Y);
  tmc4361A_tmc2660_config(&tmc4361[z], (Z_MOTOR_RMS_CURRENT_mA / 1000)*R_sense_z / 0.2298, Z_MOTOR_I_HOLD, 1, 1, 1, SCREW_PITCH_Z_MM, FULLSTEPS_PER_REV_Z, MICROSTEPPING_Z); // need to make current scaling on TMC2660 is > 16 (out of 31)

  // SPI
  SPI.begin();
  delayMicroseconds(5000);

  // initilize TMC4361 and TMC2660 - turn on functionality
  for (int i = 0; i < N_MOTOR; i++)
    tmc4361A_tmc2660_init(&tmc4361[i], clk_Hz_TMC4361); // set up ICs with SPI control and other parameters

  // enable limit switch reading
  tmc4361A_enableLimitSwitch(&tmc4361[x], lft_sw_pol[x], LEFT_SW, flip_limit_switch_x);
  tmc4361A_enableLimitSwitch(&tmc4361[x], rht_sw_pol[x], RGHT_SW, flip_limit_switch_x);
  tmc4361A_enableLimitSwitch(&tmc4361[y], lft_sw_pol[y], LEFT_SW, flip_limit_switch_y);
  tmc4361A_enableLimitSwitch(&tmc4361[y], rht_sw_pol[y], RGHT_SW, flip_limit_switch_y);
  tmc4361A_enableLimitSwitch(&tmc4361[z], rht_sw_pol[z], RGHT_SW, false);
  tmc4361A_enableLimitSwitch(&tmc4361[z], lft_sw_pol[z], LEFT_SW, false); // removing this causes z homing to not work properly
  // tmc4361A_rstBits(&tmc4361[z],TMC4361A_REFERENCE_CONF,TMC4361A_STOP_LEFT_EN_MASK);

  // motion profile configuration
  uint32_t max_velocity_usteps[N_MOTOR];
  uint32_t max_acceleration_usteps[N_MOTOR];
  max_acceleration_usteps[x] = tmc4361A_ammToMicrosteps(&tmc4361[x], MAX_ACCELERATION_X_mm);
  max_acceleration_usteps[y] = tmc4361A_ammToMicrosteps(&tmc4361[y], MAX_ACCELERATION_Y_mm);
  max_acceleration_usteps[z] = tmc4361A_ammToMicrosteps(&tmc4361[z], MAX_ACCELERATION_Z_mm);
  max_velocity_usteps[x] = tmc4361A_vmmToMicrosteps(&tmc4361[x], MAX_VELOCITY_X_mm);
  max_velocity_usteps[y] = tmc4361A_vmmToMicrosteps(&tmc4361[y], MAX_VELOCITY_Y_mm);
  max_velocity_usteps[z] = tmc4361A_vmmToMicrosteps(&tmc4361[z], MAX_VELOCITY_Z_mm);
  for (int i = 0; i < N_MOTOR; i++)
  {
    // initialize ramp with default values
    tmc4361A_setMaxSpeed(&tmc4361[i], max_velocity_usteps[i]);
    tmc4361A_setMaxAcceleration(&tmc4361[i], max_acceleration_usteps[i]);
    tmc4361[i].rampParam[ASTART_IDX] = 0;
    tmc4361[i].rampParam[DFINAL_IDX] = 0;
    tmc4361A_sRampInit(&tmc4361[i]);
  }

  /*
    // homing - temporary
    tmc4361A_enableHomingLimit(&tmc4361[x], lft_sw_pol[x], TMC4361_homing_sw[x]);
    tmc4361A_moveToExtreme(&tmc4361[x], vslow*2, RGHT_DIR);
    tmc4361A_moveToExtreme(&tmc4361[x], vslow*2, LEFT_DIR);
    tmc4361A_setHome(&tmc4361[x]);

    tmc4361A_enableHomingLimit(&tmc4361[y], lft_sw_pol[y], TMC4361_homing_sw[y]);
    tmc4361A_moveToExtreme(&tmc4361[y], vslow*2, RGHT_DIR);
    tmc4361A_moveToExtreme(&tmc4361[y], vslow*2, LEFT_DIR);
    tmc4361A_setHome(&tmc4361[y]);
  */

  // homing switch settings
  tmc4361A_enableHomingLimit(&tmc4361[x], lft_sw_pol[x], TMC4361_homing_sw[x], home_safety_margin[x]);
  tmc4361A_enableHomingLimit(&tmc4361[y], lft_sw_pol[y], TMC4361_homing_sw[y], home_safety_margin[y]);
  tmc4361A_enableHomingLimit(&tmc4361[z], rht_sw_pol[z], TMC4361_homing_sw[z], home_safety_margin[z]);

  /*********************************************************************************************************
   ***************************************** TMC4361A + TMC2660 end ****************************************
   *********************************************************************************************************/
  // DAC init
  set_DAC8050x_config();
  set_DAC8050x_default_gain();

  // led matrix
  FastLED.addLeds<APA102, LED_MATRIX_DATA_PIN, LED_MATRIX_CLOCK_PIN, BGR, 1>(matrix, NUM_LEDS);  // 1 MHz clock rate

  // variables
  X_pos = 0;
  Y_pos = 0;
  Z_pos = 0;

  offset_velocity_x = 0;
  offset_velocity_y = 0;

  // strobe timer
  strobeTimer.begin(ISR_strobeTimer, strobeTimer_interval_us);

  // motor stall prevention
  tmc4361A_config_init_stallGuard(&tmc4361[x], 12, true, 1);
  tmc4361A_config_init_stallGuard(&tmc4361[y], 12, true, 1);

  // initialize timer value
  us_since_last_pos_update = 5000;
  us_since_last_check_position = 3000;
  us_since_last_joystick_update = 3000;
  us_since_last_check_limit = 2000;
}

/***************************************************************************************************/
/********************************************** loop ***********************************************/
/***************************************************************************************************/

void loop() {

  // process incoming packets
  joystick_packetSerial.update();

  // read one meesage from the buffer
  while (SerialUSB.available())
  {
    buffer_rx[buffer_rx_ptr] = SerialUSB.read();
    buffer_rx_ptr = buffer_rx_ptr + 1;
    if (buffer_rx_ptr == CMD_LENGTH)
    {
      buffer_rx_ptr = 0;
      cmd_id = buffer_rx[0];
      uint8_t checksum = crc8ccitt(buffer_rx, CMD_LENGTH - 1);
      if (checksum != buffer_rx[CMD_LENGTH - 1])
      {
        checksum_error = true;
        // empty the serial buffer because byte-level out-of-sync can also cause this error
        while (SerialUSB.available())
          SerialUSB.read();
        return;
      }
      else
      {
        checksum_error = false;
      }

      switch (buffer_rx[1])
      {
        case MOVE_X:
          {
            long relative_position = int32_t(uint32_t(buffer_rx[2]) * 16777216 + uint32_t(buffer_rx[3]) * 65536 + uint32_t(buffer_rx[4]) * 256 + uint32_t(buffer_rx[5]));
            long current_position = tmc4361A_currentPosition(&tmc4361[x]);
            X_direction = sgn(relative_position);
            X_commanded_target_position = ( relative_position > 0 ? min(current_position + relative_position, X_POS_LIMIT) : max(current_position + relative_position, X_NEG_LIMIT) );
            if ( tmc4361A_moveTo(&tmc4361[x], X_commanded_target_position) == 0)
            {
              X_commanded_movement_in_progress = true;
              mcu_cmd_execution_in_progress = true;
            }
            break;
          }
        case MOVE_Y:
          {
            long relative_position = int32_t(uint32_t(buffer_rx[2]) * 16777216 + uint32_t(buffer_rx[3]) * 65536 + uint32_t(buffer_rx[4]) * 256 + uint32_t(buffer_rx[5]));
            long current_position = tmc4361A_currentPosition(&tmc4361[y]);
            Y_direction = sgn(relative_position);
            Y_commanded_target_position = ( relative_position > 0 ? min(current_position + relative_position, Y_POS_LIMIT) : max(current_position + relative_position, Y_NEG_LIMIT) );
            if ( tmc4361A_moveTo(&tmc4361[y], Y_commanded_target_position) == 0)
            {
              Y_commanded_movement_in_progress = true;
              mcu_cmd_execution_in_progress = true;
            }
            break;
          }
        case MOVE_Z:
          {
            long relative_position = int32_t(uint32_t(buffer_rx[2]) * 16777216 + uint32_t(buffer_rx[3]) * 65536 + uint32_t(buffer_rx[4]) * 256 + uint32_t(buffer_rx[5]));
            long current_position = tmc4361A_currentPosition(&tmc4361[z]);
            Z_direction = sgn(relative_position);
            Z_commanded_target_position = ( relative_position > 0 ? min(current_position + relative_position, Z_POS_LIMIT) : max(current_position + relative_position, Z_NEG_LIMIT) );
            focusPosition = Z_commanded_target_position;
            if ( tmc4361A_moveTo(&tmc4361[z], Z_commanded_target_position) == 0)
            {
              Z_commanded_movement_in_progress = true;
              mcu_cmd_execution_in_progress = true;
            }
            break;
          }
        case MOVETO_X:
          {
            long absolute_position = int32_t(uint32_t(buffer_rx[2]) * 16777216 + uint32_t(buffer_rx[3]) * 65536 + uint32_t(buffer_rx[4]) * 256 + uint32_t(buffer_rx[5]));
            X_direction = sgn(absolute_position - tmc4361A_currentPosition(&tmc4361[x]));
            X_commanded_target_position = absolute_position;
            if (tmc4361A_moveTo(&tmc4361[x], X_commanded_target_position) == 0)
            {
              X_commanded_movement_in_progress = true;
              mcu_cmd_execution_in_progress = true;
            }
            break;
          }
        case MOVETO_Y:
          {
            long absolute_position = int32_t(uint32_t(buffer_rx[2]) * 16777216 + uint32_t(buffer_rx[3]) * 65536 + uint32_t(buffer_rx[4]) * 256 + uint32_t(buffer_rx[5]));
            Y_direction = sgn(absolute_position - tmc4361A_currentPosition(&tmc4361[y]));
            Y_commanded_target_position = absolute_position;
            if (tmc4361A_moveTo(&tmc4361[y], Y_commanded_target_position) == 0)
            {
              Y_commanded_movement_in_progress = true;
              mcu_cmd_execution_in_progress = true;
            }
            break;
          }
        case MOVETO_Z:
          {
            long absolute_position = int32_t(uint32_t(buffer_rx[2]) * 16777216 + uint32_t(buffer_rx[3]) * 65536 + uint32_t(buffer_rx[4]) * 256 + uint32_t(buffer_rx[5]));
            Z_direction = sgn(absolute_position - tmc4361A_currentPosition(&tmc4361[z]));
            Z_commanded_target_position = absolute_position;
            if (tmc4361A_moveTo(&tmc4361[z], Z_commanded_target_position) == 0)
            {
              focusPosition = absolute_position;
              Z_commanded_movement_in_progress = true;
              mcu_cmd_execution_in_progress = true;
            }
            break;
          }
        case SET_LIM:
          {
            switch (buffer_rx[2])
            {
              case LIM_CODE_X_POSITIVE:
                {
                  X_POS_LIMIT = int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]));
                  tmc4361A_setVirtualLimit(&tmc4361[x], 1, X_POS_LIMIT);
                  tmc4361A_enableVirtualLimitSwitch(&tmc4361[x], 1);
                  break;
                }
              case LIM_CODE_X_NEGATIVE:
                {
                  X_NEG_LIMIT = int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]));
                  tmc4361A_setVirtualLimit(&tmc4361[x], -1, X_NEG_LIMIT);
                  tmc4361A_enableVirtualLimitSwitch(&tmc4361[x], -1);
                  break;
                }
              case LIM_CODE_Y_POSITIVE:
                {
                  Y_POS_LIMIT = int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]));
                  tmc4361A_setVirtualLimit(&tmc4361[y], 1, Y_POS_LIMIT);
                  tmc4361A_enableVirtualLimitSwitch(&tmc4361[y], 1);
                  break;
                }
              case LIM_CODE_Y_NEGATIVE:
                {
                  Y_NEG_LIMIT = int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]));
                  tmc4361A_setVirtualLimit(&tmc4361[y], -1, Y_NEG_LIMIT);
                  tmc4361A_enableVirtualLimitSwitch(&tmc4361[y], -1);
                  break;
                }
              case LIM_CODE_Z_POSITIVE:
                {
                  Z_POS_LIMIT = int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]));
                  tmc4361A_setVirtualLimit(&tmc4361[z], 1, Z_POS_LIMIT);
                  tmc4361A_enableVirtualLimitSwitch(&tmc4361[z], 1);
                  break;
                }
              case LIM_CODE_Z_NEGATIVE:
                {
                  Z_NEG_LIMIT = int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]));
                  tmc4361A_setVirtualLimit(&tmc4361[z], -1, Z_NEG_LIMIT);
                  tmc4361A_enableVirtualLimitSwitch(&tmc4361[z], -1);
                  break;
                }
            }
            break;
          }
        case SET_LIM_SWITCH_POLARITY:
          {
            switch (buffer_rx[2])
            {
              case AXIS_X:
                {
                  if (buffer_rx[3] != DISABLED)
                  {
                    LIM_SWITCH_X_ACTIVE_LOW = (buffer_rx[3] == ACTIVE_LOW);
                  }
                  break;
                }
              case AXIS_Y:
                {
                  if (buffer_rx[3] != DISABLED)
                  {
                    LIM_SWITCH_Y_ACTIVE_LOW = (buffer_rx[3] == ACTIVE_LOW);
                  }
                  break;
                }
              case AXIS_Z:
                {
                  if (buffer_rx[3] != DISABLED)
                  {
                    LIM_SWITCH_Z_ACTIVE_LOW = (buffer_rx[3] == ACTIVE_LOW);
                  }
                  break;
                }
            }
            break;
          }
		case SET_HOME_SAFETY_MERGIN:
		  {
            switch (buffer_rx[2])
            {
              case AXIS_X:
                {
                  uint16_t margin = (uint16_t(buffer_rx[3]) << 8) + uint16_t(buffer_rx[4]);
				  float home_safety_margin_mm = float(margin) / 1000.0;
				  home_safety_margin[x] = tmc4361A_xmmToMicrosteps(&tmc4361[x], home_safety_margin_mm);
  				  tmc4361A_enableHomingLimit(&tmc4361[x], lft_sw_pol[x], TMC4361_homing_sw[x], home_safety_margin[x]);
                  break;
                }
              case AXIS_Y:
                {
                  uint16_t margin = (uint16_t(buffer_rx[3]) << 8) + uint16_t(buffer_rx[4]);
				  float home_safety_margin_mm = float(margin) / 1000.0;
				  home_safety_margin[y] = tmc4361A_xmmToMicrosteps(&tmc4361[y], home_safety_margin_mm);
  				  tmc4361A_enableHomingLimit(&tmc4361[y], lft_sw_pol[y], TMC4361_homing_sw[y], home_safety_margin[y]);
                  break;
                }
              case AXIS_Z:
                {
                  uint16_t margin = (uint16_t(buffer_rx[3]) << 8) + uint16_t(buffer_rx[4]);
				  float home_safety_margin_mm = float(margin) / 1000.0;
				  home_safety_margin[z] = tmc4361A_xmmToMicrosteps(&tmc4361[z], home_safety_margin_mm);
  				  tmc4361A_enableHomingLimit(&tmc4361[z], lft_sw_pol[z], TMC4361_homing_sw[z], home_safety_margin[z]);
                  break;
                }
            }
            break;
		  }
		case SET_PID_ARGUMENTS:
		  {
			int axis = buffer_rx[2];
			uint16_t p = (uint16_t(buffer_rx[3]) << 8) + uint16_t(buffer_rx[4]);
			uint8_t  i = uint8_t(buffer_rx[5]);
			uint8_t  d = uint8_t(buffer_rx[6]);

			axis_pid_arg[axis].p = p; 
			axis_pid_arg[axis].i = i;
			axis_pid_arg[axis].d = d;

		  	break;
		  }
        case CONFIGURE_STEPPER_DRIVER:
          {
            switch (buffer_rx[2])
            {
              case AXIS_X:
                {
                  int microstepping_setting = buffer_rx[3];
                  if (microstepping_setting > 128)
                    microstepping_setting = 256;
                  MICROSTEPPING_X = microstepping_setting == 0 ? 1 : microstepping_setting;
                  steps_per_mm_X = FULLSTEPS_PER_REV_X * MICROSTEPPING_X / SCREW_PITCH_X_MM;
                  X_MOTOR_RMS_CURRENT_mA = uint16_t(buffer_rx[4]) * 256 + uint16_t(buffer_rx[5]);
                  X_MOTOR_I_HOLD = float(buffer_rx[6]) / 255;
                  tmc4361A_tmc2660_config(&tmc4361[x], (X_MOTOR_RMS_CURRENT_mA / 1000.0)*R_sense_xy / 0.2298, X_MOTOR_I_HOLD, 1, 1, 1, SCREW_PITCH_X_MM, FULLSTEPS_PER_REV_X, MICROSTEPPING_X);
                  tmc4361A_tmc2660_update(&tmc4361[x]);
                  break;
                }
              case AXIS_Y:
                {
                  int microstepping_setting = buffer_rx[3];
                  if (microstepping_setting > 128)
                    microstepping_setting = 256;
                  MICROSTEPPING_Y = microstepping_setting == 0 ? 1 : microstepping_setting;
                  steps_per_mm_Y = FULLSTEPS_PER_REV_Y * MICROSTEPPING_Y / SCREW_PITCH_Y_MM;
                  Y_MOTOR_RMS_CURRENT_mA = uint16_t(buffer_rx[4]) * 256 + uint16_t(buffer_rx[5]);
                  Y_MOTOR_I_HOLD = float(buffer_rx[6]) / 255;
                  tmc4361A_tmc2660_config(&tmc4361[y], (Y_MOTOR_RMS_CURRENT_mA / 1000.0)*R_sense_xy / 0.2298, Y_MOTOR_I_HOLD, 1, 1, 1, SCREW_PITCH_Y_MM, FULLSTEPS_PER_REV_Y, MICROSTEPPING_Y);
                  tmc4361A_tmc2660_update(&tmc4361[y]);
                  break;
                }
              case AXIS_Z:
                {
                  int microstepping_setting = buffer_rx[3];
                  if (microstepping_setting > 128)
                    microstepping_setting = 256;
                  MICROSTEPPING_Z = microstepping_setting == 0 ? 1 : microstepping_setting;
                  steps_per_mm_Z = FULLSTEPS_PER_REV_Z * MICROSTEPPING_Z / SCREW_PITCH_Z_MM;
                  Z_MOTOR_RMS_CURRENT_mA = uint16_t(buffer_rx[4]) * 256 + uint16_t(buffer_rx[5]);
                  Z_MOTOR_I_HOLD = float(buffer_rx[6]) / 255;
                  tmc4361A_tmc2660_config(&tmc4361[z], (Z_MOTOR_RMS_CURRENT_mA / 1000.0)*R_sense_z / 0.2298, Z_MOTOR_I_HOLD, 1, 1, 1, SCREW_PITCH_Z_MM, FULLSTEPS_PER_REV_Z, MICROSTEPPING_Z);
                  tmc4361A_tmc2660_update(&tmc4361[z]);
                  break;
                }
            }
            break;
          }
        case SET_MAX_VELOCITY_ACCELERATION:
          {
            switch (buffer_rx[2])
            {
              case AXIS_X:
                {
                  MAX_VELOCITY_X_mm = float(uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4])) / 100;
                  MAX_ACCELERATION_X_mm = float(uint16_t(buffer_rx[5]) * 256 + uint16_t(buffer_rx[6])) / 10;
                  tmc4361A_setMaxSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], MAX_VELOCITY_X_mm) );
                  tmc4361A_setMaxAcceleration(&tmc4361[x], tmc4361A_ammToMicrosteps( &tmc4361[x], MAX_ACCELERATION_X_mm) );
                  break;
                }
              case AXIS_Y:
                {
                  MAX_VELOCITY_Y_mm = float(uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4])) / 100;
                  MAX_ACCELERATION_Y_mm = float(uint16_t(buffer_rx[5]) * 256 + uint16_t(buffer_rx[6])) / 10;
                  tmc4361A_setMaxSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], MAX_VELOCITY_Y_mm) );
                  tmc4361A_setMaxAcceleration(&tmc4361[y], tmc4361A_ammToMicrosteps( &tmc4361[y], MAX_ACCELERATION_Y_mm) );
                  break;
                }
              case AXIS_Z:
                {
                  MAX_VELOCITY_Z_mm = float(uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4])) / 100;
                  MAX_ACCELERATION_Z_mm = float(uint16_t(buffer_rx[5]) * 256 + uint16_t(buffer_rx[6])) / 10;
                  tmc4361A_setMaxSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], MAX_VELOCITY_Z_mm) );
                  tmc4361A_setMaxAcceleration(&tmc4361[z], tmc4361A_ammToMicrosteps( &tmc4361[z], MAX_ACCELERATION_Z_mm) );
                  break;
                }
            }
            break;
          }
        case SET_LEAD_SCREW_PITCH:
          {
            switch (buffer_rx[2])
            {
              case AXIS_X:
                {
                  SCREW_PITCH_X_MM = float(uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4])) / 1000;
                  steps_per_mm_X = FULLSTEPS_PER_REV_X * MICROSTEPPING_X / SCREW_PITCH_X_MM;
                  break;
                }
              case AXIS_Y:
                {
                  SCREW_PITCH_Y_MM = float(uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4])) / 1000;
                  steps_per_mm_Y = FULLSTEPS_PER_REV_Y * MICROSTEPPING_Y / SCREW_PITCH_Y_MM;
                  break;
                }
              case AXIS_Z:
                {
                  SCREW_PITCH_Z_MM = float(uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4])) / 1000;
                  steps_per_mm_Z = FULLSTEPS_PER_REV_Z * MICROSTEPPING_Z / SCREW_PITCH_Z_MM;
                  break;
                }
            }
            break;
          }
        case HOME_OR_ZERO:
          {
            // zeroing
            if (buffer_rx[3] == HOME_OR_ZERO_ZERO)
            {
              switch (buffer_rx[2])
              {
                case AXIS_X:
                  tmc4361A_setCurrentPosition(&tmc4361[x], 0);
                  X_pos = 0;
                  break;
                case AXIS_Y:
                  tmc4361A_setCurrentPosition(&tmc4361[y], 0);
                  Y_pos = 0;
                  break;
                case AXIS_Z:
                  tmc4361A_setCurrentPosition(&tmc4361[z], 0);
                  Z_pos = 0;
                  focusPosition = 0;
                  break;
              }
            }
            // atomic operation, no need to change mcu_cmd_execution_in_progress flag
            // homing
            else if (buffer_rx[3] == HOME_NEGATIVE || buffer_rx[3] == HOME_POSITIVE)
            {
              switch (buffer_rx[2])
              {
                case AXIS_X:
                  if (stage_PID_enabled[AXIS_X] == 1)
                    tmc4361A_set_PID(&tmc4361[AXIS_X], PID_DISABLE);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[x], -1);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[x], 1);
                  homing_direction_X = buffer_rx[3];
                  home_X_found = false;
                  if (homing_direction_X == HOME_NEGATIVE) // use the left limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[x]) == LEFT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], RGHT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                    else
                    {
                      is_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], LEFT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                  }
                  else // use the right limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[x]) == RGHT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], LEFT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                    else
                    {
                      is_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], RGHT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                  }
                  /*
                    if(digitalRead(X_LIM)==(LIM_SWITCH_X_ACTIVE_LOW?HIGH:LOW))
                    {
                    is_homing_X = true;
                    if(homing_direction_X==HOME_NEGATIVE)
                      stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                    else
                      stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                    }
                    else
                    {
                    // get out of the hysteresis zone
                    is_preparing_for_homing_X = true;
                    if(homing_direction_X==HOME_NEGATIVE)
                      stepper_X.setSpeed(HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                    else
                      stepper_X.setSpeed(-HOMING_VELOCITY_X*MAX_VELOCITY_X_mm*steps_per_mm_X);
                    }
                  */
                  break;
                case AXIS_Y:
                  if (stage_PID_enabled[AXIS_Y] == 1)
                    tmc4361A_set_PID(&tmc4361[AXIS_Y], PID_DISABLE);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[y], -1);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[y], 1);
                  homing_direction_Y = buffer_rx[3];
                  home_Y_found = false;
                  if (homing_direction_Y == HOME_NEGATIVE) // use the left limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[y]) == LEFT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], RGHT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                    else
                    {
                      is_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], LEFT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                  }
                  else // use the right limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[y]) == RGHT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], LEFT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                    else
                    {
                      is_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], RGHT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                  }
                  break;
                case AXIS_Z:
                  if (stage_PID_enabled[AXIS_Z] == 1)
                    tmc4361A_set_PID(&tmc4361[AXIS_Z], PID_DISABLE);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[z], -1);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[z], 1);
                  homing_direction_Z = buffer_rx[3];
                  home_Z_found = false;
                  if (homing_direction_Z == HOME_NEGATIVE) // use the left limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[z]) == LEFT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_Z = true;
                      tmc4361A_readInt(&tmc4361[z], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], RGHT_DIR * HOMING_VELOCITY_Z * MAX_VELOCITY_Z_mm ));
                    }
                    else
                    {
                      is_homing_Z = true;
                      tmc4361A_readInt(&tmc4361[z], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], LEFT_DIR * HOMING_VELOCITY_Z * MAX_VELOCITY_Z_mm ));
                    }
                  }
                  else // use the right limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[z]) == RGHT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_Z = true;
                      tmc4361A_readInt(&tmc4361[z], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], LEFT_DIR * HOMING_VELOCITY_Z * MAX_VELOCITY_Z_mm ));
                    }
                    else
                    {
                      is_homing_Z = true;
                      tmc4361A_readInt(&tmc4361[z], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], RGHT_DIR * HOMING_VELOCITY_Z * MAX_VELOCITY_Z_mm ));
                      // tmc4361A_moveTo(&tmc4361[y], tmc4361A_currentPosition(&tmc4361[y])+51200); // for debugging
                    }
                  }
                  break;
                case AXES_XY:
                  if (stage_PID_enabled[AXIS_X] == 1)
                    tmc4361A_set_PID(&tmc4361[AXIS_X], PID_DISABLE);
                  if (stage_PID_enabled[AXIS_Y] == 1)
                    tmc4361A_set_PID(&tmc4361[AXIS_Y], PID_DISABLE);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[x], -1);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[x], 1);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[y], -1);
                  tmc4361A_disableVirtualLimitSwitch(&tmc4361[y], 1);
                  is_homing_XY = true;
                  home_X_found = false;
                  home_Y_found = false;
                  // homing x
                  homing_direction_X = buffer_rx[3];
                  home_X_found = false;
                  if (homing_direction_X == HOME_NEGATIVE) // use the left limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[x]) == LEFT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], RGHT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                    else
                    {
                      is_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], LEFT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                  }
                  else // use the right limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[x]) == RGHT_DIR )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], LEFT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                    else
                    {
                      is_homing_X = true;
                      tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], RGHT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
                    }
                  }
                  // homing y
                  homing_direction_Y = buffer_rx[4];
                  home_Y_found = false;
                  if (homing_direction_Y == HOME_NEGATIVE) // use the left limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[y]) == LEFT_SW )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], RGHT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                    else
                    {
                      is_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], LEFT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                  }
                  else // use the right limit switch for homing
                  {
                    if ( tmc4361A_readLimitSwitches(&tmc4361[y]) == RGHT_DIR )
                    {
                      // get out of the hysteresis zone
                      is_preparing_for_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], LEFT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                    else
                    {
                      is_homing_Y = true;
                      tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
                      tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], RGHT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
                    }
                  }
                  break;
              }
              mcu_cmd_execution_in_progress = true;
            }
          }
        case SET_OFFSET_VELOCITY:
          {
            if (enable_offset_velocity)
            {
              switch (buffer_rx[2])
              {
                case AXIS_X:
                  offset_velocity_x = float( int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6])) ) / 1000000;
                  break;
                case AXIS_Y:
                  offset_velocity_y = float( int32_t(uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6])) ) / 1000000;
                  break;
              }
              break;
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
            set_illumination(buffer_rx[2], (uint16_t(buffer_rx[3]) << 8) + uint16_t(buffer_rx[4])); //important to have "<<8" with in "()"
            break;
          }
        case SET_ILLUMINATION_LED_MATRIX:
          {
            set_illumination_led_matrix(buffer_rx[2], buffer_rx[3], buffer_rx[4], buffer_rx[5]);
            break;
          }
        case ACK_JOYSTICK_BUTTON_PRESSED:
          {
            joystick_button_pressed = false;
            break;
          }
        case ANALOG_WRITE_ONBOARD_DAC:
          {
            int dac = buffer_rx[2];
            uint16_t value = ( uint16_t(buffer_rx[3]) * 256 + uint16_t(buffer_rx[4]) );
            set_DAC8050x_output(dac, value);
			break;
          }
		case SET_DAC80508_REFDIV_GAIN:
		  {
			uint8_t div   = buffer_rx[2];
			uint8_t gains = buffer_rx[3];
			set_DAC8050x_gain(div, gains);
			break;
		  }
		case SET_ILLUMINATION_INTENSITY_FACTOR:
		  {
			uint8_t factor   = uint8_t(buffer_rx[2]);
			if (factor > 100) factor = 100;
			illumination_intensity_factor = float(factor) / 100;
			break;
		  }
        case SET_STROBE_DELAY:
          {
            strobe_delay[buffer_rx[2]] = uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]);
            break;
          }
        case SEND_HARDWARE_TRIGGER:
          {
            int camera_channel = buffer_rx[2] & 0x0f;
            control_strobe[camera_channel] = buffer_rx[2] >> 7;
            illumination_on_time[camera_channel] = uint32_t(buffer_rx[3]) * 16777216 + uint32_t(buffer_rx[4]) * 65536 + uint32_t(buffer_rx[5]) * 256 + uint32_t(buffer_rx[6]);
            digitalWrite(camera_trigger_pins[camera_channel], LOW);
            timestamp_trigger_rising_edge[camera_channel] = micros();
            trigger_output_level[camera_channel] = LOW;
            break;
          }
        case SET_PIN_LEVEL:
          {
            int pin = buffer_rx[2];
            bool level = buffer_rx[3];
            digitalWrite(pin, level);
            break;
          }
        case CONFIGURE_STAGE_PID:
          {
            int axis = buffer_rx[2];
            int flip_direction = buffer_rx[3];
            int transitions_per_revolution = (buffer_rx[4] << 8) + buffer_rx[5];
            // Init encoder. transitions per revolution, velocity filter wait time (# of clock cycles), IIR filter exponent, vmean update frequency, invert direction (must increase as microsteps increases)
            tmc4361A_init_ABN_encoder(&tmc4361[axis], transitions_per_revolution, 32, 4, 512, flip_direction);
            // Init PID. target reach tolerance, position error tolerance, P, I, and D coefficients, max speed, winding limit, derivative update rate
            if (axis == z)
              tmc4361A_init_PID(&tmc4361[axis], 25, 25, axis_pid_arg[axis].p, axis_pid_arg[axis].i, axis_pid_arg[axis].d, tmc4361A_vmmToMicrosteps(&tmc4361[axis], MAX_VELOCITY_Z_mm), 4096, 2);
            else if (axis == y)
              tmc4361A_init_PID(&tmc4361[axis], 25, 25, axis_pid_arg[axis].p, axis_pid_arg[axis].i, axis_pid_arg[axis].d, tmc4361A_vmmToMicrosteps(&tmc4361[axis], MAX_VELOCITY_Y_mm), 32767, 2);
            else
              tmc4361A_init_PID(&tmc4361[axis], 25, 25, axis_pid_arg[axis].p, axis_pid_arg[axis].i, axis_pid_arg[axis].d, tmc4361A_vmmToMicrosteps(&tmc4361[axis], MAX_VELOCITY_X_mm), 32767, 2);
            break;
          }
        case ENABLE_STAGE_PID:
          {
            int axis = buffer_rx[2];
            tmc4361A_set_PID(&tmc4361[axis], PID_BPG0);
            stage_PID_enabled[axis] = 1;
            break;
          }
        case DISABLE_STAGE_PID:
          {
            int axis = buffer_rx[2];
            tmc4361A_set_PID(&tmc4361[axis], PID_DISABLE);
            stage_PID_enabled[axis] = 0;
            break;
          }
        case INITIALIZE:
          {
            // reset z target position so that z does not move when "current position" for z is set to 0
            focusPosition = 0;
            first_packet_from_joystick_panel = true;
            // initilize TMC4361 and TMC2660
            for (int i = 0; i < N_MOTOR; i++)
              tmc4361A_tmc2660_init(&tmc4361[i], clk_Hz_TMC4361); // set up ICs with SPI control and other parameters
            // enable limit switch reading
            tmc4361A_enableLimitSwitch(&tmc4361[x], lft_sw_pol[x], LEFT_SW, flip_limit_switch_x);
            tmc4361A_enableLimitSwitch(&tmc4361[x], rht_sw_pol[x], RGHT_SW, flip_limit_switch_x);
            tmc4361A_enableLimitSwitch(&tmc4361[y], lft_sw_pol[y], LEFT_SW, flip_limit_switch_y);
            tmc4361A_enableLimitSwitch(&tmc4361[y], rht_sw_pol[y], RGHT_SW, flip_limit_switch_y);
            tmc4361A_enableLimitSwitch(&tmc4361[z], rht_sw_pol[z], RGHT_SW, false);
            tmc4361A_enableLimitSwitch(&tmc4361[z], lft_sw_pol[z], LEFT_SW, false);
            // motion profile
            uint32_t max_velocity_usteps[N_MOTOR];
            uint32_t max_acceleration_usteps[N_MOTOR];
            max_acceleration_usteps[x] = tmc4361A_ammToMicrosteps(&tmc4361[x], MAX_ACCELERATION_X_mm);
            max_acceleration_usteps[y] = tmc4361A_ammToMicrosteps(&tmc4361[y], MAX_ACCELERATION_Y_mm);
            max_acceleration_usteps[z] = tmc4361A_ammToMicrosteps(&tmc4361[z], MAX_ACCELERATION_Z_mm);
            max_velocity_usteps[x] = tmc4361A_vmmToMicrosteps(&tmc4361[x], MAX_VELOCITY_X_mm);
            max_velocity_usteps[y] = tmc4361A_vmmToMicrosteps(&tmc4361[y], MAX_VELOCITY_Y_mm);
            max_velocity_usteps[z] = tmc4361A_vmmToMicrosteps(&tmc4361[z], MAX_VELOCITY_Z_mm);
            for (int i = 0; i < N_MOTOR; i++)
            {
              // initialize ramp with default values
              tmc4361A_setMaxSpeed(&tmc4361[i], max_velocity_usteps[i]);
              tmc4361A_setMaxAcceleration(&tmc4361[i], max_acceleration_usteps[i]);
              tmc4361[i].rampParam[ASTART_IDX] = 0;
              tmc4361[i].rampParam[DFINAL_IDX] = 0;
              tmc4361A_sRampInit(&tmc4361[i]);
            }

            // homing switch settings
			tmc4361A_enableHomingLimit(&tmc4361[x], lft_sw_pol[x], TMC4361_homing_sw[x], home_safety_margin[x]);
			tmc4361A_enableHomingLimit(&tmc4361[y], lft_sw_pol[y], TMC4361_homing_sw[y], home_safety_margin[y]);
			tmc4361A_enableHomingLimit(&tmc4361[z], rht_sw_pol[z], TMC4361_homing_sw[z], home_safety_margin[z]);

            // DAC init
            set_DAC8050x_config();
            set_DAC8050x_default_gain();
            break;
          }
        case RESET:
          {
            mcu_cmd_execution_in_progress = false;
            X_commanded_movement_in_progress = false;
            Y_commanded_movement_in_progress = false;
            Z_commanded_movement_in_progress = false;
            is_homing_X = false;
            is_homing_Y = false;
            is_homing_Z = false;
            is_homing_XY = false;
            home_X_found = false;
            home_Y_found = false;
            home_Z_found = false;
            is_preparing_for_homing_X = false;
            is_preparing_for_homing_Y = false;
            is_preparing_for_homing_Z = false;
            cmd_id = 0;
            break;
          }
        default:
          break;
      }
      //break; // exit the while loop after reading one message
    }
  }

  // camera trigger
  for (int camera_channel = 0; camera_channel < 6; camera_channel++)
  {
    // end the trigger pulse
    if (trigger_output_level[camera_channel] == LOW && (micros() - timestamp_trigger_rising_edge[camera_channel]) >= TRIGGER_PULSE_LENGTH_us )
    {
      digitalWrite(camera_trigger_pins[camera_channel], HIGH);
      trigger_output_level[camera_channel] = HIGH;
    }

    /*
      // strobe pulse
      if(control_strobe[camera_channel])
      {
      if(illumination_on_time[camera_channel] <= 30000)
      {
        // if the illumination on time is smaller than 30 ms, use delayMicroseconds to control the pulse length to avoid pulse length jitter (can be up to 20 us if using the code in the else branch)
        if( ((micros()-timestamp_trigger_rising_edge[camera_channel])>=strobe_delay[camera_channel]) && strobe_output_level[camera_channel]==LOW )
        {
          turn_on_illumination();
          delayMicroseconds(illumination_on_time[camera_channel]);
          turn_off_illumination();
          control_strobe[camera_channel] = false;
        }
      }
      else
      {
        // start the strobe
        if( ((micros()-timestamp_trigger_rising_edge[camera_channel])>=strobe_delay[camera_channel]) && strobe_output_level[camera_channel]==LOW )
        {
          turn_on_illumination();
          strobe_output_level[camera_channel] = HIGH;
        }
        // end the strobe
        if(((micros()-timestamp_trigger_rising_edge[camera_channel])>=strobe_delay[camera_channel]+illumination_on_time[camera_channel]) && strobe_output_level[camera_channel]==HIGH)
        {
          turn_off_illumination();
          strobe_output_level[camera_channel] = LOW;
          control_strobe[camera_channel] = false;
        }
      }
      }
    */
  }

  // homing - preparing for homing
  if (is_preparing_for_homing_X)
  {
    if (homing_direction_X == HOME_NEGATIVE) // use the left limit switch for homing
    {
      if (tmc4361A_readLimitSwitches(&tmc4361[x]) != LEFT_SW)
      {
        is_preparing_for_homing_X = false;
        is_homing_X = true;
        tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
        tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], LEFT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
      }
    }
    else // use the right limit switch for homing
    {
      if (tmc4361A_readLimitSwitches(&tmc4361[x]) != RGHT_SW)
      {
        is_preparing_for_homing_X = false;
        is_homing_X = true;
        tmc4361A_readInt(&tmc4361[x], TMC4361A_EVENTS);
        tmc4361A_setSpeed(&tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], RGHT_DIR * HOMING_VELOCITY_X * MAX_VELOCITY_X_mm ));
      }
    }
  }
  if (is_preparing_for_homing_Y)
  {
    if (homing_direction_Y == HOME_NEGATIVE) // use the left limit switch for homing
    {
      if (tmc4361A_readLimitSwitches(&tmc4361[y]) != LEFT_SW)
      {
        is_preparing_for_homing_Y = false;
        is_homing_Y = true;
        tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
        tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], LEFT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
      }
    }
    else // use the right limit switch for homing
    {
      if (tmc4361A_readLimitSwitches(&tmc4361[y]) != RGHT_SW)
      {
        is_preparing_for_homing_Y = false;
        is_homing_Y = true;
        tmc4361A_readInt(&tmc4361[y], TMC4361A_EVENTS);
        tmc4361A_setSpeed(&tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], RGHT_DIR * HOMING_VELOCITY_Y * MAX_VELOCITY_Y_mm ));
      }
    }
  }
  if (is_preparing_for_homing_Z)
  {
    if (homing_direction_Z == HOME_NEGATIVE) // use the left limit switch for homing
    {
      if (tmc4361A_readLimitSwitches(&tmc4361[z]) != LEFT_SW)
      {
        is_preparing_for_homing_Z = false;
        is_homing_Z = true;
        tmc4361A_readInt(&tmc4361[z], TMC4361A_EVENTS);
        tmc4361A_setSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], LEFT_DIR * HOMING_VELOCITY_Z * MAX_VELOCITY_Z_mm ));
      }
    }
    else // use the right limit switch for homing
    {
      if (tmc4361A_readLimitSwitches(&tmc4361[z]) != RGHT_SW)
      {
        is_preparing_for_homing_Z = false;
        is_homing_Z = true;
        tmc4361A_readInt(&tmc4361[z], TMC4361A_EVENTS);
        tmc4361A_setSpeed(&tmc4361[z], tmc4361A_vmmToMicrosteps( &tmc4361[z], RGHT_DIR * HOMING_VELOCITY_Z * MAX_VELOCITY_Z_mm ));
      }
    }
  }

  // homing complete check
  if (is_homing_X && !home_X_found)
  {
    if (homing_direction_X == HOME_NEGATIVE) // use the left limit switch for homing
    {
      if (tmc4361A_readSwitchEvent(&tmc4361[x]) == LEFT_SW || tmc4361A_readLimitSwitches(&tmc4361[x]) == LEFT_SW)
      {
        home_X_found = true;
        us_since_x_home_found = 0;
        tmc4361[x].xmin = tmc4361A_readInt(&tmc4361[x], TMC4361A_X_LATCH_RD);
        // tmc4361A_writeInt(&tmc4361[x], TMC4361A_X_TARGET, tmc4361[x].xmin);
        tmc4361A_moveTo(&tmc4361[x], tmc4361[x].xmin);
        X_commanded_movement_in_progress = true;
        X_commanded_target_position = tmc4361[x].xmin;
        // turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,30,10,10); // debug
      }
    }
    else // use the right limit switch for homing
    {
      if (tmc4361A_readSwitchEvent(&tmc4361[x]) == RGHT_SW || tmc4361A_readLimitSwitches(&tmc4361[x]) == RGHT_SW)
      {
        home_X_found = true;
        us_since_x_home_found = 0;
        tmc4361[x].xmax = tmc4361A_readInt(&tmc4361[x], TMC4361A_X_LATCH_RD);
        // tmc4361A_writeInt(&tmc4361[x], TMC4361A_X_TARGET, tmc4361[x].xmax);
        tmc4361A_moveTo(&tmc4361[x], tmc4361[x].xmax);
        X_commanded_movement_in_progress = true;
        X_commanded_target_position = tmc4361[x].xmax;
        // turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,30,10,10); // debug
      }
    }
  }
  if (is_homing_Y && !home_Y_found)
  {
    if (homing_direction_Y == HOME_NEGATIVE) // use the left limit switch for homing
    {
      if (tmc4361A_readSwitchEvent(&tmc4361[y]) == LEFT_SW || tmc4361A_readLimitSwitches(&tmc4361[y]) == LEFT_SW)
      {
        home_Y_found = true;
        us_since_y_home_found = 0;
        tmc4361[y].xmin = tmc4361A_readInt(&tmc4361[y], TMC4361A_X_LATCH_RD);
        // tmc4361A_writeInt(&tmc4361[y], TMC4361A_X_TARGET, tmc4361[y].xmin);
        tmc4361A_moveTo(&tmc4361[y], tmc4361[y].xmin);
        Y_commanded_movement_in_progress = true;
        Y_commanded_target_position = tmc4361[y].xmin;
        // turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,30,10,10); // debug
      }
    }
    else // use the right limit switch for homing
    {
      if (tmc4361A_readSwitchEvent(&tmc4361[y]) == RGHT_SW || tmc4361A_readLimitSwitches(&tmc4361[y]) == RGHT_SW)
      {
        home_Y_found = true;
        us_since_y_home_found = 0;
        tmc4361[y].xmax = tmc4361A_readInt(&tmc4361[y], TMC4361A_X_LATCH_RD);
        // tmc4361A_writeInt(&tmc4361[y], TMC4361A_X_TARGET, tmc4361[y].xmax);
        tmc4361A_moveTo(&tmc4361[y], tmc4361[y].xmax);
        Y_commanded_movement_in_progress = true;
        Y_commanded_target_position = tmc4361[y].xmax;
        // turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,30,10,10); // debug
      }
    }
  }
  if (is_homing_Z && !home_Z_found)
  {
    if (homing_direction_Z == HOME_NEGATIVE) // use the left limit switch for homing
    {
      if (tmc4361A_readSwitchEvent(&tmc4361[z]) == LEFT_SW || tmc4361A_readLimitSwitches(&tmc4361[z]) == LEFT_SW)
      {
        home_Z_found = true;
        us_since_z_home_found = 0;
        tmc4361[z].xmin = tmc4361A_readInt(&tmc4361[z], TMC4361A_X_LATCH_RD);
        // tmc4361A_writeInt(&tmc4361[z], TMC4361A_X_TARGET, tmc4361[z].xmin);
        tmc4361A_moveTo(&tmc4361[z], tmc4361[z].xmin);
        Z_commanded_movement_in_progress = true;
        Z_commanded_target_position = tmc4361[z].xmin;
        // turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,30,10,10); // debug
      }
    }
    else // use the right limit switch for homing
    {
      if (tmc4361A_readSwitchEvent(&tmc4361[z]) == RGHT_SW || tmc4361A_readLimitSwitches(&tmc4361[z]) == RGHT_SW)
      {
        home_Z_found = true;
        us_since_z_home_found = 0;
        tmc4361[z].xmax = tmc4361A_readInt(&tmc4361[z], TMC4361A_X_LATCH_RD);
        //tmc4361A_writeInt(&tmc4361[z], TMC4361A_X_TARGET, tmc4361[z].xmax);
        tmc4361A_moveTo(&tmc4361[z], tmc4361[z].xmax);
        Z_commanded_movement_in_progress = true;
        Z_commanded_target_position = tmc4361[z].xmax;
        // turn_on_LED_matrix_pattern(matrix,ILLUMINATION_SOURCE_LED_ARRAY_FULL,30,10,10); // debug
      }
    }
  }

  // finish homing
  if (is_homing_X && home_X_found && ( tmc4361A_currentPosition(&tmc4361[x]) == tmc4361A_targetPosition(&tmc4361[x]) || us_since_x_home_found > 500 * 1000 ) )
  {
    // clear_matrix(matrix); // debug
    tmc4361A_setCurrentPosition(&tmc4361[x], 0);
    if (stage_PID_enabled[AXIS_X])
      tmc4361A_set_PID(&tmc4361[AXIS_X], PID_BPG0);
    X_pos = 0;
    is_homing_X = false;
    X_commanded_movement_in_progress = false;
    X_commanded_target_position = 0;
    if (is_homing_XY == false)
      mcu_cmd_execution_in_progress = false;
  }
  if (is_homing_Y && home_Y_found && ( tmc4361A_currentPosition(&tmc4361[y]) == tmc4361A_targetPosition(&tmc4361[y]) || us_since_y_home_found > 500 * 1000 ) )
  {
    // clear_matrix(matrix); // debug
    tmc4361A_setCurrentPosition(&tmc4361[y], 0);
    if (stage_PID_enabled[AXIS_Y])
      tmc4361A_set_PID(&tmc4361[AXIS_Y], PID_BPG0);
    Y_pos = 0;
    is_homing_Y = false;
    Y_commanded_movement_in_progress = false;
    Y_commanded_target_position = 0;
    if (is_homing_XY == false)
      mcu_cmd_execution_in_progress = false;
  }
  if (is_homing_Z && home_Z_found && ( tmc4361A_currentPosition(&tmc4361[z]) == tmc4361A_targetPosition(&tmc4361[z]) || us_since_z_home_found > 500 * 1000 ) )
  {
    // clear_matrix(matrix); // debug
    tmc4361A_setCurrentPosition(&tmc4361[z], 0);
    if (stage_PID_enabled[AXIS_Z])
      tmc4361A_set_PID(&tmc4361[AXIS_Z], PID_BPG0);
    Z_pos = 0;
    focusPosition = 0;
    is_homing_Z = false;
    Z_commanded_movement_in_progress = false;
    Z_commanded_target_position = 0;
    mcu_cmd_execution_in_progress = false;
  }

  // homing complete
  if (is_homing_XY && home_X_found && !is_homing_X && home_Y_found && !is_homing_Y)
  {
    is_homing_XY = false;
    mcu_cmd_execution_in_progress = false;
  }

  if (flag_read_joystick)
  {
	if (us_since_last_joystick_update > interval_send_joystick_update)
	{
	  us_since_last_joystick_update = 0;

	  // read x joystick
	  if (!X_commanded_movement_in_progress && !is_homing_X && !is_preparing_for_homing_X) //if(stepper_X.distanceToGo()==0) // only read joystick when computer commanded travel has finished - doens't work
	  {
	    // joystick at motion position
	    if (abs(joystick_delta_x) > 0)
	  	  tmc4361A_setSpeed( &tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], offset_velocity_x + (joystick_delta_x / 32768.0)*MAX_VELOCITY_X_mm ) );
	    // joystick at rest position
	    else
	    {
	  	  if (enable_offset_velocity)
	  	    tmc4361A_setSpeed( &tmc4361[x], tmc4361A_vmmToMicrosteps( &tmc4361[x], offset_velocity_x ) );
	  	  else
		    tmc4361A_stop(&tmc4361[x]); // tmc4361A_setSpeed( &tmc4361[x], 0 ) causes problems for zeroing
	      }
	  }

	  // read y joystick
	  if (!Y_commanded_movement_in_progress && !is_homing_Y && !is_preparing_for_homing_Y)
	  {
	    // joystick at motion position
	    if (abs(joystick_delta_y) > 0)
	  	  tmc4361A_setSpeed( &tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], offset_velocity_y + (joystick_delta_y / 32768.0)*MAX_VELOCITY_Y_mm ) );
	    // joystick at rest position
	    else
	    {
	  	  if (enable_offset_velocity)
	  	    tmc4361A_setSpeed( &tmc4361[y], tmc4361A_vmmToMicrosteps( &tmc4361[y], offset_velocity_y ) );
	  	  else
	  	    tmc4361A_stop(&tmc4361[y]); // tmc4361A_setSpeed( &tmc4361[y], 0 ) causes problems for zeroing
	    }
	  }
	}

    // set the read joystick flag to false
    flag_read_joystick = false;
  }

  /*
    // handle limits (moption from joystick control or offset velocity)
    if( tmc4361A_currentPosition(&tmc4361[x])>=X_POS_LIMIT && tmc4361A_vmmToMicrosteps( &tmc4361[x], offset_velocity_x + (joystick_delta_x/32768.0)*MAX_VELOCITY_X_mm )>0 && !X_commanded_movement_in_progress )
    {
    tmc4361A_stop(&tmc4361[x]);
    }
    if( tmc4361A_currentPosition(&tmc4361[x])<=X_NEG_LIMIT && tmc4361A_vmmToMicrosteps( &tmc4361[x], offset_velocity_x + (joystick_delta_x/32768.0)*MAX_VELOCITY_X_mm )<0 && !X_commanded_movement_in_progress )
    {
    tmc4361A_stop(&tmc4361[x]);
    }
    if( tmc4361A_currentPosition(&tmc4361[y])>=Y_POS_LIMIT && tmc4361A_vmmToMicrosteps( &tmc4361[y], offset_velocity_y + (joystick_delta_y/32768.0)*MAX_VELOCITY_Y_mm )>0 && !Y_commanded_movement_in_progress )
    {
    tmc4361A_stop(&tmc4361[y]);
    }
    if( tmc4361A_currentPosition(&tmc4361[y])<=Y_NEG_LIMIT && tmc4361A_vmmToMicrosteps( &tmc4361[y], offset_velocity_y + (joystick_delta_y/32768.0)*MAX_VELOCITY_Y_mm )<0 && !Y_commanded_movement_in_progress )
    {
    tmc4361A_stop(&tmc4361[y]);
    }
  */

  // focus control
  if (focusPosition > Z_POS_LIMIT)
    focusPosition = Z_POS_LIMIT;
  if (focusPosition < Z_NEG_LIMIT)
    focusPosition = Z_NEG_LIMIT;
  if (is_homing_Z == false && is_preparing_for_homing_Z == false)
    tmc4361A_moveTo(&tmc4361[z], focusPosition);

  // send position update to computer
  if (us_since_last_pos_update > interval_send_pos_update)
  {
    us_since_last_pos_update = 0;

    buffer_tx[0] = cmd_id;
    if (checksum_error)
      buffer_tx[1] = CMD_CHECKSUM_ERROR; // cmd_execution_status
    else
      buffer_tx[1] = mcu_cmd_execution_in_progress ? IN_PROGRESS : COMPLETED_WITHOUT_ERRORS; // cmd_execution_status

    uint32_t X_pos_int32t = uint32_t( X_use_encoder ? X_pos : int32_t(tmc4361A_currentPosition(&tmc4361[x])) );
    buffer_tx[2] = byte(X_pos_int32t >> 24);
    buffer_tx[3] = byte((X_pos_int32t >> 16) % 256);
    buffer_tx[4] = byte((X_pos_int32t >> 8) % 256);
    buffer_tx[5] = byte((X_pos_int32t) % 256);

    uint32_t Y_pos_int32t = uint32_t( Y_use_encoder ? Y_pos : int32_t(tmc4361A_currentPosition(&tmc4361[y])) );
    buffer_tx[6] = byte(Y_pos_int32t >> 24);
    buffer_tx[7] = byte((Y_pos_int32t >> 16) % 256);
    buffer_tx[8] = byte((Y_pos_int32t >> 8) % 256);
    buffer_tx[9] = byte((Y_pos_int32t) % 256);

    uint32_t Z_pos_int32t = uint32_t( Z_use_encoder ? Z_pos : int32_t(tmc4361A_currentPosition(&tmc4361[z])) );
    buffer_tx[10] = byte(Z_pos_int32t >> 24);
    buffer_tx[11] = byte((Z_pos_int32t >> 16) % 256);
    buffer_tx[12] = byte((Z_pos_int32t >> 8) % 256);
    buffer_tx[13] = byte((Z_pos_int32t) % 256);

    // fail-safe clearing of the joystick_button_pressed bit (in case the ack is not received)
    if (joystick_button_pressed && millis() - joystick_button_pressed_timestamp > 1000)
      joystick_button_pressed = false;

    buffer_tx[18] &= ~ (1 << BIT_POS_JOYSTICK_BUTTON); // clear the joystick button bit
    buffer_tx[18] = buffer_tx[18] | joystick_button_pressed << BIT_POS_JOYSTICK_BUTTON;

    if(!DEBUG_MODE)
      SerialUSB.write(buffer_tx,MSG_LENGTH);
    else
    {
      SerialUSB.print("focus: ");
      SerialUSB.print(focuswheel_pos);
      // Serial.print(buffer[3]);
      SerialUSB.print(", joystick delta x: ");
      SerialUSB.print(joystick_delta_x);
      SerialUSB.print(", joystick delta y: ");
      SerialUSB.print(joystick_delta_y);
      SerialUSB.print(", btns: ");
      SerialUSB.print(btns);
      SerialUSB.print(", PG:");
      SerialUSB.println(digitalRead(pin_PG));
    }
    flag_send_pos_update = false;
    
  }

  // keep checking position process at suitable frequence
  if(us_since_last_check_position > interval_check_position) {
	  us_since_last_check_position = 0;

	  // check if commanded position has been reached
  	  if (X_commanded_movement_in_progress && tmc4361A_currentPosition(&tmc4361[x]) == X_commanded_target_position && !is_homing_X && !tmc4361A_isRunning(&tmc4361[x], stage_PID_enabled[x])) // homing is handled separately
	  {
		X_commanded_movement_in_progress = false;
		mcu_cmd_execution_in_progress = false || Y_commanded_movement_in_progress || Z_commanded_movement_in_progress;
	  }
  	  if (Y_commanded_movement_in_progress && tmc4361A_currentPosition(&tmc4361[y]) == Y_commanded_target_position && !is_homing_Y && !tmc4361A_isRunning(&tmc4361[y], stage_PID_enabled[y]))
	  {
		Y_commanded_movement_in_progress = false;
		mcu_cmd_execution_in_progress = false || X_commanded_movement_in_progress || Z_commanded_movement_in_progress;
	  }
      if (Z_commanded_movement_in_progress && tmc4361A_currentPosition(&tmc4361[z]) == Z_commanded_target_position && !is_homing_Z && !tmc4361A_isRunning(&tmc4361[z], stage_PID_enabled[z]))
	  {
		Z_commanded_movement_in_progress = false;
		mcu_cmd_execution_in_progress = false || X_commanded_movement_in_progress || Y_commanded_movement_in_progress;
	  }
  }

  if (us_since_last_check_limit > interval_check_limit) {
	us_since_last_check_limit = 0;

  	// at limit
    if (X_commanded_movement_in_progress && !is_homing_X) // homing is handled separately
    {
      uint8_t event = tmc4361A_readSwitchEvent(&tmc4361[x]);
      // if( tmc4361A_readLimitSwitches(&tmc4361[x])==LEFT_SW || tmc4361A_readLimitSwitches(&tmc4361[x])==RGHT_SW )
      if ( ( X_direction == LEFT_DIR && event == LEFT_SW ) || ( X_direction == RGHT_DIR && event == RGHT_SW ) )
      {
        X_commanded_movement_in_progress = false;
        mcu_cmd_execution_in_progress = false || Y_commanded_movement_in_progress || Z_commanded_movement_in_progress;
      }
    }
    if (Y_commanded_movement_in_progress && !is_homing_Y) // homing is handled separately
    {
      uint8_t event = tmc4361A_readSwitchEvent(&tmc4361[y]);
      //if( tmc4361A_readLimitSwitches(&tmc4361[y])==LEFT_SW || tmc4361A_readLimitSwitches(&tmc4361[y])==RGHT_SW )
      if ( ( Y_direction == LEFT_DIR && event == LEFT_SW ) || ( Y_direction == RGHT_DIR && event == RGHT_SW ) )
      {
        Y_commanded_movement_in_progress = false;
        mcu_cmd_execution_in_progress = false || X_commanded_movement_in_progress || Z_commanded_movement_in_progress;
      }
    }
    if (Z_commanded_movement_in_progress && !is_homing_Z) // homing is handled separately
    {
      uint8_t event = tmc4361A_readSwitchEvent(&tmc4361[z]);
      // if( tmc4361A_readLimitSwitches(&tmc4361[z])==LEFT_SW || tmc4361A_readLimitSwitches(&tmc4361[z])==RGHT_SW )
      if ( ( Z_direction == LEFT_DIR && event == LEFT_SW ) || ( Z_direction == RGHT_DIR && event == RGHT_SW ) )
      {
        Z_commanded_movement_in_progress = false;
        mcu_cmd_execution_in_progress = false || X_commanded_movement_in_progress || Y_commanded_movement_in_progress;
      }
    }
  }
}

/***************************************************

                    timer interrupt

 ***************************************************/

// timer interrupt
/*
  // IntervalTimer stops working after SPI.begin()
  void timer_interruptHandler()
  {
  SerialUSB.println("timer event");
  counter_send_pos_update = counter_send_pos_update + 1;
  if(counter_send_pos_update==interval_send_pos_update/TIMER_PERIOD)
  {
    flag_send_pos_update = true;
    counter_send_pos_update = 0;
    SerialUSB.println("send pos update");
  }
  }
*/

/***************************************************************************************************/
/*********************************************  utils  *********************************************/
/***************************************************************************************************/
long signed2NBytesUnsigned(long signedLong, int N)
{
  long NBytesUnsigned = signedLong + pow(256L, N) / 2;
  //long NBytesUnsigned = signedLong + 8388608L;
  return NBytesUnsigned;
}

static inline int sgn(int val) {
  if (val < 0) return -1;
  if (val == 0) return 0;
  return 1;
}

/***************************************************************************************************/
/*******************************************  LED Array  *******************************************/
/***************************************************************************************************/
void set_all(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  for (int i = 0; i < DOTSTAR_NUM_LEDS; i++)
    matrix[i].setRGB(r, g, b);
}

void set_left(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  for (int i = 0; i < DOTSTAR_NUM_LEDS / 2; i++)
    matrix[i].setRGB(r, g, b);
}

void set_right(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  for (int i = DOTSTAR_NUM_LEDS / 2; i < DOTSTAR_NUM_LEDS; i++)
    matrix[i].setRGB(r, g, b);
}

void set_top(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  static const int LED_matrix_top[] = {
        0, 1, 2, 3,
        15, 14, 13, 12,
        16, 17, 18, 19, 20, 21,
        39, 38, 37, 36, 35, 34,
        40, 41, 42, 43, 44, 45,
        63, 62, 61, 60, 59, 58,
        64, 65, 66, 67, 68, 69,
        87, 86, 85, 84, 83, 82,
        88, 89, 90, 91, 92, 93,
        111, 110, 109, 108, 107, 106,
        112, 113, 114, 115,
        127, 126, 125, 124};
  for (int i = 0; i < 64; i++)
    matrix[LED_matrix_top[i]].setRGB(r,g,b);
}

void set_bottom(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  static const int LED_matrix_bottom[] = {
        4, 5, 6, 7,
        11, 10, 9, 8,
        22, 23, 24, 25, 26, 27,
        33, 32, 31, 30, 29, 28,
        46, 47, 48, 49, 50, 51,
        57, 56, 55, 54, 53, 52,
        70, 71, 72, 73, 74, 75,
        81, 80, 79, 78, 77, 76,
        94, 95, 96, 97, 98, 99,
        105, 104, 103, 102, 101, 100,
        116, 117, 118, 119,
        123, 122, 121, 120};
  for (int i = 0; i < 64; i++)
    matrix[LED_matrix_bottom[i]].setRGB(r,g,b);
}

void set_low_na(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  // matrix[44].setRGB(r,g,b);
  matrix[45].setRGB(r, g, b);
  matrix[46].setRGB(r, g, b);
  // matrix[47].setRGB(r,g,b);
  matrix[56].setRGB(r, g, b);
  matrix[57].setRGB(r, g, b);
  matrix[58].setRGB(r, g, b);
  matrix[59].setRGB(r, g, b);
  matrix[68].setRGB(r, g, b);
  matrix[69].setRGB(r, g, b);
  matrix[70].setRGB(r, g, b);
  matrix[71].setRGB(r, g, b);
  // matrix[80].setRGB(r,g,b);
  matrix[81].setRGB(r, g, b);
  matrix[82].setRGB(r, g, b);
  // matrix[83].setRGB(r,g,b);
}

void set_left_dot(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  matrix[3].setRGB(r, g, b);
  matrix[4].setRGB(r, g, b);
  matrix[11].setRGB(r, g, b);
  matrix[12].setRGB(r, g, b);
}

void set_right_dot(CRGB * matrix, uint8_t r, uint8_t g, uint8_t b)
{
  matrix[115].setRGB(r, g, b);
  matrix[116].setRGB(r, g, b);
  matrix[123].setRGB(r, g, b);
  matrix[124].setRGB(r, g, b);
}

void clear_matrix(CRGB * matrix)
{
  for (int i = 0; i < DOTSTAR_NUM_LEDS; i++)
    matrix[i].setRGB(0, 0, 0);
  FastLED.show();
}

void turn_on_LED_matrix_pattern(CRGB * matrix, int pattern, uint8_t led_matrix_r, uint8_t led_matrix_g, uint8_t led_matrix_b)
{

  led_matrix_r = (float(led_matrix_r) / 255) * LED_MATRIX_MAX_INTENSITY;
  led_matrix_g = (float(led_matrix_g) / 255) * LED_MATRIX_MAX_INTENSITY;
  led_matrix_b = (float(led_matrix_b) / 255) * LED_MATRIX_MAX_INTENSITY;

  // clear matrix
  set_all(matrix, 0, 0, 0);

  switch (pattern)
  {
    case ILLUMINATION_SOURCE_LED_ARRAY_FULL:
      set_all(matrix, led_matrix_g * GREEN_ADJUSTMENT_FACTOR, led_matrix_r * RED_ADJUSTMENT_FACTOR, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_HALF:
      set_left(matrix, led_matrix_g * GREEN_ADJUSTMENT_FACTOR, led_matrix_r * RED_ADJUSTMENT_FACTOR, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_HALF:
      set_right(matrix, led_matrix_g * GREEN_ADJUSTMENT_FACTOR, led_matrix_r * RED_ADJUSTMENT_FACTOR, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFTB_RIGHTR:
      set_left(matrix, 0, 0, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      set_right(matrix, 0, led_matrix_r * RED_ADJUSTMENT_FACTOR, 0);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LOW_NA:
      set_low_na(matrix, led_matrix_g * GREEN_ADJUSTMENT_FACTOR, led_matrix_r * RED_ADJUSTMENT_FACTOR, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_LEFT_DOT:
      set_left_dot(matrix, led_matrix_g * GREEN_ADJUSTMENT_FACTOR, led_matrix_r * RED_ADJUSTMENT_FACTOR, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_RIGHT_DOT:
      set_right_dot(matrix, led_matrix_g * GREEN_ADJUSTMENT_FACTOR, led_matrix_r * RED_ADJUSTMENT_FACTOR, led_matrix_b * BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_TOP_HALF:
      set_top(matrix, led_matrix_g*GREEN_ADJUSTMENT_FACTOR, led_matrix_r*RED_ADJUSTMENT_FACTOR, led_matrix_b*BLUE_ADJUSTMENT_FACTOR);
      break;
    case ILLUMINATION_SOURCE_LED_ARRAY_BOTTOM_HALF:
      set_bottom(matrix, led_matrix_g*GREEN_ADJUSTMENT_FACTOR, led_matrix_r*RED_ADJUSTMENT_FACTOR, led_matrix_b*BLUE_ADJUSTMENT_FACTOR);
      break;
  }
  FastLED.show();
}
