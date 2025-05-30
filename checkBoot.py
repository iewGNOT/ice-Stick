from pylibftdi import Device, INTERFACE_B
from struct import pack
from time import sleep

# Initialize FTDI device
dev = Device(mode='b', interface_select=INTERFACE_B)
dev.baudrate = 115200

EOL = b"\r\n"
CMD_PASSTHROUGH = b"\x00"

# Send '?' as raw 0x3F byte through passthrough
def send_question_mark():
    dev.write(CMD_PASSTHROUGH + pack("B", 1) + b"\x3F")

# Read one line from the target
def read_line():
    line = b""
    while True:
        b1 = dev.read(1)
        if not b1:
            return None
        line += b1
        if line.endswith(EOL):
            return line.strip()

print("[*] Sending '?' (0x3F) to target every 1s. Press Ctrl+C to exit.")
while True:
    send_question_mark()
    resp = read_line()
    print("[Response]", resp)
    sleep(1)
