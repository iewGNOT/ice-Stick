#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from binascii import hexlify
from codecs import decode
from pylibftdi import Device, INTERFACE_B
from struct import pack
from time import sleep

CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
CRYSTAL_FREQ = b"10000" + CRLF
DUMP_FILE = "flash_crp0.dump"
MAX_BYTES = 20

# FPGA passthrough command
CMD_PASSTHROUGH = b"\x00"

class GlitcherLite():
    def __init__(self):
        self.dev = Device(mode='b', interface_select=INTERFACE_B)
        self.dev.baudrate = 115200

    def read_data(self, terminator=b"\r\n", echo=True):
        if echo:
            while self.dev.read(1) != b"\r":
                pass
        data = b""
        while True:
            c = self.dev.read(1)
            if not c:
                return b"TIMEOUT"
            data += c
            if data.endswith(terminator):
                break
        return data.replace(terminator, b"")

    def synchronize(self):
        # Step 1: send '?'
        self.dev.write(CMD_PASSTHROUGH + pack("B", 1) + b"?")
        resp = self.read_data(echo=False)
        if resp != SYNCHRONIZED:
            print("[-] Sync failed:", resp)
            return False

        # Step 2: send 'Synchronized\r\n'
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(SYNCHRONIZED + CRLF)) + SYNCHRONIZED + CRLF)
        if self.read_data() != OK:
            print("[!] No OK after Synchronized")
            return False

        # Step 3: send clock
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(CRYSTAL_FREQ)) + CRYSTAL_FREQ)
        if self.read_data() != OK:
            print("[!] No OK after clock")
            return False

        print("[+] Synchronized with target.")
        return True

    def send_target_command(self, command, response_count=1):
        cmd = command + b"\r"
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd)
        resp = []

        # Read return code
        line = self.read_data()
        resp.append(line)
        if line != b"0":
            return resp

        # Read data lines
        for _ in range(response_count):
            line = self.read_data()
            resp.append(line)
        return resp

    def dump_flash(self):
        with open(DUMP_FILE, "wb") as f:
            for i in range(0x8000 // 32):  # 32KB flash / 32 bytes per read
                # Send dummy OK
                self.send_target_command(OK, 1)

                addr = i * 32
                cmd = f"R {addr} 32".encode("utf-8")
                resp = self.send_target_command(cmd, 1)
                if resp[0] != b"0":
                    print(f"[-] Failed to read at {hex(addr)}: {resp}")
                    continue
                data = b"begin 666 <data>\n" + resp[1] + b" \n \nend\n"
                raw = decode(data, "uu")
                f.write(raw)
                print(f"[{hex(addr)}] {hexlify(raw).decode()}")

        print(f"[+] Flash dump saved to {DUMP_FILE}")

    def run(self):
        if self.synchronize():
            self.dump_flash()
        else:
            print("[-] Sync failed. Check UART or bootloader mode.")

if __name__ == '__main__':
    GlitcherLite().run()
