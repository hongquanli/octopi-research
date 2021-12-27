// LED matrix
#define DOTSTAR_NUM_LEDS 128

// Joystick
static const bool ENABLE_JOYSTICK = true;
constexpr int joystickSensitivity = 75; // for comparison with number in the range of 0-512

// Motorized stage
static const int FULLSTEPS_PER_REV_X = 200;
static const int FULLSTEPS_PER_REV_Y = 200;
static const int FULLSTEPS_PER_REV_Z = 200;
static const int FULLSTEPS_PER_REV_THETA = 200;

float SCREW_PITCH_X_MM = 1;
float SCREW_PITCH_Y_MM = 1;
float SCREW_PITCH_Z_MM = 0.012*25.4;

int MICROSTEPPING_X = 8;
int MICROSTEPPING_Y = 8;
int MICROSTEPPING_Z = 8;

static const float HOMING_VELOCITY_X = 0.5;
static const float HOMING_VELOCITY_Y = 0.5;
static const float HOMING_VELOCITY_Z = 0.5;

long steps_per_mm_X = FULLSTEPS_PER_REV_X*MICROSTEPPING_X/SCREW_PITCH_X_MM;
long steps_per_mm_Y = FULLSTEPS_PER_REV_Y*MICROSTEPPING_Y/SCREW_PITCH_Y_MM;
long steps_per_mm_Z = FULLSTEPS_PER_REV_Z*MICROSTEPPING_Z/SCREW_PITCH_Z_MM;

float MAX_VELOCITY_X_mm = 20;
float MAX_VELOCITY_Y_mm = 20;
float MAX_VELOCITY_Z_mm = 2;
float MAX_ACCELERATION_X_mm = 200;
float MAX_ACCELERATION_Y_mm = 200;
float MAX_ACCELERATION_Z_mm = 20;

static const long X_NEG_LIMIT_MM = -130;
static const long X_POS_LIMIT_MM = 130;
static const long Y_NEG_LIMIT_MM = -130;
static const long Y_POS_LIMIT_MM = 130;
static const long Z_NEG_LIMIT_MM = -20;
static const long Z_POS_LIMIT_MM = 20;

// nanotec size 8 linear actuators
int X_MOTOR_RMS_CURRENT_mA = 600;
int Y_MOTOR_RMS_CURRENT_mA = 600;
// haydon kerk size 8 linear actuator
int Z_MOTOR_RMS_CURRENT_mA = 490;

float X_MOTOR_I_HOLD = 0.5;
float Y_MOTOR_I_HOLD = 0.5;
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
int JOYSTICK_SIGN_X = -1;
int JOYSTICK_SIGN_Y = 1;
int JOYSTICK_SIGN_Z = 1;

// limit switch polarity
bool LIM_SWITCH_X_ACTIVE_LOW = false;
bool LIM_SWITCH_Y_ACTIVE_LOW = false;
bool LIM_SWITCH_Z_ACTIVE_LOW = false;
