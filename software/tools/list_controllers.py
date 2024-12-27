import serial
import serial.tools.list_ports

print('\n')

for p in serial.tools.list_ports.comports():
	print(p.__dict__)
	print('\n')