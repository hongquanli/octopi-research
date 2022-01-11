#include <SPI.h>

// MCU - computer communication
static const int CMD_LENGTH = 8;
byte buffer_rx[500];
volatile int buffer_rx_ptr;

byte cmd_id = 0;
bool mcu_cmd_execution_in_progress = false;

unsigned long current_time_us;

// command sets
static const int SET_DAC = 0;

// DAC80508
const int DAC8050x_CS_pin = 10;
const uint8_t DAC8050x_DAC_ADDR = 0x08;
uint8_t DAC8050x_GAIN_ADDR = 0x04;
uint8_t DAC8050x_CONFIG_ADDR = 0x03;
uint16_t dac_value = 0;

void setup() 
{
  // configure the CS pin for DAC8050x
  pinMode(DAC8050x_CS_pin,OUTPUT);
  digitalWrite(DAC8050x_CS_pin,HIGH);

  // initialize/configure the SPI
  SPI.begin();
  delayMicroseconds(100000);
  
  // set the DAC80501 voltage reference and gain
  set_DAC8050x_gain();

  SerialUSB.begin(20000000);
  delayMicroseconds(100000);
  while (SerialUSB.available()) 
    SerialUSB.read();
}

void loop() 
{
  // put your main code here, to run repeatedly:
  while (SerialUSB.available()) 
  { 
    buffer_rx[buffer_rx_ptr] = SerialUSB.read();
    buffer_rx_ptr = buffer_rx_ptr + 1;
    if (buffer_rx_ptr == CMD_LENGTH) 
    {
      buffer_rx_ptr = 0;
      cmd_id = buffer_rx[0];
      switch(buffer_rx[1])
      {
        case SET_DAC: 
        {
          set_DAC8050x_output(buffer_rx[2],uint16_t(buffer_rx[3])<<8 + uint16_t(buffer_rx[4]));
          mcu_cmd_execution_in_progress = false;
          break;
        }
      }
    }
  }
}

void set_DAC8050x_output(int channel, uint16_t value)
{
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE2));
  digitalWrite(DAC8050x_CS_pin,LOW);
  SPI.transfer(DAC8050x_DAC_ADDR+channel);
  SPI.transfer16(dac_value);
  digitalWrite(DAC8050x_CS_pin,HIGH);
  SPI.endTransaction();
}

void set_DAC8050x_gain()
{
  // the reference voltage is internally divided by a factor of 2 - 1.25 V
  // the buffer amplifier for corresponding DAC has a gain of 2 => full scale output is 0-2.5V
  uint16_t value = 0x01FF;
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE2));
  digitalWrite(DAC8050x_CS_pin,LOW);
  SPI.transfer(DAC8050x_GAIN_ADDR);
  SPI.transfer16(value);
  digitalWrite(DAC8050x_CS_pin,HIGH);
  SPI.endTransaction();
}
