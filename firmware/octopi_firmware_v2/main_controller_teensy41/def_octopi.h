// LED matrix
#define DOTSTAR_NUM_LEDS 128

// Axis assignment
static const uint8_t x = 1;
static const uint8_t y = 0;
static const uint8_t z = 2;

static const float R_sense_xy = 0.22;
static const float R_sense_z = 0.43;

// limit switch
static const bool flip_limit_switch_x = true;
static const bool flip_limit_switch_y = false;

// Motorized stage
static const int FULLSTEPS_PER_REV_X = 200;
static const int FULLSTEPS_PER_REV_Y = 200;
static const int FULLSTEPS_PER_REV_Z = 200;
static const int FULLSTEPS_PER_REV_THETA = 200;

float SCREW_PITCH_X_MM = 2.54;
float SCREW_PITCH_Y_MM = 2.54;
float SCREW_PITCH_Z_MM = 0.3;

int MICROSTEPPING_X = 256;
int MICROSTEPPING_Y = 256;
int MICROSTEPPING_Z = 256;

static const float HOMING_VELOCITY_X = 0.8;
static const float HOMING_VELOCITY_Y = 0.8;
static const float HOMING_VELOCITY_Z = 0.5;

long steps_per_mm_X = FULLSTEPS_PER_REV_X*MICROSTEPPING_X/SCREW_PITCH_X_MM;
long steps_per_mm_Y = FULLSTEPS_PER_REV_Y*MICROSTEPPING_Y/SCREW_PITCH_Y_MM;
long steps_per_mm_Z = FULLSTEPS_PER_REV_Z*MICROSTEPPING_Z/SCREW_PITCH_Z_MM;

float MAX_VELOCITY_X_mm = 30;
float MAX_VELOCITY_Y_mm = 30;
float MAX_VELOCITY_Z_mm = 2;
float MAX_ACCELERATION_X_mm = 500;
float MAX_ACCELERATION_Y_mm = 500;
float MAX_ACCELERATION_Z_mm = 20;

static const long X_NEG_LIMIT_MM = -130;
static const long X_POS_LIMIT_MM = 130;
static const long Y_NEG_LIMIT_MM = -130;
static const long Y_POS_LIMIT_MM = 130;
static const long Z_NEG_LIMIT_MM = -20;
static const long Z_POS_LIMIT_MM = 20;

// size 11 lead screw motors
float X_MOTOR_RMS_CURRENT_mA = 1000;
float Y_MOTOR_RMS_CURRENT_mA = 1000;
// Ding's motion size 8 linear actuator
float Z_MOTOR_RMS_CURRENT_mA = 500;

float X_MOTOR_I_HOLD = 0.25;
float Y_MOTOR_I_HOLD = 0.25;
float Z_MOTOR_I_HOLD = 0.5;

// encoder
bool X_use_encoder = false;
bool Y_use_encoder = false;
bool Z_use_encoder = false;

// signs
int MOVEMENT_SIGN_X = 1;    // not used for now
int MOVEMENT_SIGN_Y = 1;    // not used for now
int MOVEMENT_SIGN_Z = 1;    // not used for now
int ENCODER_SIGN_X = 1;     // not used for now
int ENCODER_SIGN_Y = 1;     // not used for now
int ENCODER_SIGN_Z = 1;     // not used for now
int JOYSTICK_SIGN_X = 1;
int JOYSTICK_SIGN_Y = -1;
int JOYSTICK_SIGN_Z = 1;

// limit switch polarity
bool LIM_SWITCH_X_ACTIVE_LOW = false;
bool LIM_SWITCH_Y_ACTIVE_LOW = false;
bool LIM_SWITCH_Z_ACTIVE_LOW = false;

// offset velocity enable/disable
bool enable_offset_velocity = false;
