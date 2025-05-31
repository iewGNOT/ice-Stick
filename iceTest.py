#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from binascii import hexlify
from codecs import decode
from pylibftdi import Device, BitBangDevice
from struct import pack
from time import sleep

# === 常量定义 ===
CRLF = b"\r\n"
SYNC = b"Synchronized"
OK = b"OK"
CRYSTAL_FREQ = b"10000" + CRLF
DUMP_FILE = "flash_auto_crp0.dump"
CMD_PASSTHROUGH = b"\x00"
MAX_ADDR = 0x8000  # 32KB

# CBUS 控制定义（根据接线自定义）
# 比如：CBUS0 控 VCC，CBUS1 控 RESET
VCC_BIT = 0x01  # bit 0
RST_BIT = 0x02  # bit 1

class AutoDumper:
    def __init__(self):
        self.dev = Device(mode='b')
        self.dev.baudrate = 115200
        self.gpio = BitBangDevice()

    def power_cycle_into_bootloader(self):
        print("[*] 自动复位并进入 bootloader...")
        self.gpio.direction = 0xFF  # 所有 pin 输出

        # 步骤：断电 + RESET 高 -> 供电 -> RESET 低
        self.gpio.port = 0x00              # 全部拉低 = 断电
        sleep(0.05)
        self.gpio.port = VCC_BIT           # 上电但 RESET 高
        sleep(0.05)
        self.gpio.port = VCC_BIT | RST_BIT # RESET 拉低
        sleep(0.1)
        self.gpio.port = VCC_BIT           # RESET 释放
        sleep(0.05)

    def read_line(self, terminator=b"\r\n", echo=True):
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
        print("[*] 与 MCU 同步...")
        self.dev.write(CMD_PASSTHROUGH + pack("B", 1) + b"?")
        resp = self.read_line(echo=False)
        if resp != SYNC:
            print("[-] Sync failed:", resp)
            return False

        self.dev.write(CMD_PASSTHROUGH + pack("B", len(SYNC + CRLF)) + SYNC + CRLF)
        if self.read_line() != OK:
            print("[!] No OK after SYNC")
            return False

        self.dev.write(CMD_PASSTHROUGH + pack("B", len(CRYSTAL_FREQ)) + CRYSTAL_FREQ)
        if self.read_line() != OK:
            print("[!] No OK after crystal freq")
            return False

        print("[+] 同步成功！")
        return True

    def send_cmd(self, cmd_str, expect=1):
        cmd = cmd_str + b"\r"
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(cmd)) + cmd)
        resp = [self.read_line()]
        if resp[0] != b"0":
            return resp
        for _ in range(expect):
            resp.append(self.read_line())
        return resp

    def dump_flash(self):
        print("[*] 开始 dump flash...")
        with open(DUMP_FILE, "wb") as f:
            for i in range(MAX_ADDR // 32):
                addr = i * 32
                self.send_cmd(OK, 1)  # dummy OK
                resp = self.send_cmd(f"R {addr} 32".encode(), 1)
                if resp[0] != b"0":
                    print(f"[!] 失败 @ {hex(addr)}: {resp}")
                    continue
                data = b"begin 666 <data>\n" + resp[1] + b" \n \nend\n"
                raw = decode(data, "uu")
                f.write(raw)
                print(f"[{hex(addr)}] {hexlify(raw).decode()}")
        print(f"[+] Dump 完成: {DUMP_FILE}")

    def run(self):
        self.power_cycle_into_bootloader()
        if self.synchronize():
            self.dump_flash()
        else:
            print("[-] 无法与目标同步。确认是否在 Bootloader 模式！")

if __name__ == '__main__':
    AutoDumper().run()
