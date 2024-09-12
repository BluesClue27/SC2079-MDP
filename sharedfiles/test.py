import serial
import time

ser = serial.Serial('/dev/ttyUSB0',115200,timeout=1)

time.sleep(2)

ser.write(b'02030')

response = ser.readline().decode('utf-8').strip()
print("Received from STM32: ", response)

ser.close()
