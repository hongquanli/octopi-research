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

static const float SCREW_PITCH_X_MM = 1;
static const float SCREW_PITCH_Y_MM = 1;
static const float SCREW_PITCH_Z_MM = 0.012*25.4;

static const int MICROSTEPPING_DEFAULT_X = 8;
static const int MICROSTEPPING_DEFAULT_Y = 8;
static const int MICROSTEPPING_DEFAULT_Z = 8;
static const int MICROSTEPPING_DEFAULT_THETA = 8;

static const float HOMING_VELOCITY_X = 0.5;
static const float HOMING_VELOCITY_Y = 0.5;
static const float HOMING_VELOCITY_Z = 0.5;

static const long steps_per_mm_X = FULLSTEPS_PER_REV_X*MICROSTEPPING_DEFAULT_X/SCREW_PITCH_X_MM;
static const long steps_per_mm_Y = FULLSTEPS_PER_REV_Y*MICROSTEPPING_DEFAULT_Y/SCREW_PITCH_Y_MM;
static const long steps_per_mm_Z = FULLSTEPS_PER_REV_Z*MICROSTEPPING_DEFAULT_Z/SCREW_PITCH_Z_MM;

constexpr float MAX_VELOCITY_X_mm = 20;
constexpr float MAX_VELOCITY_Y_mm = 20;
constexpr float MAX_VELOCITY_Z_mm = 2;
constexpr float MAX_ACCELERATION_X_mm = 200;  // 50 mm/s/s
constexpr float MAX_ACCELERATION_Y_mm = 200;  // 50 mm/s/s
constexpr float MAX_ACCELERATION_Z_mm = 20;   // 20 mm/s/s
static const long X_NEG_LIMIT_MM = -130;
static const long X_POS_LIMIT_MM = 130;
static const long Y_NEG_LIMIT_MM = -130;
static const long Y_POS_LIMIT_MM = 130;
static const long Z_NEG_LIMIT_MM = -20;
static const long Z_POS_LIMIT_MM = 20;

// encoder
bool X_use_encoder = false;
bool Y_use_encoder = false;
bool Z_use_encoder = false;
