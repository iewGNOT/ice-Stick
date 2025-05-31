#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from binascii import hexlify
from codecs import decode
from pylibftdi import Device, INTERFACE_B
from struct import pack

CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
CRYSTAL_FREQ = b"10000" + CRLF
DUMP_FILE = "flash_crp0.dump"

class FlashDumper:
    def __init__(self):
        self.dev = Device(mode='b', interface_select=INTERFACE_B)
        self.dev.baudrate = 115200

    def read_line(self, terminator=b"\r\n"):
        buf = b""
        while True:
            b = self.dev.read(1)
            if not b:
                return b"TIMEOUT"
            buf += b
            if buf.endswith(terminator):
                return buf.replace(terminator, b"")

    def send_cmd(self, raw):
        payload = b"\x00" + pack("B", len(raw)) + raw
        self.dev.write(payload)

    def sync(self):
        print("[*] Synchronizing...")
        self.send_cmd(b"?")
        if self.read_line() != SYNCHRONIZED:
            return False
        self.send_cmd(SYNCHRONIZED + CRLF)
        if self.read_line() != OK:
            return False
        self.send_cmd(CRYSTAL_FREQ)
        if self.read_line() != OK:
            return False
        print("[+] Synchronized.")
        return True

    def dump(self):
        with open(DUMP_FILE, "wb") as f:
            for addr in range(0, 0x8000, 32):  # 32 KB
                # ACK
                self.send_cmd(OK + b"\r")
                if self.read_line() != b"0":
                    print(f"[!] No OK before R @ {hex(addr)}")
                    continue

                # Read command
                rcmd = f"R {addr} 32".encode()
                self.send_cmd(rcmd + b"\r")

                if self.read_line() != b"0":
                    print(f"[!] Read failed @ {hex(addr)}")
                    continue

                line = self.read_line()
                if not line:
                    print(f"[!] No data @ {hex(addr)}")
                    continue

                try:
                    uu = b"begin 666 <data>\n" + line + b" \n \nend\n"
                    raw = decode(uu, "uu")
                    f.write(raw)
                    print(f"[{hex(addr)}] {hexlify(raw).decode()}")
                except Exception as e:
                    print(f"[!] Decode error @ {hex(addr)}: {e}")
                    continue

        print(f"[✓] Dump complete → {DUMP_FILE}")

if __name__ == "__main__":
    dumper = FlashDumper()
    if dumper.sync():
        dumper.dump()
    else:
        print("[-] Sync failed. Is the target in bootloader mode?")
