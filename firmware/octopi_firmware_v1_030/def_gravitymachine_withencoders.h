// LED matrix
#define DOTSTAR_NUM_LEDS 128

// Joystick
static const bool ENABLE_JOYSTICK = true;
constexpr int joystickSensitivity = 75; // for comparison with number in the range of 0-512

// Motorized stage
static const int FULLSTEPS_PER_REV_X = 200; // x axis
static const int FULLSTEPS_PER_REV_Y = 200; // theta axis
static const int FULLSTEPS_PER_REV_Z = 200; // y axis

static const float SCREW_PITCH_X_MM = 1; // x axis
static const float SCREW_PITCH_Z_MM = 1; // y axis

static const int MICROSTEPPING_DEFAULT_X = 8;
static const int MICROSTEPPING_DEFAULT_Y = 8;
static const int MICROSTEPPING_DEFAULT_Z = 8;

static const float HOMING_VELOCITY_X = 0.5;
static const float HOMING_VELOCITY_Y = 0.5;
static const float HOMING_VELOCITY_Z = 0.5;

static const long steps_per_mm_X = FULLSTEPS_PER_REV_X*MICROSTEPPING_DEFAULT_X/SCREW_PITCH_X_MM; // x axis
static const long steps_per_mm_Y = (99.5075*FULLSTEPS_PER_REV_Y*MICROSTEPPING_DEFAULT_Y)/(2*3.14159265*100); // theta axis - 253.39 usteps/mm => 3.95 um per ustep
static const long steps_per_mm_Z = FULLSTEPS_PER_REV_Z*MICROSTEPPING_DEFAULT_Z/SCREW_PITCH_Z_MM; // y axis

constexpr float MAX_VELOCITY_X_mm = 20; // x axis
constexpr float MAX_VELOCITY_Y_mm = 20; // theta axis
constexpr float MAX_VELOCITY_Z_mm = 20;  // y axis
constexpr float MAX_ACCELERATION_X_mm = 200;
constexpr float MAX_ACCELERATION_Y_mm = 200;
constexpr float MAX_ACCELERATION_Z_mm = 200;
static const long X_NEG_LIMIT_MM = -50; // x axis
static const long X_POS_LIMIT_MM = 50;	// x axis
static const long Y_NEG_LIMIT_MM = -8475013; // 2,147,483,648/253.39 = 8475013.40;
static const long Y_POS_LIMIT_MM = 8475013;  // 2,147,483,647/253.39 = 8475013.40;
static const long Z_NEG_LIMIT_MM = -10; // y axis
static const long Z_POS_LIMIT_MM = 10;  // y axis

// encoder
bool X_use_encoder = true;
bool Y_use_encoder = true;
bool Z_use_encoder = true;
