import serial
import serial.tools.list_ports

arduino_ports = [
        p.device
        for p in serial.tools.list_ports.comports()
        if 'Arduino' in p.description]
if not arduino_ports:
    raise IOError("No Arduino found")
if len(arduino_ports) > 1:
    warnings.warn('Multiple Arduinos found - using the first')
else:
    print('Using Arduino found at : {}'.format(arduino_ports[0]))

# establish serial communication
arduino = serial.Serial(arduino_ports[0],2000000)

rx_buffer_length = 9

while True:
    while arduino.in_waiting==0:
        pass
    while arduino.in_waiting % rx_buffer_length != 0:
        pass

    num_bytes_in_rx_buffer = arduino.in_waiting

    # get rid of old data
    if num_bytes_in_rx_buffer > rx_buffer_length:
        print('getting rid of old data')
        for i in range(num_bytes_in_rx_buffer-rx_buffer_length):
            arduino.read()

    # read the buffer
    data=[]
    for i in range(rx_buffer_length):
        data.append(ord(arduino.read()))

    print(int(data[2])+256*int(data[1])+65536*int(data[0])-(256**3)/2)
