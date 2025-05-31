#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Minimal Flash-Dump Script for iCEstick (CRP0 chips)

This script opens the FTDI interface, synchronizes with the iCEstick
bootloader, and reads out the entire 32 KB flash (in 32‐byte chunks),
saving it to 'flash_crp0.dump'.

Usage:
    python3 ice_dump.py

Requirements:
    pip install pylibftdi
"""

from binascii import hexlify
from codecs import decode
from pylibftdi import Device, INTERFACE_B
from struct import pack
from time import sleep

# UART framing
CRLF = b"\r\n"
SYNCHRONIZED = b"Synchronized"
OK = b"OK"
CRYSTAL_FREQ = b"10000" + CRLF

# Passthrough command prefix for FPGA
CMD_PASSTHROUGH = b"\x00"

# Output file
DUMP_FILE = "flash_crp0.dump"

# Maximum loop‐back bytes before timing out
MAX_BYTES = 200


class FlashDumper:
    def __init__(self):
        # Open FTDI in bitbang‐passthrough mode (INTERFACE_B)
        self.dev = Device(mode="b", interface_select=INTERFACE_B)
        self.dev.baudrate = 115200
        sleep(0.1)  # give FTDI a moment to set up

    def read_line(self, terminator=CRLF, echo=True):
        """
        Read until we see the terminator (CRLF).
        If echo=True, first consume one echoed '\r' from previous write.
        Returns the bytes (without the trailing CRLF), or b"TIMEOUT" on failure.
        """
        if echo:
            # Consume the echoed carriage return from the last command
            loop_count = 0
            while True:
                c = self.dev.read(1)
                if c == b"\r" or loop_count > MAX_BYTES:
                    break
                loop_count += 1

        data = b""
        loop_count = 0
        while True:
            chunk = self.dev.read(1)
            if not chunk:
                return b"TIMEOUT"
            data += chunk
            if data.endswith(terminator):
                return data[:-len(terminator)]
            loop_count += 1
            if loop_count > MAX_BYTES:
                return b"TIMEOUT"

    def synchronize(self) -> bool:
        """
        Perform the 3‐step synchronisation handshake with the bootloader:
         1) send "?"   → expect "Synchronized"
         2) send "Synchronized\r\n" → expect "OK"
         3) send "10000\r\n"    → expect "OK"
        Returns True on success, False otherwise.
        """
        # 1) send "?"
        self.dev.write(CMD_PASSTHROUGH + pack("B", 1) + b"?")
        resp = self.read_line(echo=False)
        if resp != SYNCHRONIZED:
            print(f"[-] Step 1 failed, got: {resp!r}")
            return False

        # 2) send "Synchronized\r\n"
        reply = SYNCHRONIZED + CRLF
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(reply)) + reply)
        resp = self.read_line()
        if resp != OK:
            print(f"[-] Step 2 failed, got: {resp!r}")
            return False

        # 3) send the crystal frequency (kHz)
        payload = CRYSTAL_FREQ
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(payload)) + payload)
        resp = self.read_line()
        if resp != OK:
            print(f"[-] Step 3 failed, got: {resp!r}")
            return False

        print("[+] Synchronized with target bootloader.")
        return True

    def send_command(self, cmd_bytes: bytes, response_lines: int = 1):
        """
        Send a command (without the trailing CR) to the target.
        Args:
          cmd_bytes: a byte‐string like b"R 0 32"
          response_lines: number of data lines to read *after* the "0" return code.
        Returns:
          A list of byte‐strings. The first item is the return code (b"0" or error code),
          then up to response_lines of data (each line without CRLF). 
          If a read times out, `"TIMEOUT"` is returned instead of the byte list.
        """
        full_cmd = cmd_bytes + b"\r"
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(full_cmd)) + full_cmd)

        # Read return code line
        ret = self.read_line()
        if ret == b"TIMEOUT":
            return b"TIMEOUT"

        responses = [ret]
        if ret != b"0":
            # error code, no data follows
            return responses

        # read the specified number of data lines
        for _ in range(response_lines):
            data_line = self.read_line()
            if data_line == b"TIMEOUT":
                return b"TIMEOUT"
            responses.append(data_line)

        return responses

    def dump_flash(self):
        """
        Read the entire 32 KB flash (0x0000–0x7FFF), in 32‐byte chunks.
        Saves raw 32 byte blocks (decoded from UUencode) to DUMP_FILE.
        Also prints each chunk’s hex on stdout.
        """
        total_size = 32 * 1024
        chunk_size = 32

        with open(DUMP_FILE, "wb") as f:
            # There are total_size / chunk_size reads → 1024 reads
            for i in range(total_size // chunk_size):
                addr = i * chunk_size

                # 1) Send dummy OK (to keep bootloader in sync)
                ack = self.send_command(OK, response_lines=1)
                if ack == b"TIMEOUT" or ack[0] != b"0":
                    print(f"[!] No OK before read @ 0x{addr:04X}: {ack}")
                    # Try to re‐sync once and continue
                    if not self.synchronize():
                        print("[-] Resync failed. Aborting dump.")
                        return
                    # Retry sending OK once more after re‐sync
                    ack = self.send_command(OK, response_lines=1)
                    if ack == b"TIMEOUT" or ack[0] != b"0":
                        print(f"[!] Still no OK @ 0x{addr:04X}. Skipping.")
                        continue

                # 2) Send the read command “R <addr> 32”
                cmd_read = f"R {addr} {chunk_size}".encode("ascii")
                resp = self.send_command(cmd_read, response_lines=1)

                if resp == b"TIMEOUT":
                    print(f"[-] TIMEOUT reading @ 0x{addr:04X}. Retrying…")
                    # Attempt a resync and retry once
                    if not self.synchronize():
                        print("[-] Resync failed. Aborting dump.")
                        return
                    resp = self.send_command(cmd_read, response_lines=1)
                    if resp == b"TIMEOUT" or resp[0] != b"0":
                        print(f"[!] Still failed @ 0x{addr:04X}: {resp}. Skipping.")
                        continue

                if resp[0] != b"0":
                    print(f"[-] Read error @ 0x{addr:04X}: {resp}")
                    continue

                uu_line = resp[1]
                if not uu_line or len(uu_line) < 2:
                    print(f"[!] UU line too short @ 0x{addr:04X}: {uu_line!r}")
                    continue

                # 3) UU‐decode it
                try:
                    wrapper = b"begin 666 <data>\n" + uu_line + b" \n \nend\n"
                    raw_block = decode(wrapper, "uu")
                    f.write(raw_block)
                    print(f"[0x{addr:04X}] {hexlify(raw_block).decode()}")
                except Exception as e:
                    print(f"[!] Decode error @ 0x{addr:04X}: {e}")
                    continue

        print(f"[+] Flash dump complete → {DUMP_FILE}")

    def run(self):
        """
        Top‐level: synchronize then dump.
        """
        if not self.synchronize():
            print("[-] Synchronization failed. Check UART wiring & Bootloader mode.")
            return
        self.dump_flash()


if __name__ == "__main__":
    dumper = FlashDumper()
    dumper.run()
