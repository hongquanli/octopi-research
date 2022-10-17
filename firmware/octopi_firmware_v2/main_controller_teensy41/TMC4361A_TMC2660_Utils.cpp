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
          Arguments: TMC4361ATypeDef *tmc4361A
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
      tmc4361A_setSPR:                  Write the number of steps per revolution to the motor driver
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
  DESCRIPTION: tmc4361A_writeMicrosteps() writes the number of microsteps per fullstep to the motor controller.
  
  OPERATION:   We first check if the mstep argument is a power of 2. We set an error flag if it is not.
               We then convert the microsteps number to the correct format for the tmc4361A: 256 -> 0, 128 -> 1, ..., 1 -> 8.
               This conversion is performed by shifting mstep down a bit and incrementing bitsSet until mstep is equal to 0. This is equivalent to evaluating log_2(mstep)+1. Then we calculate 9-bitsSet to convert to the proper format.
  
  ARGUMENTS:
      TMC4361ATypeDef *tmc4361A: Pointer to a struct containing motor driver info
  
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
  // software reset
  tmc4361A_writeInt(tmc4361A, TMC4361A_RESET_REG, 0x52535400);
  // clock
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
  tmc4361A_setBits(tmc4361A, TMC4361A_CURRENT_CONF, TMC4361A_DRIVE_CURRENT_SCALE_EN_MASK); // keep drive current scale
  tmc4361A_setBits(tmc4361A, TMC4361A_CURRENT_CONF, TMC4361A_HOLD_CURRENT_SCALE_EN_MASK);  // keep hold current scale
  // microstepping setting
  tmc4361A_writeMicrosteps(tmc4361A);
  // steps per revolution
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
  tmc4361A_setBits(tmc4361A, TMC4361A_CURRENT_CONF, TMC4361A_DRIVE_CURRENT_SCALE_EN_MASK); // keep drive current scale
  tmc4361A_setBits(tmc4361A, TMC4361A_CURRENT_CONF, TMC4361A_HOLD_CURRENT_SCALE_EN_MASK);  // keep hold current scale
  // microstepping setting
  tmc4361A_writeMicrosteps(tmc4361A);
  // steps per revolution
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
  RETURNS: None
  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively
  LOCAL VARIABLES: None
  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct
  GLOBAL VARIABLES: None
  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_tmc2660_config(TMC4361ATypeDef *tmc4361A, float tmc2660_cscale, float tmc4361a_hold_scale_val, float tmc4361a_drv2_scale_val, float tmc4361a_drv1_scale_val, float tmc4361a_boost_scale_val, float pitch_mm, uint16_t steps_per_rev, uint16_t microsteps) {

  tmc4361A->cscaleParam[0] = uint8_t(tmc2660_cscale*31);
  tmc4361A->cscaleParam[1] = uint8_t(tmc4361a_hold_scale_val*255);
  tmc4361A->cscaleParam[2] = uint8_t(tmc4361a_drv2_scale_val*255);
  tmc4361A->cscaleParam[3] = uint8_t(tmc4361a_drv1_scale_val*255);
  tmc4361A->cscaleParam[4] = uint8_t(tmc4361a_boost_scale_val*255);
  tmc4361A_setPitch(tmc4361A, pitch_mm);
  tmc4361A_setSPR(tmc4361A, steps_per_rev);
  tmc4361A_setMicrosteps(tmc4361A, microsteps);
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
  if(flipped != 0){
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

  RETURNS: None

  INPUTS / OUTPUTS: The CS pin and SPI MISO and MOSI pins output, input, and output data respectively

  LOCAL VARIABLES: None

  SHARED VARIABLES:
      TMC4361ATypeDef *tmc4361A: Values are read from the struct

  GLOBAL VARIABLES: None

  DEPENDENCIES: tmc4316A.h
  -----------------------------------------------------------------------------
*/
void tmc4361A_enableHomingLimit(TMC4361ATypeDef *tmc4361A, uint8_t polarity, uint8_t which){
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
  tmc4361A_setBits(tmc4361A, TMC4361A_HOME_SAFETY_MARGIN, 1 << 2);

  return;
}

/*
  -----------------------------------------------------------------------------
  DESCRIPTION: tmc4361A_readLimitSwitches() reads the limit switches and returns their state in the two low bits of a byte.
                00 - both not pressed
                01 - left switch pressed
                10 - right
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
    // tmc4361A_rotate(tmc4361A, vel * LEFT_DIR);
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
    // tmc4361A_rotate(tmc4361A, vel * RGHT_DIR);
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
  // Keep moving until we get a switch event
  while (((eventstate != RGHT_SW) && (dir == RGHT_DIR)) || ((eventstate != LEFT_SW) && (dir == LEFT_DIR))) {
    delay(5);
    eventstate = tmc4361A_readSwitchEvent(tmc4361A );
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
  tmc4361A_setBits(tmc4361A, TMC4361A_RAMPMODE, 0b110); // positioning mode, s-shaped ramp
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
  // tmc4361A_rstBits(tmc4361A, TMC4361A_RAMPMODE, 0b111); // no velocity ramp
  tmc4361A_rstBits(tmc4361A, TMC4361A_RAMPMODE, 0b100); // keep velocity ramp
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
  if(tmc4361A->velocity_mode)
  {
    // ensure we are in positioning mode with S-shaped ramp
    tmc4361A_sRampInit(tmc4361A);
    tmc4361A->velocity_mode = false;
  }
  if (x_pos < tmc4361A->xmin || x_pos > tmc4361A->xmax) {
    return ERR_OUT_OF_RANGE;
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
  // first, ensure no overflows happen
  int32_t xmax  = tmc4361A->xmax;
  int32_t xmin  = tmc4361A->xmin;
  int32_t xhome = tmc4361A->xhome;
  if(dif > 0){
    // perform addition overflow check
    if(xmax > INT32_MAX-dif){
      err = ERR_OUT_OF_RANGE;
      xmax = INT32_MAX;
    }
    else{
      xmax += dif;
    }
    if(xmin > INT32_MAX-dif){
      err = ERR_OUT_OF_RANGE;
      xmin = INT32_MAX;
    }
    else{
      xmin += dif;
    }
    if(xhome > INT32_MAX-dif){
      err = ERR_OUT_OF_RANGE;
      xhome = INT32_MAX;
    }
    else{
      xhome += dif;
    }
  }
  else{
    // perform subtraction overflow check
    if(xmax < INT32_MIN-dif){
      err = ERR_OUT_OF_RANGE;
      xmax = INT32_MIN;
    }
    else{
      xmax += dif;
    }
    if(xmin < INT32_MIN-dif){
      err = ERR_OUT_OF_RANGE;
      xmin = INT32_MIN;
    }
    else{
      xmin += dif;
    }
    if(xhome < INT32_MIN-dif){
      err = ERR_OUT_OF_RANGE;
      xmin = INT32_MIN;
    }
    else{
      xhome += dif;
    }
  }
  // save the new values
  tmc4361A->xmax = xmax;
  tmc4361A->xmin = xmin;
  tmc4361A->xhome = xhome;
  // change motor parameters on the driver
  tmc4361A_writeInt(tmc4361A, TMC4361A_VMAX, 0); // max speed
  tmc4361A_moveTo(tmc4361A, position);
  tmc4361A_writeInt(tmc4361A, TMC4361A_XACTUAL, position);
  // set the velocity_mode flag as velocity needs to be reset
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
bool tmc4361A_isRunning(TMC4361ATypeDef *tmc4361A) {
  int32_t stat_reg = tmc4361A_readInt(tmc4361A, TMC4361A_STATUS);

  // We aren't running if target is reached OR (velocity = 0 and acceleration == 0)
  if ((stat_reg & TMC4361A_TARGET_REACHED_MASK) != 0) {
    return true;
  }
  stat_reg &= (TMC4361A_VEL_STATE_F_MASK | TMC4361A_RAMP_STATE_F_MASK);
  if (stat_reg == 0) {
    return true;
  }

  // Otherwise, return false
  return false;
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
