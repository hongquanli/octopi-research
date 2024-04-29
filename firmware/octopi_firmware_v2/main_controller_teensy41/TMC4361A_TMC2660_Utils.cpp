/*
   Utils.cpp
   This file contains higher-level functions for interacting with the TMC4362A.
   Some functions are low-level helpers and do not need to be accessed directly by the user
    User-facing functions:
      tmc4361A_tmc2660_init:   Initialize the tmc4361A and tmc2660
          Arguments: TMC4361ATypeDef *tmc4361A, uint32_t clk_Hz_TMC4361
      tmc4361A_setMaxSpeed:             Write the target velocity to the tmc4361A in units microsteps per second and recalculates bow values
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t velocity
      tmc4361A_setSpeed:                Start moving at a constant speed in units microsteps per second
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t velocity
      tmc4361A_init_ABN_encoder:            Initialize an incremental ABN encoder with a given resolution and filter parameters
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t enc_res, uint8_t filter_wait_time, uint8_t filter_exponent, uint16_t filter_vmean
      tmc4361A_init_calib_feedback:     Initialize the encoder feedback and run calibration
          Arguments: (TMC4361ATypeDef *tmc4361A, int32_t enc_res);
      read_feedback_flag:               Returns the feedback error flags
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_speed:                   Returns the current speed in microsteps per second
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_acceleration:            Returns the current acceleration in microsteps per second^2
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_setMaxAcceleration:      Write the maximum acceleration in units microsteps per second squared and recalculates bow values
          Arguments: TMC4361ATypeDef *tmc4361A, uint32_t acceleration
      tmc4361A_moveTo:                  Move to the target absolute position in units microsteps
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t x_pos
      tmc4361A_move:                    Move to a position relative to the current position in units microsteps
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t x_pos
      tmc4361A_currentPosition:         Return the current position in units microsteps
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_targetPosition:          Return the target position in units microsteps
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_setCurrentPosition:      Set the current position to a specific value in units microsteps
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t position
      tmc4361A_stop:                    Halt operation by setting the target position to the current position
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_isRunning:               Returns true if the motor is moving
          Arguments: TMC4361ATypeDef *tmc4361A, bool pid_enable
      tmc4361A_xmmToMicrosteps:         Convert from millimeters to units microsteps for position and jerk values
          Arguments: TMC4361ATypeDef *tmc4361A, float mm
      tmc4361A_xmicrostepsTomm:         Convert from microsteps to units millimeters for position and jerk values
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t microsteps
      tmc4361A_vmmToMicrosteps:         Convert from millimeters to units microsteps for velocity values
          Arguments: TMC4361ATypeDef *tmc4361A, float mm
      tmc4361A_vmicrostepsTomm:         Convert from microsteps to units millimeters for velocity values
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t microsteps
      tmc4361A_ammToMicrosteps:         Convert from millimeters to units microsteps for acceleration values
          Arguments: TMC4361ATypeDef *tmc4361A, float mm
      tmc4361A_amicrostepsTomm:         Convert from microsteps to units millimeters for acceleration values
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t microsteps
      tmc4361A_enableLimitSwitch:       Enables reading from limit switches and using limit switches as automatic stop indicators.
          Arguments: TMC4361ATypeDef *tmc4361A, uint8_t polarity, uint8_t which
      tmc4361A_enableHomingLimit:       Enables using the limit switch or homing
          Arguments: TMC4361ATypeDef *tmc4361A, uint8_t sw, uint8_t pol_lft, uint8_t pol_rht
      tmc4361A_readLimitSwitches:       Read limit switch current state
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_moveToExtreme:           Go all the way left or right
          Arguments: TMC4361ATypeDef *tmc4361A, int32_t vel, int8_t dir
      tmc4361A_setHome:                 Set current location as home
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_cScaleInit:              Initialize current scale values.
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_setPitch:                Set the pitch (mm of travel per motor rotation)
          Arguments: TMC4361ATypeDef *tmc4361A, float pitchval
      tmc4361A_setMicrosteps:           Set the number of microsteps per fullstep, must be a power of 2 between 1 and 256 inclusive
          Arguments: TMC4361ATypeDef *tmc4361A, uint16_t mstep
      tmc4361A_setSPR:                  Set the motor's steps per revolution, typically 200
          Arguments: TMC4361ATypeDef *tmc4361A, uint16_t spr
      tmc4361A_writeMicrosteps:         Write the number of microsteps per fullstep to the motor driver
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_writeSPR:                  Write the number of steps per revolution to the motor driver
          Arguments: TMC4361ATypeDef *tmc4361A

    For internal use:
      tmc4361A_readWriteArray: Used for low-level SPI communication with the TMC4361A
          Arguments: uint8_t channel, uint8_t *data, size_t length
      tmc4361A_setBits:        Implements some of the features of tmc4361A_readWriteCover in an easier to use way; it sets bits in a register without disturbing the other bits
          Arguments: TMC4361ATypeDef *tmc4361A, uint8_t address, int32_t dat
      tmc4361A_rstBits:        Implements some of the features of tmc4361A_readWriteCover in an easier to use way; it clears bits in a register without disturbing the other bits
          Arguments: TMC4361ATypeDef *tmc4361A, uint8_t address, int32_t dat
      tmc4361A_readSwitchEvent:         Read events created by the limit switches
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_sRampInit:               Write all parameters for the s-shaped ramp
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_cScaleInit:              Write all parameters for current scaling
          Arguments: TMC4361ATypeDef *tmc4361A
      tmc4361A_setSRampParam:           Set and write an individual parameter for the s-shaped ramp
          Arguments: TMC4361ATypeDef *tmc4361A, uint8_t idx, int32_t param
      tmc4361A_adjustBows:              Sets shared bow values based on velocity and acceleration
          Arguments: TMC4361ATypeDef *tmc4361A
*/
#include "TMC4361A_TMC2660_Utils.h"

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_readWriteArray() sends a number of bytes to a target device over SPI. Functions in TMC4316A.cpp depend on this function.

  OPERATION:   This function mediates a SPI transaction by first setting the CS pin of the target device low, then sending bytes from an array one at a time over SPI and storing the data back into the original array. Once the transaction is over, the CS pin is brought high again.

  ARGUMENTS:
      uint8_t channel: CS pin number
      uint8_t *data:   Pointer to data array
      size_t length:   Number of bytes in the data array

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      uint8_t *data: Values in this array are overwritten

  GLOBAL VARIABLES: None

  DEPENDENCIES: SPI.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_readWriteArray(uint8_t channel, uint8_t *data, size_t length) {
  // Initialize SPI transfer
  SPI.beginTransaction(SPISettings(500000, MSBFIRST, SPI_MODE0));
  digitalWrite(channel, LOW);
  delayMicroseconds(100);
  // Write each byte and overwrite data[] with the response
  for (size_t i = 0; i < length; i++) {
    data[i] = SPI.transfer(data[i]);
  }
  // End the transaction
  digitalWrite(channel, HIGH);
  SPI.endTransaction();
  return;
}


/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setBits() sets bits in a register without affecting the other bits.

  OPERATION:   We first read the register data then OR the register with the bits we want to set. Then, it writes the data to the address.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t address:           Address of the register we want to write to
      int32_t dat:               Data we want to write to the array

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      int32_t datagram: Used to hold both the data read from the register and the data we want to write to the register

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_setBits(TMC4361ATypeDef *tmc4361A, uint8_t address, int32_t dat) {
  // Set the bits in dat without disturbing any other bits in the register
  // Read the bits already there
  int32_t datagram = tmc4361A_readInt(tmc4361A, address);
  // OR with the bits we want to set
  datagram |= dat;
  // Write
  tmc4361A_writeInt(tmc4361A, address, datagram);

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_rstBits() clears bits in a register without affecting the other bits.

  OPERATION:   We first read the register data then AND the register with the negation of bits we want to set. Then, it writes the data to the address.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t address:           Address of the register we want to write to
      int32_t dat:               Data we want to write to the array

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      int32_t datagram: Used to hold both the data read from the register and the data we want to write to the register

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_rstBits(TMC4361ATypeDef *tmc4361A, uint8_t address, int32_t dat) {
  // Reset the bits in dat without disturbing any other bits in the register
  // Read the bits already there
  int32_t datagram = tmc4361A_readInt(tmc4361A, address);
  // AND with the bits with the negation of the bits we want to clear
  datagram &= ~dat;
  // Write
  tmc4361A_writeInt(tmc4361A, address, datagram);

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_cScaleInit() writes current scale parameters to the TCM4361A and TMC2660

  OPERATION:   We first write the current scale to the TMC2660 then write hold, drive, and boost scale parameters to the TCM4361A. The values being written are stored in *tmc4361A.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: Sends signals ove MOSI/MISO; the motor should not move

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_cScaleInit(TMC4361ATypeDef *tmc4361A) {
  tmc4361A_writeInt(tmc4361A, TMC4361A_COVER_LOW_WR, SGCSCONF | SFILT | tmc4361A->cscaleParam[CSCALE_IDX]);
  // current open loop scaling
  tmc4361A_writeInt(tmc4361A, TMC4361A_SCALE_VALUES, (tmc4361A->cscaleParam[HOLDSCALE_IDX] << TMC4361A_HOLD_SCALE_VAL_SHIFT) +   // Set hold scale value (0 to 255)
                    (tmc4361A->cscaleParam[DRV2SCALE_IDX] << TMC4361A_DRV2_SCALE_VAL_SHIFT) +   // Set DRV2 scale  (0 to 255)
                    (tmc4361A->cscaleParam[DRV1SCALE_IDX] << TMC4361A_DRV1_SCALE_VAL_SHIFT) +   // Set DRV1 scale  (0 to 255)
                    (tmc4361A->cscaleParam[BSTSCALE_IDX]  << TMC4361A_BOOST_SCALE_VAL_SHIFT));  // Set boost scale (0 to 255)
  tmc4361A_setBits(tmc4361A, TMC4361A_CURRENT_CONF, TMC4361A_DRIVE_CURRENT_SCALE_EN_MASK); // keep drive current scale
  tmc4361A_setBits(tmc4361A, TMC4361A_CURRENT_CONF, TMC4361A_HOLD_CURRENT_SCALE_EN_MASK);  // keep hold current scale

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setPitch() sets screw pitch for the screw attached to the motor.

  OPERATION:   We write the value in the argument to the motor driver struct

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      float pitchval:            Number of millimeteres traveled per full motor revolution

  RETURNS: None

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_setPitch(TMC4361ATypeDef *tmc4361A, float pitchval) {
  tmc4361A->threadPitch = pitchval;
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_writeMicrosteps() writes the number of microsteps per fullstep to the motor controller.

  OPERATION:   We first check if the mstep argument is a power of 2. We set an error flag if it is not.
               We then convert the microsteps number to the correct format for the tmc4361A: 256 -> 0, 128 -> 1, ..., 1 -> 8.
               This conversion is performed by shifting mstep down a bit and incrementing bitsSet until mstep is equal to 0. This is equivalent to evaluating log_2(mstep)+1. Then we calculate 9-bitsSet to convert to the proper format.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint16_t mstep:            Number of microsteps in one full step

  RETURNS: none

  INPUTS / OUTPUTS: Sends signals ove MOSI/MISO; the motor should not move

  LOCAL VARIABLES:
      int8_t err:          indicates whether the operation was successful
      uint8_t bitsSet:     Holds which bits to set on the tmc4361A
      uint16_t microsteps: Holds a copy of microsteps

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_writeMicrosteps(TMC4361ATypeDef *tmc4361A) {
  int8_t err = NO_ERR; // Initally assume mstep is valid
  uint8_t  bitsSet = 0;
  uint16_t mstep = tmc4361A->microsteps;
  // Check if mstep is a valid microstep value (a power of 2 between 1 and 256 inclusive)
  if ((mstep != 0) && !(mstep & (mstep - 1)) && (mstep <= 256)) {
    // Clear the low 4 bits of STEP_CONF to prepare it for writing to
    tmc4361A_rstBits(tmc4361A, TMC4361A_STEP_CONF, 0b1111);
  }
  else {
    // If it's not valid, mark all the bits as invalid
    mstep = 0;
    err = ERR_OUT_OF_RANGE;
  }

  while (mstep > 0) {
    bitsSet++;
    mstep = mstep >> 1;
  }

  bitsSet = 9 - bitsSet;
  if (err == NO_ERR) {
    tmc4361A_setBits(tmc4361A, TMC4361A_STEP_CONF, bitsSet);
  }

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setMicrosteps() sets microsteps per fullstep for the motor.

  OPERATION:   We write the value in the argument to the motor driver struct

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint16_t mstep:            microsteps per fullstep

  RETURNS: None

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_setMicrosteps(TMC4361ATypeDef *tmc4361A, uint16_t mstep) {
  // Ensure mstep is a power of 2 and within bounds
  if ((mstep != 0) && !(mstep & (mstep - 1)) && (mstep <= 256)) {
    tmc4361A->microsteps = mstep;
    return NO_ERR;
  }
  else {
    return ERR_OUT_OF_RANGE;
  }
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setSPR() sets steps-per-revolution for the motor.

  OPERATION:   We write the value in the argument to the motor driver struct

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint16_t spr:              Steps per revolution

  RETURNS: None

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_setSPR(TMC4361ATypeDef *tmc4361A, uint16_t spr) {
  if (spr > ((1 << 12) - 1)) { // spr is a 12 bit number
    return ERR_OUT_OF_RANGE;
  }
  else {
    tmc4361A->stepsPerRev = spr;
    return NO_ERR;
  }
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_writeSPR() writes steps-per-revolution for the motor to the motor driver.

  OPERATION:   We read the value in the motor driver struct, format it, and send it to the motor driver

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_writeSPR(TMC4361ATypeDef *tmc4361A) {
  tmc4361A_rstBits(tmc4361A, TMC4361A_STEP_CONF, TMC4361A_FS_PER_REV_MASK);
  tmc4361A_setBits(tmc4361A, TMC4361A_STEP_CONF, tmc4361A->stepsPerRev << TMC4361A_FS_PER_REV_SHIFT);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_tmc2660_init() initializes the tmc4361A and tmc2660

  OPERATION:   We write several bytes to the two ICs to configure their behaviors.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint32_t clk_Hz_TMC4361:   Clock frequency we are driving the ICs at

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_tmc2660_init(TMC4361ATypeDef *tmc4361A, uint32_t clk_Hz_TMC4361) {
  // reset
  tmc4361A_writeInt(tmc4361A, TMC4361A_RESET_REG, 0x52535400);
  // clk
  tmc4361A_writeInt(tmc4361A, TMC4361A_CLK_FREQ, clk_Hz_TMC4361);
  // SPI configuration
  tmc4361A_writeInt(tmc4361A, TMC4361A_SPIOUT_CONF, 0x4440108A);
  // cover datagram for TMC2660
  tmc4361A_writeInt(tmc4361A, TMC4361A_COVER_LOW_WR, 0x000900C3);
  tmc4361A_writeInt(tmc4361A, TMC4361A_COVER_LOW_WR, 0x000A0000);
  tmc4361A_writeInt(tmc4361A, TMC4361A_COVER_LOW_WR, 0x000C000A);
  tmc4361A_writeInt(tmc4361A, TMC4361A_COVER_LOW_WR, 0x000E00A0); // SDOFF = 1 -> SPI mode
  // current scaling
  tmc4361A_cScaleInit(tmc4361A);
  // microstepping setting
  tmc4361A_writeMicrosteps(tmc4361A);
  tmc4361A_writeSPR(tmc4361A);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_tmc2660_update() update the tmc4361A and tmc2660 settings (current scaling and microstepping settings)

  OPERATION:   We write several bytes to the two ICs to configure their behaviors.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_tmc2660_update(TMC4361ATypeDef *tmc4361A) {
  // current scaling
  tmc4361A_cScaleInit(tmc4361A);
  // microstepping setting
  tmc4361A_writeMicrosteps(tmc4361A);
  tmc4361A_writeSPR(tmc4361A);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_tmc2660_config() configures the parameters for tmc4361A and tmc2660
  OPERATION:   set parameters
  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      float tmc2660_cscale: 0-1
      float tmc4361a_hold_scale_val: 0-1
      float tmc4361a_drv2_scale_val: 0-1
      float tmc4361a_drv1_scale_val: 0-1
      float tmc4361a_boost_scale_val: maximum current during the boost phase (in certain sections of the velocity ramp it can be useful to boost the current), 0-1
      float pitch_mm: mm traveled per full motor revolution
      uint16_t steps_per_rev: full steps per rev
      uint16_t microsteps: number of microsteps per fullstep. must be a power of 2 from 1 to 256.
      uint8_t dac_idx: DAC associated with this stage. Set to NO_DAC of there isn't one
      uint32_t dac_fullscale_msteps: abs(mstep when voltage set to 0 - mstep when voltage set to 5V); used for setting the position using the piezo
  RETURNS: None
  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively
  LOCAL VARIABLES: None
  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct
  GLOBAL VARIABLES: None
  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_tmc2660_config(TMC4361ATypeDef *tmc4361A, float tmc2660_cscale, float tmc4361a_hold_scale_val, float tmc4361a_drv2_scale_val, float tmc4361a_drv1_scale_val, float tmc4361a_boost_scale_val, float pitch_mm, uint16_t steps_per_rev, uint16_t microsteps, uint8_t dac_idx, uint32_t dac_fullscale_msteps) {

  tmc4361A->cscaleParam[0] = uint8_t(tmc2660_cscale * 31);
  tmc4361A->cscaleParam[1] = uint8_t(tmc4361a_hold_scale_val * 255);
  tmc4361A->cscaleParam[2] = uint8_t(tmc4361a_drv2_scale_val * 255);
  tmc4361A->cscaleParam[3] = uint8_t(tmc4361a_drv1_scale_val * 255);
  tmc4361A->cscaleParam[4] = uint8_t(tmc4361a_boost_scale_val * 255);
  tmc4361A_setPitch(tmc4361A, pitch_mm);
  tmc4361A_setSPR(tmc4361A, steps_per_rev);
  tmc4361A_setMicrosteps(tmc4361A, microsteps);

  tmc4361A->dac_idx = dac_idx;
  tmc4361A->dac_fullscale_msteps = dac_fullscale_msteps;

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_enableLimitSwitch() enables either the left or right

  OPERATION:   We format the switch polarity variables into a datagram and send it to the tmc4361. We then enable position latching when the limit switch is hit

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t polarity:          Polarity of the switch - 0 if active low, 1 if active high
      uint8_t which:             either LEFT_SW or RGHT_SW - which switch to enable
      uint8_t flipped:           if flipped is 1, treat the left/right switches for this motor the opposite way. For example, if which = LEFT_SW and flipped = 1 then the right switch will be initialized and behave as though it was the left switch.

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      uint32_t pol_datagram, en_datagram: store datagrams to write to the tmc4361.

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_enableLimitSwitch(TMC4361ATypeDef *tmc4361A, uint8_t polarity, uint8_t which, uint8_t flipped) {
  polarity &= 1; // mask off unwanted bits
  uint32_t pol_datagram;
  uint32_t en_datagram;
  // Handle case where the switches are flipped
  if (flipped != 0) {
    tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_INVERT_STOP_DIRECTION_MASK);
  }
  // Determine what to do based on which switch to enable
  switch (which) {
    case LEFT_SW:
      // Set whether they are low active (set bit to 0) or high active (1)
      pol_datagram = (polarity << TMC4361A_POL_STOP_LEFT_SHIFT);
      en_datagram = TMC4361A_STOP_LEFT_EN_MASK;
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, pol_datagram);
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, en_datagram);
      // store position when we hit left bound
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_LATCH_X_ON_ACTIVE_L_MASK);
      break;
    case RGHT_SW:
      // Set whether they are low active (set bit to 0) or high active (1)
      pol_datagram = (polarity << TMC4361A_POL_STOP_RIGHT_SHIFT);
      en_datagram = TMC4361A_STOP_RIGHT_EN_MASK;
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, pol_datagram);
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, en_datagram);
      // store position when we hit right bound
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_LATCH_X_ON_ACTIVE_R_MASK);
      break;
  }
  return;
}

void tmc4361A_setVirtualStop(TMC4361ATypeDef *tmc4361A, uint8_t which, int32_t target) {
  // Set VIRTUAL_STOP_[LEFT/RIGHT] with stop position in microsteps
  uint8_t address = (which == LEFT_SW) ? TMC4361A_VIRT_STOP_LEFT : TMC4361A_VIRT_STOP_RIGHT;
  tmc4361A_writeInt(tmc4361A, address, target);
  // Set virtual_[left/right]_limit_en = 1 in REFERENCE_CONF
  int32_t dat = (which == LEFT_SW) ? (1 << TMC4361A_VIRTUAL_LEFT_LIMIT_EN_SHIFT) : (1 << TMC4361A_VIRTUAL_RIGHT_LIMIT_EN_SHIFT);
  tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, dat);

  return;
}

// vitual limit switch - to add doc
void tmc4361A_enableVirtualLimitSwitch(TMC4361ATypeDef *tmc4361A, int dir) {
  uint32_t en_datagram;
  // Determine what to do based on which switch to enable
  switch (dir) {
    case -1:
      en_datagram = TMC4361A_VIRTUAL_LEFT_LIMIT_EN_MASK + (1<<TMC4361A_VIRT_STOP_MODE_SHIFT); // hard stop
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, en_datagram);
      break;
    case 1:
      en_datagram = TMC4361A_VIRTUAL_RIGHT_LIMIT_EN_MASK + (1<<TMC4361A_VIRT_STOP_MODE_SHIFT); // hard stop
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, en_datagram);
      break;
  }
  return;
}
void tmc4361A_disableVirtualLimitSwitch(TMC4361ATypeDef *tmc4361A, int dir) {
  uint32_t en_datagram;
  // Determine what to do based on which switch to enable
  switch (dir) {
    case -1:
      en_datagram = TMC4361A_VIRTUAL_LEFT_LIMIT_EN_MASK;
      tmc4361A_rstBits(tmc4361A, TMC4361A_REFERENCE_CONF, en_datagram);
      break;
    case 1:
      en_datagram = TMC4361A_VIRTUAL_RIGHT_LIMIT_EN_MASK;
      tmc4361A_rstBits(tmc4361A, TMC4361A_REFERENCE_CONF, en_datagram);
      break;
  }
  return;
}
int8_t tmc4361A_setVirtualLimit(TMC4361ATypeDef *tmc4361A, int dir, int32_t limit) {
  switch (dir) {
    case -1:
      tmc4361A_writeInt(tmc4361A, TMC4361A_VIRT_STOP_LEFT, limit);
      break;
    case 1:
      tmc4361A_writeInt(tmc4361A, TMC4361A_VIRT_STOP_RIGHT, limit);
      break;
  }
  return NO_ERR;
}



/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_enableHomingLimit() enables using either the left or right limit switch for homing

  OPERATION:   We format the switch polarity variables and target switch into a datagram and send it to the tmc4361. We then enable position latching when the limit switch is hit

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t polarity:          Polarity of the switch - 0 if active low, 1 if active high
      uint8_t which:             Which switch to use as home
      uint16_t safety_margin:	 safty margin of home pointer around

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_enableHomingLimit(TMC4361ATypeDef *tmc4361A, uint8_t polarity, uint8_t which, uint16_t safety_margin) {
  if (which == LEFT_SW) {
    if (polarity != 0) {
      // If the left switch is active high, HOME_REF = 0 indicates positive direction in reference to X_HOME
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, 0b1100 << TMC4361A_HOME_EVENT_SHIFT);
    }
    else {
      // if active low, HOME_REF = 0 indicates negative direction in reference to X_HOME
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, 0b0011 << TMC4361A_HOME_EVENT_SHIFT);
    }
    // use stop left as home
    tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_STOP_LEFT_IS_HOME_MASK);
  }
  else {
    if (polarity != 0) {
      // If the right switch is active high, HOME_REF = 0 indicates positive direction in reference to X_HOME
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, 0b0011 << TMC4361A_HOME_EVENT_SHIFT);
    }
    else {
      // if active low, HOME_REF = 0 indicates negative direction in reference to X_HOME
      tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, 0b1100 << TMC4361A_HOME_EVENT_SHIFT);
    }
    // use stop right as home
    tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_STOP_RIGHT_IS_HOME_MASK);
  }
  // have a safety margin around home
  tmc4361A_setBits(tmc4361A, TMC4361A_HOME_SAFETY_MARGIN, safety_margin);

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_readLimitSwitches() reads the limit switches and returns their state in the two low bits of a byte.
                00 - both not pressed
                01 - right switch pressed
                10 - left
                11 - both

  OPERATION:   We read the status register, mask the irrelevant bits, and shift the relevant bits down

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      uint8_t result: Byte containing the button state in the last two bits

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      uint32_t i_datagram: data received from the tmc4361A

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
uint8_t tmc4361A_readLimitSwitches(TMC4361ATypeDef *tmc4361A) {
  // Read both limit switches. Set bit 0 if the left switch is pressed and bit 1 if the right switch is pressed
  uint32_t i_datagram = 0;

  // Get the datagram
  i_datagram = tmc4361A_readInt(tmc4361A, TMC4361A_STATUS);
  // Mask off everything except the button states
  i_datagram &= (TMC4361A_STOPL_ACTIVE_F_MASK | TMC4361A_STOPR_ACTIVE_F_MASK);
  // Shift the button state down to bits 0 and 1
  i_datagram >>= TMC4361A_STOPL_ACTIVE_F_SHIFT;
  // Get rid of the high bits
  uint8_t result = i_datagram & 0xff;

  return result;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_readSwitchEvent() checks whether there was a switch event and returns their state in the two low bits of a byte.
                00 - both not pressed
                01 - left switch pressed
                10 - right
                11 - both

  OPERATION:   We read the events register, mast the irrelevant bits, and shift the relevant bits down

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      uint8_t result: Byte containing the button state in the last two bits

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      uint32_t i_datagram: data received from the tmc4361A

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
uint8_t tmc4361A_readSwitchEvent(TMC4361ATypeDef *tmc4361A) {
  // Read both limit switches. Set bit 0 if the left switch is pressed and bit 1 if the right switch is pressed
  unsigned long i_datagram = 0;
  unsigned long address = TMC4361A_EVENTS;

  // Get the datagram
  i_datagram = tmc4361A_readInt(tmc4361A, address);
  // Mask off everything except the button states
  i_datagram &= (TMC4361A_STOPL_EVENT_MASK | TMC4361A_STOPR_EVENT_MASK);
  // Shift the button state down to bits 0 and 1
  i_datagram >>= TMC4361A_STOPL_EVENT_SHIFT;
  // Get rid of the high bits
  uint8_t result = i_datagram & 0xff;

  return result;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setHome() writes the latched position to the motor driver struct.

  OPERATION:   We read the latched value from the TMC4361 and write it to the struct

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_setHome(TMC4361ATypeDef *tmc4361A) {
  tmc4361A->xhome = tmc4361A_readInt(tmc4361A, TMC4361A_X_LATCH_RD);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_moveToExtreme() moves a carriage to one of the extremes (min x or max x) and writes the min/max positions to the struct. Use the RGHT_DIR and LEFT_DIR macros as direction arguements

  OPERATION:   First, move away from any limit switches to ensure an accurate reading of the extreme. Ensure the velocity has the correct sign. Then we clear events and start moving until we hit a switch event. We latch the position value and write it to the struct.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      uint32_t eventstate: data from the events register

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_moveToExtreme(TMC4361ATypeDef *tmc4361A, int32_t vel, int8_t dir) {
  uint8_t eventstate = tmc4361A_readLimitSwitches(tmc4361A);
  vel = abs(vel);
  // If we are moving right and already are at the right switch, back up a bit
  if (dir == RGHT_DIR && eventstate == RGHT_SW) {
    tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
    // rotate puts us in velocity mode
    tmc4361A_setSpeed(tmc4361A, vel * LEFT_DIR);
    while (eventstate == RGHT_SW) {
      eventstate = tmc4361A_readLimitSwitches(tmc4361A);
      delay(5);
    }
    delay(300);
  }
  // If we are moving left and already are at the left switch, back up
  else if (dir == LEFT_DIR && eventstate == LEFT_SW) {
    tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
    tmc4361A_setSpeed(tmc4361A, vel * RGHT_DIR);
    while (eventstate == LEFT_SW) {
      eventstate = tmc4361A_readLimitSwitches(tmc4361A);
      delay(5);
    }
    delay(300);
  }
  // Move to the right to find xmax
  // Move the direction specified
  vel *= dir;
  // Read the events register before moving
  tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
  tmc4361A_setSpeed(tmc4361A, vel);
  // Keep moving until we get a switch event or switch status
  while (((eventstate != RGHT_SW) && (dir == RGHT_DIR)) || ((eventstate != LEFT_SW) && (dir == LEFT_DIR))) {
    delay(5);
    eventstate = tmc4361A_readSwitchEvent(tmc4361A );
    eventstate |= tmc4361A_readLimitSwitches(tmc4361A);
  }
  // When we do get a switch event, write the latched X
  if (dir == RGHT_DIR) {
    tmc4361A->xmax = tmc4361A_readInt(tmc4361A, TMC4361A_X_LATCH_RD);
    tmc4361A_writeInt(tmc4361A, TMC4361A_X_TARGET, tmc4361A->xmax);
  }
  else {
    tmc4361A->xmin = tmc4361A_readInt(tmc4361A, TMC4361A_X_LATCH_RD);
    tmc4361A_writeInt(tmc4361A, TMC4361A_X_TARGET, tmc4361A->xmin);
  }

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_sRampInit() writes the ramp parameters to the TMC4361A.

  OPERATION:   We read the data from the shared struct and write them one at a time to the tmc4361A

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_sRampInit(TMC4361ATypeDef *tmc4361A) {
  tmc4361A_setBits(tmc4361A, TMC4361A_RAMPMODE, TMC4361A_RAMP_POSITION | TMC4361A_RAMP_SSHAPE); // positioning mode, s-shaped ramp
  tmc4361A_rstBits(tmc4361A, TMC4361A_GENERAL_CONF, TMC4361A_USE_ASTART_AND_VSTART_MASK); // keep astart, vstart = 0
  tmc4361A_writeInt(tmc4361A, TMC4361A_BOW1, tmc4361A->rampParam[BOW1_IDX]); // determines the value which increases the absolute acceleration value.
  tmc4361A_writeInt(tmc4361A, TMC4361A_BOW2, tmc4361A->rampParam[BOW2_IDX]); // determines the value which decreases the absolute acceleration value.
  tmc4361A_writeInt(tmc4361A, TMC4361A_BOW3, tmc4361A->rampParam[BOW3_IDX]); // determines the value which increases the absolute deceleration value.
  tmc4361A_writeInt(tmc4361A, TMC4361A_BOW4, tmc4361A->rampParam[BOW4_IDX]); // determines the value which decreases the absolute deceleration value.
  tmc4361A_writeInt(tmc4361A, TMC4361A_AMAX, tmc4361A->rampParam[AMAX_IDX]); // max acceleration
  tmc4361A_writeInt(tmc4361A, TMC4361A_DMAX, tmc4361A->rampParam[DMAX_IDX]); // max decelleration
  tmc4361A_writeInt(tmc4361A, TMC4361A_ASTART, tmc4361A->rampParam[ASTART_IDX]); // initial acceleration
  tmc4361A_writeInt(tmc4361A, TMC4361A_DFINAL, tmc4361A->rampParam[DFINAL_IDX]); // final decelleration
  tmc4361A_writeInt(tmc4361A, TMC4361A_VMAX, tmc4361A->rampParam[VMAX_IDX]); // max speed

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setSRampParam() writes a single ramp parameter to the TMC4361A.

  OPERATION:   We change a variable in the shared struct and call sRampInit() to write the data.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t idx:               Which parameter to change
      int32_t param:             The new value of the parameter

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_setSRampParam(TMC4361ATypeDef *tmc4361A, uint8_t idx, int32_t param) {
  // Ensure idx is in range
  if (idx >= N_RPARAM) {
    return;
  }

  tmc4361A->rampParam[idx] = param;
  tmc4361A_sRampInit(tmc4361A);

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_adjustBows() computes bow values such that the least amount of time is spent saturated at AMAX

  OPERATION:   We read AMAX and VMAX, convert to mm, and compute AMAX^2/VMAX to get our target jerk. The jerk is them bound to be below our maximum value and writes it to the shared struct. All 4 bows are assigned the same value. The data is not written to the IC in this function.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/

void tmc4361A_adjustBows(TMC4361ATypeDef *tmc4361A) {
  // Calculate what the jerks should be given amax and vmax
  // Minimize the time a = amax under the constraint BOW1 = BOW2 = BOW3 = BOW4
  // We also have to do unit conversions
  float bowval = tmc4361A_amicrostepsTomm(tmc4361A, tmc4361A->rampParam[AMAX_IDX]) * tmc4361A_amicrostepsTomm(tmc4361A, tmc4361A->rampParam[AMAX_IDX]) / tmc4361A_vmicrostepsTomm(tmc4361A, tmc4361A->rampParam[VMAX_IDX]);
  int32_t bow = abs(tmc4361A_xmmToMicrosteps(tmc4361A, bowval));
  bow = min(BOWMAX, bow);

  tmc4361A->rampParam[BOW1_IDX] = bow;
  tmc4361A->rampParam[BOW2_IDX] = bow;
  tmc4361A->rampParam[BOW3_IDX] = bow;
  tmc4361A->rampParam[BOW4_IDX] = bow;

  return;
}


/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setMaxSpeed() writes a single ramp parameter to the TMC4361A.

  OPERATION:   We first verify the new velocity value is in bounds, then we change the variable in the shared struct and call sRampInit() to write the data.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t velocity:          The velocity in units microsteps per second

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_setMaxSpeed(TMC4361ATypeDef *tmc4361A, int32_t velocity) {
  tmc4361A->rampParam[VMAX_IDX] = velocity;
  tmc4361A_adjustBows(tmc4361A);
  tmc4361A_sRampInit(tmc4361A);
  return;
}


/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setSpeed() sets the motor moving at a constant velocity.

  OPERATION:   We clear the events register, clear the ramp parameters (no velocity ramping) and write the velocity

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t velocity:          The velocity in units microsteps per second

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_setSpeed(TMC4361ATypeDef *tmc4361A, int32_t velocity) {
  tmc4361A->velocity_mode = true;
  tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS); // clear register
  tmc4361A_rstBits(tmc4361A, TMC4361A_RAMPMODE, TMC4361A_RAMP_POSITION | TMC4361A_RAMP_HOLD); // no velocity ramp
  tmc4361A_writeInt(tmc4361A, TMC4361A_VMAX, velocity);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_speed() reads the current velocity and returns it in units microsteps per second

  OPERATION:   We read the VACTUAL register.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      uint32_t result: Velocity

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_speed(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_VACTUAL);
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_acceleration() reads the current acceleration and returns it in units microsteps per second^2

  OPERATION:   We read the AACTUAL register.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      uint32_t result: Acceleration

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_acceleration(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_AACTUAL);
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setMaxAcceleration() writes a acceleration and bow ramp parameters to the TMC4361A.

  OPERATION:   We first verify the new acceleration value is in bounds, then we change the variable in the shared struct. We also change bows 1 through 4 to ensure we hit max acceleration. Then we call sRampInit() to write the data.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t acceleration:      The acceleration in microsteps per second squared

  RETURNS:
      uint8_t err: Return ERR_OUT_OF_RANGE or NO_ERR depending on what happened.

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_setMaxAcceleration(TMC4361ATypeDef *tmc4361A, uint32_t acceleration) {
  int8_t err = NO_ERR;
  if (acceleration > ACCELMAX) {
    err = ERR_OUT_OF_RANGE;
    acceleration = ACCELMAX;
  }

  tmc4361A->rampParam[AMAX_IDX] = acceleration;
  tmc4361A->rampParam[DMAX_IDX] = acceleration;
  tmc4361A_adjustBows(tmc4361A);
  tmc4361A_sRampInit(tmc4361A);

  return err;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_moveTo() writes the new setpoint to the TMC4361A.

  OPERATION:   First, go to posiitoning mode. Then first verify the new position value is in bounds, then we clear the event register, send the data to the TMC4613, clear the event register again, and read the current position to refresh it.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t x_pos:             The target position in microsteps

  RETURNS:
      uint8_t err: Return ERR_OUT_OF_RANGE or NO_ERR depending on what happened.

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_moveTo(TMC4361ATypeDef *tmc4361A, int32_t x_pos) {
  if (x_pos < tmc4361A->xmin || x_pos > tmc4361A->xmax) {
    return ERR_OUT_OF_RANGE;
  }

  if(tmc4361A->velocity_mode) {
    // ensure we are in positioning mode with S-shaped ramp
    tmc4361A_sRampInit(tmc4361A);
    tmc4361A->velocity_mode = false;
  }

  // Read events before and after to clear the register
  tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
  tmc4361A_writeInt(tmc4361A, TMC4361A_X_TARGET, x_pos);
  tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
  // Read X_ACTUAL to get it to refresh
  tmc4361A_readInt(tmc4361A, TMC4361A_XACTUAL);

  return NO_ERR;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_move() writes the new setpoint relative to the current position to the TMC4361A.

  OPERATION:   We first convert the relative position to an absolute position and call moveTo()

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t x_pos:             The target position in microsteps

  RETURNS:
      uint8_t err: Return ERR_OUT_OF_RANGE or NO_ERR depending on what happened.

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      int32_t current: current position
      int32_t target:  calculated absolute position

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_move(TMC4361ATypeDef *tmc4361A, int32_t x_pos) {
  int32_t current = tmc4361A_currentPosition(tmc4361A);
  int32_t target = current + x_pos;

  return tmc4361A_moveTo(tmc4361A, target);
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_currentPosition() reads the current position

  OPERATION:   We read the data in the XACTUAL register

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      int32_t xpos: The position in units microsteps

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_currentPosition(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_XACTUAL);
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_targetPosition() reads the target position

  OPERATION:   We read the data in the X_TARGET register

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      int32_t xpos: The position in units microsteps

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_targetPosition(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_X_TARGET);
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_setCurrentPosition() overwrites the current position with a new position. This doesn't change the physical position of the motor.

  OPERATION:   We change the motor driver struct varaibles to reflect the new offset and update the TMC4361A.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS:
      int8_t err: NO_ERR if the new xmin, xmax, and xhome don't hit the min/max int32_t values and ERR_OUT_OF_RANGE if they do

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      int32_t current: stores the current position
      int32_t diff:    stores the difference between the current and target position

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from and written to the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_setCurrentPosition(TMC4361ATypeDef *tmc4361A, int32_t position) {
  int32_t current = tmc4361A_currentPosition(tmc4361A);
  int32_t dif = position - current;
  int8_t err = NO_ERR;
  // change motor parameters on the teensy
  // first, ensure no overflows happen
  int32_t xmax  = tmc4361A->xmax;
  int32_t xmin  = tmc4361A->xmin;
  int32_t xhome = tmc4361A->xhome;
  if (dif > 0) {
    // perform addition overflow check
    if (xmax > INT32_MAX - dif) {
      err = ERR_OUT_OF_RANGE;
      xmax = INT32_MAX;
    }
    else {
      xmax += dif;
    }
    if (xmin > INT32_MAX - dif) {
      err = ERR_OUT_OF_RANGE;
      xmin = INT32_MAX;
    }
    else {
      xmin += dif;
    }
    if (xhome > INT32_MAX - dif) {
      err = ERR_OUT_OF_RANGE;
      xhome = INT32_MAX;
    }
    else {
      xhome += dif;
    }
  }
  else {
    // perform subtraction overflow check
    if (xmax < INT32_MIN - dif) {
      err = ERR_OUT_OF_RANGE;
      xmax = INT32_MIN;
    }
    else {
      xmax += dif;
    }
    if (xmin < INT32_MIN - dif) {
      err = ERR_OUT_OF_RANGE;
      xmin = INT32_MIN;
    }
    else {
      xmin += dif;
    }
    if (xhome < INT32_MIN - dif) {
      err = ERR_OUT_OF_RANGE;
      xmin = INT32_MIN;
    }
    else {
      xhome += dif;
    }
  }
  // save the new values
  tmc4361A->xmax = xmax;
  tmc4361A->xmin = xmin;
  tmc4361A->xhome = xhome;
  // change motor parameters on the driver
  tmc4361A_writeInt(tmc4361A, TMC4361A_VMAX, 0);
  tmc4361A_writeInt(tmc4361A, TMC4361A_XACTUAL, position);
  tmc4361A_moveTo(tmc4361A, position);

  tmc4361A->velocity_mode = true;
  return err;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_stop() halts motor motion

  OPERATION:   We move the motor to position 0 relative to its current position

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_stop(TMC4361ATypeDef *tmc4361A) {
  tmc4361A_move(tmc4361A, 0);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_isRunning() checks whether the motor is moving and returns either true or false

  OPERATION:   We check if the motor hit its target. If so, we return true. We then check the acceleration and velocity; if they are both zero we also return true. Then, otherwise, return false

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
	  bool pid_enable: true: if this aix enable pid control, else: false

  RETURNS:
      bool moving: true if moving, false otherwise

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      int32_t stat_reg: The status register

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
bool tmc4361A_isRunning(TMC4361ATypeDef *tmc4361A, bool pid_enable) {
  int32_t stat_reg = tmc4361A_readInt(tmc4361A, TMC4361A_STATUS);

  if (pid_enable) {
  	  int32_t pid_err  = abs(tmc4361A_readInt(tmc4361A, TMC4361A_PID_E_RD));
	  // We aren't running if target is reached OR (velocity = 0 and acceleration == 0)
	  if (((stat_reg & TMC4361A_TARGET_REACHED_MASK) == 1) && ((stat_reg & (TMC4361A_VEL_STATE_F_MASK | TMC4361A_RAMP_STATE_F_MASK))==0) && (pid_err < tmc4361A->target_tolerance)) {
		  return false;
	  }
  }
  else {
	  // We aren't running if target is reached OR (velocity = 0 and acceleration == 0)
	  if (((stat_reg & TMC4361A_TARGET_REACHED_MASK) == 1) && ((stat_reg & (TMC4361A_VEL_STATE_F_MASK | TMC4361A_RAMP_STATE_F_MASK))==0)) {
		  return false;
	  }
  }

  // Otherwise, return true
  return true;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: The three mmToMicrosteps() functions convers a position in units mm to a position in units microsteps
               xmmToMicrosteps() also works for bow jerks

  OPERATION:   We multiply the mm by a conversion factor and cast to int32_t

  ARGUMENTS:
      float mm: posiiton in mm
      TMC4361ATypeDef *tmc4361A: for motor parameters

  RETURNS:
      int32_t microsteps: the position in units microsteps

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES:
      int32_t microsteps

  SHARED VARIABLES: None

  GLOBAL VARIABLES: None

  DEPENDENCIES: None
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_xmmToMicrosteps(TMC4361ATypeDef *tmc4361A, float mm) {
  int32_t microsteps = mm * ((float)(tmc4361A->microsteps * tmc4361A->stepsPerRev)) / (tmc4361A->threadPitch);
  return microsteps;
}
int32_t tmc4361A_vmmToMicrosteps(TMC4361ATypeDef *tmc4361A, float mm) {
  int32_t microsteps = (1 << 8) * mm * ((float)(tmc4361A->microsteps * tmc4361A->stepsPerRev)) / (tmc4361A->threadPitch); // mult. by 1 << 8 to account for 8 decimal places
  return microsteps;
}
int32_t tmc4361A_ammToMicrosteps(TMC4361ATypeDef *tmc4361A, float mm) {
  int32_t microsteps = (1 << 2) * mm * ((float)(tmc4361A->microsteps * tmc4361A->stepsPerRev)) / (tmc4361A->threadPitch); // mult. by 1 << 2 to account for 2 decimal places
  return microsteps;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_microstepsTomm() convers a position in units microsteps to a position in units mm
               tmc4361A_xmicrostepsTomm() also works for bow jerks

  OPERATION:   We cast the microsteps to a float and multiply the microsteps by a conversion factor

  ARGUMENTS:
      int32_t microsteps: the position in units microsteps

  RETURNS:
      float mm: posiiton in mm
      TMC4361ATypeDef *tmc4361A: for motor parameters

  INPUTS / OUTPUTS: None

  LOCAL VARIABLES:
      float mm

  SHARED VARIABLES: None

  GLOBAL VARIABLES: None

  DEPENDENCIES: None
  -----------------------------------------------------------------------------
*/
float   tmc4361A_xmicrostepsTomm(TMC4361ATypeDef *tmc4361A, int32_t microsteps) {
  float mm = microsteps * (tmc4361A->threadPitch) / ((float)(tmc4361A->microsteps * tmc4361A->stepsPerRev));
  return mm;
}
float   tmc4361A_vmicrostepsTomm(TMC4361ATypeDef *tmc4361A, int32_t microsteps) {
  float mm = microsteps * (tmc4361A->threadPitch) / ((float)(tmc4361A->microsteps * tmc4361A->stepsPerRev * (1 << 8)));
  return mm;
}
float   tmc4361A_amicrostepsTomm(TMC4361ATypeDef *tmc4361A, int32_t microsteps) {
  float mm = microsteps * (tmc4361A->threadPitch) / ((float)(tmc4361A->microsteps * tmc4361A->stepsPerRev * (1 << 2)));
  return mm;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_init_ABN_encoder() initializes an ABN encoder and IIR filtering. Must be done after initializing the tmc4361A.

  OPERATION:   Mask the high bit of the enc_res to prevent the manual mode bit from being set. Then, write the number of A/B transitions per revolution to the device.
               Next, format the filter values into a datagram and write it.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint32_t enc_res:          Resolution of the encoder; number of A/B transitions per revolution
      uint8_t filter_wait_time:  Delay between consecutive clock cycles for reading the encoder velocity. Minimum of FILTER_WAITTIME_MIN
      uint8_t filter_exponent:   Decay exponent for the IIR filter. Lower value means faster response; 0 disables filtering
      uint16_t filter_vmean:     Frequency at which V_mean is updated in the register. Minimum of FILTER_UPDATETIME_MIN.
      bool invert:               If set to true, invert the direction of the encoder

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      uint32_t datagram: store datagrams to write to the tmc4361.

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_init_ABN_encoder(TMC4361ATypeDef *tmc4361A, uint32_t enc_res, uint8_t filter_wait_time, uint8_t filter_exponent, uint16_t filter_vmean, bool invert) {
  uint32_t datagram;

  datagram = enc_res & TMC4361A_ENC_IN_RES_MASK; // ensure manual mode bit isn't set
  tmc4361A_writeInt(tmc4361A, TMC4361A_ENC_IN_RES_WR, datagram);

  // set the velocity filter
  datagram = uint32_t(filter_wait_time) + ((uint32_t(filter_exponent) << TMC4361A_ENC_VMEAN_FILTER_SHIFT)&TMC4361A_ENC_VMEAN_FILTER_MASK) + ((uint32_t(filter_vmean) << TMC4361A_ENC_VMEAN_INT_SHIFT)&TMC4361A_ENC_VMEAN_INT_MASK);
  tmc4361A_writeInt(tmc4361A, TMC4361A_ENC_VMEAN_FILTER_WR, datagram);

  // set whether or not to invert
  if (invert) {
    tmc4361A_setBits(tmc4361A, TMC4361A_ENC_IN_CONF, TMC4361A_INVERT_ENC_DIR_MASK);
  }

  return;
}
/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_read_encoder(), tmc4361A_read_encoder_filtered() reads the encoder and filtered encoder values respectively

  OPERATION:   We read the relevant registers. We wait 500 us between each reading so this function blocks for at least 2^(n_avg_exp - 1) milliseconds

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t n_avg_exp:         Average 2^n_avg_exp values. It takes slightly longer than 1ms for each avg

  RETURNS: Encoder position in units "microsteps"

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES:
      double reading: stores the intermediate values

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_read_encoder(TMC4361ATypeDef *tmc4361A, uint8_t n_avg_exp) {
  double reading = 0;
  for (uint8_t j = 0; j < (1 << n_avg_exp); j++) {
    reading += double(tmc4361A_readInt(tmc4361A, TMC4361A_ENC_POS)) / (double(1 << n_avg_exp));
    delayMicroseconds(500);
  }

  return reading;
}
int32_t tmc4361A_read_encoder_vel(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_V_ENC_RD);
}
int32_t tmc4361A_read_encoder_vel_filtered(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_V_ENC_MEAN_RD);
}
/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_read_deviation() reads the difference between XACTUAL and ENC_POS

  OPERATION:   We read the relevant registers.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: "Microstep" error between XACTUAL and ENC_POS

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int32_t tmc4361A_read_deviation(TMC4361ATypeDef *tmc4361A) {
  return tmc4361A_readInt(tmc4361A, TMC4361A_ENC_POS_DEV_RD);
}
/*
  -----------------------------------------------------------------------------
  This function doesn't work. It appeas the problem is that the deviation error tolerance isn't being written properly so the flag never gets raised.
  DESCRIPTION: tmc4361A_read_deviation_flag() returns True if the difference between XACTUAL and ENC_POS exceeds

  OPERATION:   We read the relevant registers.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info

  RETURNS: Returns true if the flag is set, otherwise false.

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
bool tmc4361A_read_deviation_flag(TMC4361ATypeDef *tmc4361A) {
  uint32_t datagram = tmc4361A_readInt(tmc4361A, TMC4361A_STATUS);
  datagram = datagram & TMC4361A_ENC_FAIL_MASK;
  return datagram >> TMC4361A_ENC_FAIL_SHIFT;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_set_PID() enables or disables PID

  OPERATION:   We have 3 "modes" we can set:
                PID_DISABLE: Disables PID
                PID_BPG0:    Enables PID and sets the initial PID velocity to 0
                PID_BPGV:    Enables PID and sets the initial PID velocity to the current velocity
              This operation is performed by first clearing the mode register, then writing the new mode.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint8_t pid_mode:          PID initial conditions

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_set_PID(TMC4361ATypeDef *tmc4361A, uint8_t pid_mode) {
  tmc4361A_rstBits(tmc4361A, TMC4361A_ENC_IN_CONF, TMC4361A_REGULATION_MODUS_MASK);
  tmc4361A_setBits(tmc4361A, TMC4361A_ENC_IN_CONF, pid_mode << TMC4361A_REGULATION_MODUS_SHIFT);
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_init_PID() writes PID parameters to the device.

  OPERATION:   The data in the arguments are packaged and written to the device.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      uint32_t target_tolerance: If the difference between XACTUAL and ENC_POS is less than this, raise the TARGET_REACHED flag
      uint32_t pid_tolerance:    If the difference between XACTUAL and ENC_POS is less than this, stop the PID and hold the current position
      uint32_t pid_p:            24-bit proportional term. (PID_P/256) * error * 1/seconds
      uint32_t pid_i:            24-bit integral term. (PID_I/256) * (PID_ISUM / 256) * 1/seconds
      uint32_t pid_d:            24-bit differential term. (PID_D) * error * d/dt
      uint32_t pid_dclip:        Limits the speed to be at most pid_dclip
      uint32_t pid_iclip:        15-bit integral winding limit, limit = pid_iclip * 2^16
      uint8_t pid_d_clkdiv:      For the derivate term of the PID control, PID_E will be compared to its former value every PID_D_CLK_DIV*128 / fCLK seconds


  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: uint32_t datagram

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_init_PID(TMC4361ATypeDef *tmc4361A, uint32_t target_tolerance, uint32_t pid_tolerance, uint32_t pid_p, uint32_t pid_i, uint32_t pid_d, uint32_t pid_dclip, uint32_t pid_iclip, uint8_t pid_d_clkdiv) {
  uint32_t datagram;

  tmc4361A_writeInt(tmc4361A, TMC4361A_CL_TR_TOLERANCE_WR, target_tolerance);   // Set the TARGET_REACHED tolerance
  tmc4361A_writeInt(tmc4361A, TMC4361A_PID_TOLERANCE_WR, pid_tolerance); // Set the PID tolerance


  // Write the PID parameters
  tmc4361A_writeInt(tmc4361A, TMC4361A_PID_P_WR, pid_p & TMC4361A_PID_P_MASK);
  tmc4361A_writeInt(tmc4361A, TMC4361A_PID_I_WR, pid_i & TMC4361A_PID_I_MASK);
  tmc4361A_writeInt(tmc4361A, TMC4361A_PID_D_WR, pid_d & TMC4361A_PID_D_MASK);

  tmc4361A_writeInt(tmc4361A, TMC4361A_PID_DV_CLIP_WR, pid_dclip & TMC4361A_PID_DV_CLIP_MASK);

  // Set up the datagram
  datagram = ((pid_iclip << TMC4361A_PID_I_CLIP_SHIFT) & TMC4361A_PID_I_CLIP_MASK) + ((pid_d_clkdiv << TMC4361A_PID_D_CLKDIV_SHIFT) & TMC4361A_PID_D_CLKDIV_MASK);
  tmc4361A_writeInt(tmc4361A, TMC4361A_PID_I_CLIP_WR, datagram);

  // save paramters
  tmc4361A->target_tolerance = target_tolerance;
  tmc4361A->pid_tolerance = pid_tolerance;
  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_measure_linearity() sweeps the motor across a range of positions open-loop and
               records the encoder reading and internal microstep reading. The rest of the open-loop
               setup must be done before running this function (e.g. set home and init_ABN_encoder).

               This also can be run with the PID loop active to compare the different results.

  OPERATION:   We first use the start_pos, end_pos, and n_measurements to find the step size.
               Next, we set start_pos as our setpoint and wait until we reach there.
               Then, we record the encoder and microstep readings into the shared array.
               We then move by our step size and repeat.
               If we hit a limit switch during any point or time out when trying to reach a target,
               return an error.

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t *encoder_reading:  Pointer to array of encoder readings
      int32_t *internal_reading: Pointer to array of microsteps readings
      uint8_t n_measurements:    Number of points to read along start to stop pos. Must be 2 or larger.
      int32_t start_pos:         Initial position to start the sweep
      int32_t end_pos:           Position to end the sweep. Due to rounding errors, we might not get all the way there.
      uint16_t timeout_ms:       If it takes longer than timeout_ms to hit the target, give up and return an error.

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively
                    The motor also will move.

  LOCAL VARIABLES: int32_t step_size: the amount to move to get to the next step
                   uint32_t t0:       tracks time since the movement began for use for timeout
                   int32_t target:    the desitnation to move the motor to
                   int8_t:            error from movement problems (timeout or hitting a limit switch)

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_measure_linearity(TMC4361ATypeDef *tmc4361A, int32_t *encoder_reading, int32_t *internal_reading, uint8_t n_measurements, int32_t start_pos, int32_t end_pos, uint16_t timeout_ms) {
  int32_t step_size = (end_pos - start_pos) / (n_measurements - 1);
  uint32_t t0;
  int32_t target;
  int8_t err;

  for (uint8_t i = 0; i < n_measurements; i++) {
    // Move to the target position
    target = start_pos + (i * step_size);
    err = tmc4361A_moveTo(tmc4361A, target);
    // If there was a movement error, break.
    if (err != NO_ERR) {
      break;
    }
    t0 = millis();
    // Wait until we hit the target
    while ((tmc4361A_currentPosition(tmc4361A) != target) && ((millis() - t0) < timeout_ms)) {
      delay(1);
    }
    // Get the positions
    delay(50);
    encoder_reading[i] = tmc4361A_read_encoder(tmc4361A, N_ENC_AVG_EXP);
    internal_reading[i] = tmc4361A_currentPosition(tmc4361A);
    // If we didn't, break
    if (tmc4361A_currentPosition(tmc4361A) != target) {
      err = ERR_TIMEOUT;
      break;
    }
    // Make sure we didn't hit a limit switch
    if (tmc4361A_readLimitSwitches(tmc4361A) != 0) {
      err = ERR_OUT_OF_RANGE;
      break;
    }
  }

  return err;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_moveTo_no_stick() writes the new setpoint to the TMC4361A and monitors the movement in case the carriage gets stuck.
               This is a blocking function. It only works if the motor stage has an encoder set up.

  OPERATION:   First, go to positioning mode. Then first verify the new position value is in bounds, then we clear the event register, send the data to the TMC4613, clear the event register again, and read the current position to refresh it.
               We next monitor the deviation while the carriage is moving. If the deviation exceeds the threshold, go back to the position where it got stuck and then some to un-stick the carriage.
               then continue moving to the target position.
               If we do not get to the target position before the timeout time, return an error


  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t x_pos:             The target position in microsteps
      int32_t backup_amount:     Distance to back up if the carriage is stuck in microsteps
      uint32_t err_thresh:       Deviation error threshold for recognizing the carriage is stuck. This should be a relatively large value because the deviation gets large when moving normally.
      uint16_t timeout_ms:       If timeout_ms elapses and we do not hit our target, raise an error.

  RETURNS:
      uint8_t err: Return ERR_OUT_OF_RANGE, ERR_TIMEOUT, or NO_ERR depending on what happened.

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively. The motor also will move.

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_moveTo_no_stick(TMC4361ATypeDef *tmc4361A, int32_t x_pos, int32_t backup_amount, uint32_t err_thresh, uint16_t timeout_ms)  {
  uint32_t t0 = 0;
  int32_t original_position, backup_target;
  int8_t err = NO_ERR;

  // ensure we are in positioning mode with S-shaped ramp
  tmc4361A_sRampInit(tmc4361A);

  if (x_pos < tmc4361A->xmin || x_pos > tmc4361A->xmax) {
    return ERR_OUT_OF_RANGE;
  }
  // Check which direction we are going - used to determine whether to subtract or add the backup amount
  original_position = tmc4361A_currentPosition(tmc4361A);
  if (x_pos - original_position > 0) {
    // If the target is more positive than the current position, the backup direction is negative
    backup_amount = backup_amount * -1;
  }
  // Get the current time
  t0 = millis();
  // Read events before and after to clear the register
  tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
  tmc4361A_writeInt(tmc4361A, TMC4361A_X_TARGET, x_pos);
  // Start keeping track of time, deviation, and position:
  while (true) {
    // Break and return error if we time out
    if (millis() - t0 > timeout_ms) {
      err = ERR_TIMEOUT;
      break;
    }
    // Break and return no error if we hit the target successfully
    if ((tmc4361A_readInt(tmc4361A, TMC4361A_STATUS) & TMC4361A_TARGET_REACHED_MASK) != 0) {
      err = NO_ERR;
      break;
    }
    // If we have too much deviation, back up and try again
    uint32_t deviation = abs(tmc4361A_read_deviation(tmc4361A));
    if (deviation > err_thresh) {
      tmc4361A_stop(tmc4361A);
      // disable PID
      tmc4361A_set_PID(tmc4361A, PID_DISABLE);
      // Find out where to back up to
      original_position = tmc4361A_currentPosition(tmc4361A);
      backup_target = backup_amount + original_position;

      tmc4361A_writeInt(tmc4361A, TMC4361A_X_TARGET, backup_target);

      // Wait until we back up or time out
      while ((millis() - t0 < timeout_ms) && ((tmc4361A_readInt(tmc4361A, TMC4361A_STATUS) & TMC4361A_TARGET_REACHED_MASK) == 0)) {
        delay(50);
      }

      // re-enable PID
      tmc4361A_set_PID(tmc4361A, PID_BPG0);
      // Go back to the original target
      tmc4361A_writeInt(tmc4361A, TMC4361A_X_TARGET, x_pos);
      delay(50); // Give extra time to start moving
    }
    // idle
    delay(50);
  }
  tmc4361A_readInt(tmc4361A, TMC4361A_EVENTS);
  // Read X_ACTUAL to get it to refresh
  tmc4361A_readInt(tmc4361A, TMC4361A_XACTUAL);

  return err;
}
/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_moveTo_no_stick() sets the new setpoint relative to the current setpoint.

  OPERATION:   We first convert the relative position to an absolute position and call moveTo_no_stick()


  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int32_t x_pos:             The target position in microsteps
      int32_t backup_amount:     Distance to back up if the carriage is stuck in microsteps
      uint32_t err_thresh:       Deviation error threshold for recognizing the carriage is stuck. This should be a relatively large value because the deviation gets large when moving normally.
      uint16_t timeout_ms:       If timeout_ms elapses and we do not hit our target, raise an error.

  RETURNS:
      uint8_t err: Return ERR_OUT_OF_RANGE, ERR_TIMEOUT, or NO_ERR depending on what happened.

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively. The motor also will move.

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int8_t tmc4361A_move_no_stick(TMC4361ATypeDef *tmc4361A, int32_t x_pos, int32_t backup_amount, uint32_t err_thresh, uint16_t timeout_ms) {
  int32_t current = tmc4361A_currentPosition(tmc4361A);
  int32_t target = current + x_pos;

  return tmc4361A_moveTo_no_stick(tmc4361A, target, backup_amount, err_thresh, timeout_ms);
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_config_init_stallGuard() initializes stall prevention on the TMC4316A and TMC2660

  OPERATION:   First, check if arugments are within bounds. If the argument exceed the bounds, constrain them before writing the values, and note that this function failed.
               We then write the sensitivitity to the TMC2660.
               

  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
      int8_t sensitivity: Value from -64 to +63 indicating sensitivity to stall condition. Larger values are less sensitive.
      bool filter_en: Set true to use filter (more accurate, slower).
      uint32_t vstall_lim: 24-bit value. The internal ramp velocity is set immediately to 0 whenever a stall is detected and |VACTUAL| >VSTALL_LIMIT.

  RETURNS: 
      bool success: return true if there were no errors

  INPUTS / OUTPUTS: Sends signals over SPI
  
  LOCAL VARIABLES: None

  SHARED VARIABLES: 
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
int16_t tmc4361A_config_init_stallGuard(TMC4361ATypeDef *tmc4361A, int8_t sensitivity, bool filter_en, uint32_t vstall_lim){
  // First, ensure values are within limits
  bool success = true;
  if((sensitivity > 63) || (sensitivity < -64) || (vstall_lim >= (1<<24))){
    success = false;
  }
  sensitivity = constrain(sensitivity, -64, 63);
  vstall_lim = constrain(vstall_lim, 0, ((1<<24)-1));
  // Mask the high bit
  sensitivity = sensitivity & 0x7F;
  // Build the datagram
  uint32_t datagram = 0;
  datagram = filter_en ? SFILT : 0;
  datagram |= SGCSCONF;
  datagram |= (sensitivity << 8);
  datagram |= tmc4361A->cscaleParam[CSCALE_IDX];
  // Next, write to the TMC2660 - write to the "cover_0.3 *10^6 /(200*256)low" register
  tmc4361A_writeInt(tmc4361A, TMC4361A_COVER_LOW_WR, datagram);
  // Enable stall detection on the TMC4316A
  // set vstall limit
  tmc4361A_writeInt(tmc4361A, TMC4361A_VSTALL_LIMIT_WR, vstall_lim);
  // enable stop on stall
  tmc4361A_setBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_STOP_ON_STALL_MASK);
  // disable drive after stall
  tmc4361A_rstBits(tmc4361A, TMC4361A_REFERENCE_CONF, TMC4361A_DRV_AFTER_STALL_MASK);

  return success;
}
