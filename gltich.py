def _write_intel_hex(self, bin_bytes: bytes, out_path: str, base_addr=0, rec_len=16):
    def rec(addr16, rtype, data):
        ll   = len(data)
        a_hi = (addr16 >> 8) & 0xFF
        a_lo = addr16 & 0xFF
        b = bytes([ll, a_hi, a_lo, rtype]) + data
        cks = ((~(sum(b) & 0xFF) + 1) & 0xFF)
        return ":" + "".join(f"{x:02X}" for x in b + bytes([cks])) + "\n"
    with open(out_path, "w", newline="\n") as f:
        addr = base_addr & 0xFFFF
        ext  = (base_addr >> 16) & 0xFFFF
        if ext:
            f.write(rec(0x0000, 0x04, bytes([(ext >> 8) & 0xFF, ext & 0xFF])))
        i = 0
        n = len(bin_bytes)
        while i < n:
            chunk = bin_bytes[i:i+16]
            f.write(rec(addr, 0x00, chunk))
            i    += len(chunk)
            addr  = (addr + len(chunk)) & 0xFFFF
            if addr == 0 and i < n:
                ext += 1
                f.write(rec(0x0000, 0x04, bytes([(ext >> 8) & 0xFF, ext & 0xFF])))
        f.write(":00000001FF\n")

def dump_memory(self):
    buf = bytearray()
    # 建议这里把 1023 改为 1024，确实是 32 KiB / 32B = 1024 块
    for i in range(1024):
        resp = self.send_target_command(OK, 1, True, b"\r\n")
        cmd = "R {} 32".format(i * 32).encode("utf-8")
        resp = self.send_target_command(cmd, 1, True, b"\r\n")
        if resp[0] == b"0":
            data = b"begin 666 <data>\n" + resp[1] + b" \n \nend\n"
            raw = decode(data, "uu")
            print(fg.li_blue + bytes.hex(raw) + fg.rs)
            buf.extend(raw)

    with open(DUMP_FILE_BIN, "wb") as f:
        f.write(buf)

    # 这里默认以 0x0000 为基地址输出 HEX；如果需要别的基址自行调整
    self._write_intel_hex(bytes(buf), DUMP_FILE_HEX, base_addr=0x0000, rec_len=16)

    print(fg.li_white + "[*] Wrote '{}' ({} bytes) and '{}'".format(
        DUMP_FILE_BIN, len(buf), DUMP_FILE_HEX) + fg.rs)
