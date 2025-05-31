#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pylibftdi import Device, INTERFACE_B
from time import sleep
from struct import pack
from codecs import decode
from binascii import hexlify

CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
CRYSTAL_FREQ = b"10000" + CRLF
CMD_PASSTHROUGH = b"\x00"
DUMP_FILE = "flash_crp0.dump"

class FlashDumper:
    def __init__(self):
        self.dev = Device(mode='b', interface_select=INTERFACE_B)
        self.dev.baudrate = 115200

    def toggle_reset(self):
        # 控制 RESET 引脚（假设为 CBUS0）
        print("[*] Resetting target via FTDI CBUS0...")
        self.dev.driver_control = True
        self.dev.ftdi_fn.ftdi_set_bitmode(0x01, 0x01)  # CBUS0 output
        self.dev.ftdi_fn.ftdi_write_data(bytes([0x00]))  # Reset LOW
        sleep(0.1)
        self.dev.ftdi_fn.ftdi_write_data(bytes([0x01]))  # Reset HIGH
        sleep(0.3)

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
        print("[*] Synchronizing with bootloader...")

        self.dev.write(CMD_PASSTHROUGH + pack("B", 1) + b"?")
        resp = self.read_data(echo=False)
        print("[*] Got:", resp)
        if resp != SYNCHRONIZED:
            return False

        self.dev.write(CMD_PASSTHROUGH + pack("B", len(SYNCHRONIZED + CRLF)) + SYNCHRONIZED + CRLF)
        resp = self.read_data()
        print("[*] Got OK?", resp)
        if resp != OK:
            print("[!] No OK after sync, trying anyway...")

        self.dev.write(CMD_PASSTHROUGH + pack("B", len(CRYSTAL_FREQ)) + CRYSTAL_FREQ)
        resp = self.read_data()
        print("[*] Clock response:", resp)

        return True

    def send_command(self, command, resp_lines=1):
        cmd = command + b"\r"
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd)

        lines = []
        code = self.read_data()
        lines.append(code)

        if code != b"0":
            return lines

        for _ in range(resp_lines):
            line = self.read_data()
            lines.append(line)

        return lines

    def dump(self):
        print("[*] Dumping flash...")
        with open(DUMP_FILE, "wb") as f:
            for i in range(0x8000 // 32):
                self.send_command(OK, 1)
                addr = i * 32
                cmd = f"R {addr} 32".encode()
                resp = self.send_command(cmd, 1)

                if resp[0] != b"0":
                    print(f"[!] Fail at {hex(addr)}: {resp}")
                    continue

                data = b"begin 666 <x>\n" + resp[1] + b" \n \nend\n"
                raw = decode(data, "uu")
                print(f"[{hex(addr)}] {hexlify(raw).decode()}")
                f.write(raw)

        print(f"[✓] Flash dump saved to {DUMP_FILE}")

    def run(self):
        self.toggle_reset()
        if self.synchronize():
            self.dump()
        else:
            print("[-] Synchronization failed.")

if __name__ == '__main__':
    FlashDumper().run()
