import serial

def read_from_stm32(port = "/dev/ttyUSB0", baudrate = 1152000):
    ser = serial.Serial(port, baudrate)
    while True:
        line = ser.readline().decode().strip()