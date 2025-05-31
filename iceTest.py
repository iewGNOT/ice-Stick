    def run(self):
        """CRP0: skip glitching, directly synchronize and dump memory."""
        
        print(fg.li_white + "[*] CRP0 assumed. Skipping glitching, synchronizing..." + fg.rs)
        
        if not self.synchronize():
            print(fg.li_red + "[-] Synchronization failed. Check UART wiring and bootloader mode." + fg.rs)
            return False

        print(fg.li_white + "[*] Testing read access with 'R 0 4'..." + fg.rs)
        resp = self.send_target_command(b"R 0 4", 1, True, b"\r\n")
        print("[DEBUG] R 0 4 response:", resp)

        if isinstance(resp, list) and resp[0] == b"0":
            print(fg.green + "[*] Flash read confirmed. Proceeding to dump full memory." + fg.rs)
        else:
            print(fg.li_red + "[-] Read test failed. Is the device really in CRP0 bootloader mode?" + fg.rs)
            return False

        print(fg.li_white + "[*] Dumping full flash memory..." + fg.rs)
        self.dump_memory()

        print(fg.green + "[✓] Flash dump complete." + fg.rs)
        return True
