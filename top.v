// ========================================================================
//  iCEstick voltage‑glitcher  —  Top‑level + tri‑state reset/power modules
//  (unified file: top.v, resetter.v, duration_counter.v)
//  2025‑07‑19  •  tri‑state outputs compatible with pull‑up PCF
// ========================================================================
`default_nettype none

// ─────────────────────────────────────────────────────────────────────────
//  Top‑level ----------------------------------------------------------------
// ─────────────────────────────────────────────────────────────────────────
module top (
    input  wire clk,          // 12 MHz clock on iCEstick
    // FTDI UART
    input  wire uart_rx,
    output wire uart_tx,
    // Target‑device UART
    input  wire target_rx,
    output wire target_tx,
    // Control
    output wire target_rst,   // active‑low reset to target MCU (tri‑state)
    output wire power_ctrl,   // active‑low glitch FET / VCC enable (tri‑state)
    // LEDs
    output wire gled1, rled1, rled2, rled3, rled4
);

    // ─── PLL & power‑up delay ────────────────────────────────────────────
    wire sys_clk;
    wire pll_locked;
    pll pll_i (
        .clock_in (clk),
        .clock_out(sys_clk),
        .locked   (pll_locked)
    );

    // 500 µs 延时（假设 PLL 100 MHz）
    reg  [15:0] pwrup_cnt = 0;
    wire init_done = (pwrup_cnt == 16'd50000);
    wire sys_ready = pll_locked & init_done;

    always @(posedge sys_clk) begin
        if (!pll_locked)
            pwrup_cnt <= 0;
        else if (!init_done)
            pwrup_cnt <= pwrup_cnt + 1'b1;
    end

    // ─── Command‑processor ───────────────────────────────────────────────
    wire        start_ofs_cnt;
    wire        start_dur_cnt;
    wire [31:0] glitch_ofs;
    wire [31:0] glitch_dur;
    wire        tgt_reset_req;

    command_processor CMD (
        .clk                 (sys_clk),
        .rst                 (!sys_ready),
        .din                 (uart_rx),
        .dout                (target_tx),
        .target_reset        (tgt_reset_req),
        .duration            (glitch_dur),
        .offset              (glitch_ofs),
        .start_offset_counter(start_ofs_cnt)
    );

    // ─── Reset / glitch timing chain ────────────────────────────────────
    wire reset_active_low;   // low when asserting reset
    wire glitch_active_low;  // low when glitch window active

    // reset pulse generator (~100 ms)
    resetter RST (
        .clk   (sys_clk),
        .enable(tgt_reset_req),
        .active_low(reset_active_low)
    );

    offset_counter OFS (
        .clk   (sys_clk),
        .reset (tgt_reset_req),
        .enable(start_ofs_cnt),
        .din   (glitch_ofs),
        .done  (start_dur_cnt)
    );

    duration_counter DUR (
        .clk        (sys_clk),
        .reset      (tgt_reset_req),
        .enable     (start_dur_cnt),
        .din        (glitch_dur),
        .active_low (glitch_active_low)
    );

    // ─── Tri‑state buffers (pull‑up enabled in .pcf) ─────────────────────
    assign target_rst =  reset_active_low ? 1'b0 : 1'bz;
    assign power_ctrl = glitch_active_low ? 1'b0 : 1'bz;

    // ─── UART relay: target RX → PC TX ───────────────────────────────────
    assign uart_tx = target_rx;

    // ─── Status LEDs ─────────────────────────────────────────────────────
    assign gled1 = pll_locked;
    assign rled1 = sys_ready;
    assign rled2 = tgt_reset_req;
    assign rled3 = init_done;
    assign rled4 = 1'b0;

endmodule
