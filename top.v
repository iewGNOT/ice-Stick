// ========================================================================
//  top.v  —  iCEstick voltage‑glitcher  •  UART relay + tri‑state outputs
//  2025‑07‑19  •  Adds pull‑up‑friendly Z‑state for target_rst & power_ctrl
// ========================================================================
`default_nettype none

module top (
    // ─── External clock ────────────────────────────────────────────────
    input  wire clk,          // 12 MHz on iCEstick

    // ─── FTDI UART (PC side) ───────────────────────────────────────────
    input  wire uart_rx,      // FTDI‑TX → FPGA
    output wire uart_tx,      // FPGA   → FTDI‑RX

    // ─── Target‑device UART ────────────────────────────────────────────
    input  wire target_rx,    // Target TX → FPGA
    output wire target_tx,    // FPGA       → Target RX

    // ─── Control / indicators ─────────────────────────────────────────
    output wire target_rst,   // Reset pin  (active‑low pulse)
    output wire power_ctrl,   // Glitch MOSFET / VCC enable (active‑low)
    output wire gled1, rled1, rled2, rled3, rled4
);

// ─────────────────────────────────────────────────────────────────────────
// 1.  PLL & power‑up delay
// ─────────────────────────────────────────────────────────────────────────
    wire sys_clk;
    wire pll_locked;
    pll pll_i (
        .clock_in (clk),
        .clock_out(sys_clk),
        .locked   (pll_locked)
    );

    // 500 µs power‑up delay after PLL lock (100 MHz × 500 µs = 50 000)
    reg  [15:0] pwrup_cnt = 0;
    wire init_done = (pwrup_cnt == 16'd50000);
    wire sys_ready = pll_locked & init_done;

    always @(posedge sys_clk) begin
        if (!pll_locked)
            pwrup_cnt <= 0;
        else if (!init_done)
            pwrup_cnt <= pwrup_cnt + 1'b1;
    end

// ─────────────────────────────────────────────────────────────────────────
// 2.  Command‑processor (handles USB‑UART commands)
// ─────────────────────────────────────────────────────────────────────────
    wire        start_ofs_cnt;
    wire        start_dur_cnt;
    wire [31:0] glitch_ofs;
    wire [31:0] glitch_dur;
    wire        tgt_reset_req;

    command_processor CMD (
        .clk                 (sys_clk),
        .rst                 (!sys_ready),
        .din                 (uart_rx),      // USB‑UART RX from PC
        .dout                (target_tx),    // Forward to target MCU
        .target_reset        (tgt_reset_req),
        .duration            (glitch_dur),
        .offset              (glitch_ofs),
        .start_offset_counter(start_ofs_cnt)
    );

// ─────────────────────────────────────────────────────────────────────────
// 3.  Reset & glitch timing chain
// ─────────────────────────────────────────────────────────────────────────
    wire rst_out;     // active‑low pulse from resetter
    wire glitch_out;  // active‑low from duration_counter

    resetter RST (
        .clk        (sys_clk),
        .enable     (tgt_reset_req),
        .reset_line (rst_out)      // ≈100 ms low when enable=1
    );

    offset_counter OFS (
        .clk   (sys_clk),
        .reset (tgt_reset_req),
        .enable(start_ofs_cnt),
        .din   (glitch_ofs),
        .done  (start_dur_cnt)
    );

    duration_counter DUR (
        .clk         (sys_clk),
        .reset       (tgt_reset_req),
        .enable      (start_dur_cnt),
        .din         (glitch_dur),
        .power_select(glitch_out)   // low → enable glitch MOSFET
    );

    // ─── Tri‑state buffers with pull‑ups enabled in .pcf ────────────────
    assign target_rst = (rst_out    == 1'b0) ? 1'b0 : 1'bz; // low when active else Z
    assign power_ctrl = (glitch_out == 1'b0) ? 1'b0 : 1'bz; // low when glitch else Z

// ─────────────────────────────────────────────────────────────────────────
// 4.  UART relay: target → PC (simple buffer)
// ─────────────────────────────────────────────────────────────────────────
    assign uart_tx = target_rx;   // no tri‑state needed, push‑pull from target

// ─────────────────────────────────────────────────────────────────────────
// 5.  Status LEDs
// ─────────────────────────────────────────────────────────────────────────
    assign gled1 = pll_locked;  // Green  : PLL locked
    assign rled1 = sys_ready;   // Red1   : system ready
    assign rled2 = tgt_reset_req; // Red2 : reset active
    assign rled3 = init_done;   // Red3   : power‑up delay done
    assign rled4 = 1'b0;        // Red4   : reserved

endmodule
