#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from pyftdi.gpio import GpioAsyncController
from pylibftdi import Device, INTERFACE_B
from struct import pack
from codecs import decode
from binascii import hexlify
import time

# ========== 常量 ==========
CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
CRYSTAL_FREQ = b"10000" + CRLF
DUMP_FILE = "flash_crp0.dump"
CMD_PASSTHROUGH = b"\x00"  # FPGA passthrough command

# ========== 自动复位 ==========
def auto_reset():
    print("[*] Resetting target via FTDI CBUS0 ...")
    gpio = GpioAsyncController()
    gpio.configure('ftdi://::/1', direction=0x01)  # CBUS0 = output
    gpio.write(0x01)  # 拉高（上电）
    time.sleep(0.05)
    gpio.write(0x00)  # 拉低（复位）
    gpio.close()
    print("[+] Reset complete.")

# ========== 主类 ==========
class FlashDumper:
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
        print("[*] Synchronizing ...")
        self.dev.write(CMD_PASSTHROUGH + pack("B", 1) + b"?")
        resp = self.read_data(echo=False)
        print(f"[DEBUG] response 1: {resp}")
        if resp != SYNCHRONIZED:
            return False

        self.dev.write(CMD_PASSTHROUGH + pack("B", len(SYNCHRONIZED + CRLF)) + SYNCHRONIZED + CRLF)
        resp = self.read_data()
        print(f"[DEBUG] response 2: {resp}")
        if resp != OK:
            return False

        self.dev.write(CMD_PASSTHROUGH + pack("B", len(CRYSTAL_FREQ)) + CRYSTAL_FREQ)
        resp = self.read_data()
        print(f"[DEBUG] response 3: {resp}")
        if resp != OK:
            return False

        print("[+] Synchronized with bootloader.")
        return True

    def send_target_command(self, command, response_count=1):
        cmd = command + b"\r"
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd)
        resp = []
        line = self.read_data()
        resp.append(line)
        if line != b"0":
            return resp
        for _ in range(response_count):
            line = self.read_data()
            resp.append(line)
        return resp

    def dump_flash(self):
        print("[*] Starting flash dump ...")
        with open(DUMP_FILE, "wb") as f:
            for i in range(0x8000 // 32):
                self.send_target_command(OK, 1)  # Dummy OK
                addr = i * 32
                cmd = f"R {addr} 32".encode("utf-8")
                resp = self.send_target_command(cmd, 1)
                if resp[0] != b"0":
                    print(f"[!] Failed at {hex(addr)}: {resp}")
                    continue
                data = b"begin 666 <data>\n" + resp[1] + b" \n \nend\n"
                raw = decode(data, "uu")
                f.write(raw)
                print(f"[{hex(addr)}] {hexlify(raw).decode()}")
        print(f"[+] Dump complete. Saved to {DUMP_FILE}")

# ========== 主程序 ==========
if __name__ == "__main__":
    auto_reset()
    time.sleep(0.2)  # 等待 MCU 上电
    dumper = FlashDumper()
    if dumper.synchronize():
        dumper.dump_flash()
    else:
        print("[-] Bootloader sync failed. Check P0_1 and RESET timing.")
