// LED matrix
#define DOTSTAR_NUM_LEDS 128

// Joystick
static const bool ENABLE_JOYSTICK = true;
constexpr int joystickSensitivity = 75; // for comparison with number in the range of 0-512

// Motorized stage
static const int FULLSTEPS_PER_REV_X = 200; // x axis
static const int FULLSTEPS_PER_REV_Y = 200; // theta axis
static const int FULLSTEPS_PER_REV_Z = 200; // y axis

float SCREW_PITCH_X_MM = 1; // x axis
float SCREW_PITCH_Z_MM = 1; // y axis (focus axis)
float SCREW_PITCH_Y_MM = 6.31; // z axis

int MICROSTEPPING_X = 8;
int MICROSTEPPING_Y = 8;
int MICROSTEPPING_Z = 8;

static const float HOMING_VELOCITY_X = 0.5;
static const float HOMING_VELOCITY_Y = 0.5;
static const float HOMING_VELOCITY_Z = 0.5;

long steps_per_mm_X = FULLSTEPS_PER_REV_X*MICROSTEPPING_X/SCREW_PITCH_X_MM; // x axis
long steps_per_mm_Y = (99.5075*FULLSTEPS_PER_REV_Y*MICROSTEPPING_Y)/(2*3.14159265*100); // theta axis - 253.39 usteps/mm => 3.95 um per ustep
long steps_per_mm_Z = FULLSTEPS_PER_REV_Z*MICROSTEPPING_Z/SCREW_PITCH_Z_MM; // y axis
// to add: proper update of steps_per_mm_Y when MICROSTEPPING_Y or SCREW_PITCH_Y_MM is changed by the computer - when Y correspond to the theta motor

float MAX_VELOCITY_X_mm = 20; // x axis
float MAX_VELOCITY_Y_mm = 20; // theta axis
float MAX_VELOCITY_Z_mm = 20;  // y axis
float MAX_ACCELERATION_X_mm = 200;
float MAX_ACCELERATION_Y_mm = 200;
float MAX_ACCELERATION_Z_mm = 200;

static const long X_NEG_LIMIT_MM = -50; // x axis
static const long X_POS_LIMIT_MM = 50;	// x axis
static const long Y_NEG_LIMIT_MM = -8475013; // 2,147,483,648/253.39 = 8475013.40;
static const long Y_POS_LIMIT_MM = 8475013;  // 2,147,483,647/253.39 = 8475013.40;
static const long Z_NEG_LIMIT_MM = -10; // y axis
static const long Z_POS_LIMIT_MM = 10;  // y axis

// size 11 linear actuators
int X_MOTOR_RMS_CURRENT_mA = 600;
int Z_MOTOR_RMS_CURRENT_mA = 600;
// rotation stage
int Y_MOTOR_RMS_CURRENT_mA = 600;

float X_MOTOR_I_HOLD = 0.25;
float Y_MOTOR_I_HOLD = 0.5;
float Z_MOTOR_I_HOLD = 0.25;

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
