/*
   Utils.h
   Contains utilities for running the TCM4361 and TMC2660

    Created on: 7/8/2022
        Author: Kevin Marx
    
    With additions and modifications from Hongquan Li 8/3/2022
*/
#ifndef TMC_UTILS_H_
#define TMC_UTILS_H_

#include <stddef.h>
#include <stdint.h>
#include <SPI.h>
#include "TMC4361A.h"

// Functions for user-facing API
void tmc4361A_tmc2660_config(TMC4361ATypeDef *tmc4361A, float tmc2660_cscale, float tmc4361a_hold_scale_val, float tmc4361a_drv2_scale_val, float tmc4361a_drv1_scale_val, float tmc4361a_boost_scale_val, float pitch_mm, uint16_t steps_per_rev, uint16_t microsteps);
void tmc4361A_tmc2660_init(TMC4361ATypeDef *tmc4361A, uint32_t clk_Hz_TMC4361);
void tmc4361A_tmc2660_update(TMC4361ATypeDef *tmc4361A);
void tmc4361A_setMaxSpeed(TMC4361ATypeDef *tmc4361A, int32_t velocity);
void tmc4361A_setSpeed(TMC4361ATypeDef *tmc4361A, int32_t velocity);
int32_t tmc4361A_speed(TMC4361ATypeDef *tmc4361A);
int32_t tmc4361A_acceleration(TMC4361ATypeDef *tmc4361A);
int8_t tmc4361A_setMaxAcceleration(TMC4361ATypeDef *tmc4361A, uint32_t acceleration);
int8_t tmc4361A_moveTo(TMC4361ATypeDef *tmc4361A, int32_t x_pos);
int8_t tmc4361A_move(TMC4361ATypeDef *tmc4361A, int32_t x_pos);
int32_t tmc4361A_currentPosition(TMC4361ATypeDef *tmc4361A);
int32_t tmc4361A_targetPosition(TMC4361ATypeDef *tmc4361A);
int8_t tmc4361A_setCurrentPosition(TMC4361ATypeDef *tmc4361A, int32_t position);
void tmc4361A_stop(TMC4361ATypeDef *tmc4361A);
bool tmc4361A_isRunning(TMC4361ATypeDef *tmc4361A);
int32_t tmc4361A_xmmToMicrosteps(TMC4361ATypeDef *tmc4361A, float mm);
float   tmc4361A_xmicrostepsTomm(TMC4361ATypeDef *tmc4361A, int32_t microsteps);
int32_t tmc4361A_vmmToMicrosteps(TMC4361ATypeDef *tmc4361A, float mm);
float   tmc4361A_vmicrostepsTomm(TMC4361ATypeDef *tmc4361A, int32_t microsteps);
int32_t tmc4361A_ammToMicrosteps(TMC4361ATypeDef *tmc4361A, float mm);
float   tmc4361A_amicrostepsTomm(TMC4361ATypeDef *tmc4361A, int32_t microsteps);
void tmc4361A_enableLimitSwitch(TMC4361ATypeDef *tmc4361A, uint8_t polarity, uint8_t which, uint8_t flipped);
void tmc4361A_enableHomingLimit(TMC4361ATypeDef *tmc4361A, uint8_t polarity, uint8_t which);
uint8_t tmc4361A_readLimitSwitches(TMC4361ATypeDef *tmc4361A);
void tmc4361A_setHome(TMC4361ATypeDef *tmc4361A);
void tmc4361A_moveToExtreme(TMC4361ATypeDef *tmc4361A, int32_t vel, int8_t dir);
void tmc4361A_cScaleInit(TMC4361ATypeDef *tmc4361A);
void tmc4361A_setPitch(TMC4361ATypeDef *tmc4361A, float pitchval);
int8_t tmc4361A_setMicrosteps(TMC4361ATypeDef *tmc4361A, uint16_t mstep);
void tmc4361A_writeMicrosteps(TMC4361ATypeDef *tmc4361A);
int8_t tmc4361A_setSPR(TMC4361ATypeDef *tmc4361A, uint16_t spr);
void tmc4361A_writeSPR(TMC4361ATypeDef *tmc4361A);
void tmc4361A_disableVirtualLimitSwitch(TMC4361ATypeDef *tmc4361A, int dir);
void tmc4361A_enableVirtualLimitSwitch(TMC4361ATypeDef *tmc4361A, int dir);
int8_t tmc4361A_setVirtualLimit(TMC4361ATypeDef *tmc4361A, int dir, int32_t limit);


// The following does not need to be accessed by the end user
// Default motor settings - can override using tmc4361A_setPitch(), tmc4361A_setMicrosteps(), tmc4361A_setSPR()
#define DEFAULT_PITCH        (float)2.54 // carriage parameter - 1 rotation is 2.54 mm
#define DEFAULT_MICROSTEPS   256         // motor driver parameter - 1 rotation has 256 microsteps
#define DEFAULT_STEP_PER_REV 200         // motor parameter - number of steps per full revolution

// Current Scale Values - can override using tmc4361A_cScaleInit()
#define TMC2660_CSCALE           0x1F  // Current scale value on the TCM2660, ranges from 0x00 to 0x1F
#define TMC4361A_HOLD_SCALE_VAL  0xFF  // 0 to 255 
#define TMC4361A_DRV2_SCALE_VAL  0xFF
#define TMC4361A_DRV1_SCALE_VAL  0xFF
#define TMC4361A_BOOST_SCALE_VAL 0xFF
static const uint8_t TMC2660_TMC4361A_defaultCscaleval[N_CPARAM] = {TMC2660_CSCALE, TMC4361A_HOLD_SCALE_VAL, TMC4361A_DRV2_SCALE_VAL, TMC4361A_DRV1_SCALE_VAL, TMC4361A_BOOST_SCALE_VAL};

// TMC2660 register parameters
#define SGCSCONF    0x0C0000
#define SFILT       0x010000

// Error handling macros
#define NO_ERR            0
#define ERR_OUT_OF_RANGE -1
#define ERR_MISC         -2

#define LEFT_SW 0b01
#define RGHT_SW 0b10
#define LEFT_DIR -1
#define RGHT_DIR  1
#define BOWMAX ((1<<24) - 1) 
#define ACCELMAX ((1 << 24) - 1)

void tmc4361A_readWriteArray(uint8_t channel, uint8_t *data, size_t length);
void tmc4361A_setBits(TMC4361ATypeDef *tmc4361A, uint8_t address, int32_t dat);
void tmc4361A_rstBits(TMC4361ATypeDef *tmc4361A, uint8_t address, int32_t dat);
uint8_t tmc4361A_readSwitchEvent(TMC4361ATypeDef *tmc4361A);
void tmc4361A_sRampInit(TMC4361ATypeDef *tmc4361A);
void tmc4361A_setSRampParam(TMC4361ATypeDef *tmc4361A, uint8_t idx, int32_t param);
void tmc4361A_adjustBows(TMC4361ATypeDef *tmc4361A);

#endif /* TMC_UTILS_H_ */
