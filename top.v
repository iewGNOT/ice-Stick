// ========================================================================
//  iCEstick voltage‑glitcher  —  Top‑level + tri‑state reset/power modules
//  Pure Verilog‑2005 implementation (no SystemVerilog syntax)
//  2025‑07‑19
// ========================================================================
`default_nettype none

// ─────────────────────────────────────────────────────────────────────────
//  Top‑level --------------------------------------------------------------
// ─────────────────────────────────────────────────────────────────────────
module top (
    // Clock
    input  wire clk,          // 12 MHz clock on iCEstick
    // FTDI UART
    input  wire uart_rx,
    output wire uart_tx,
    // Target‑device UART
    input  wire target_rx,
    output wire target_tx,
    // Control (active‑low, pulled‑up externally)
    inout  wire target_rst,   // reset to target MCU
    inout  wire power_ctrl,   // glitch MOSFET / VCC enable
    // LEDs
    output wire gled1,
    output wire rled1,
    output wire rled2,
    output wire rled3,
    output wire rled4
);

    // ─── PLL & power‑up delay ────────────────────────────────────────────
    wire sys_clk;
    wire pll_locked;
    pll pll_i (
        .clock_in (clk),
        .clock_out(sys_clk),
        .locked   (pll_locked)
    );

    // 500 µs 上电稳定等待（假设 sys_clk = 100 MHz，由 icepll 生成）
    reg [15:0] pwrup_cnt = 16'd0;
    wire init_done = (pwrup_cnt == 16'd50000);  // 100 MHz × 500 µs
    wire sys_ready = pll_locked & init_done;

    always @(posedge sys_clk) begin
        if (!pll_locked)
            pwrup_cnt <= 16'd0;
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

    // ─── Reset / glitch timing chain ─────────────────────────────────────
    wire reset_n;   // 0 = assert
    wire glitch_n;  // 0 = glitch window active

    resetter RST (
        .clk       (sys_clk),
        .enable    (tgt_reset_req),
        .active_low(reset_n)
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
        .active_low (glitch_n)
    );

    // ─── Tri‑state buffers (external pull‑ups defined in PCF) ────────────
    assign target_rst  = (reset_n  == 1'b0) ? 1'b0 : 1'bz;
    assign power_ctrl  = (glitch_n == 1'b0) ? 1'b0 : 1'bz;

    // ─── UART relay: target RX → PC TX ───────────────────────────────────
    assign uart_tx = target_rx;

    // ─── Status LEDs ─────────────────────────────────────────────────────
    assign gled1 = pll_locked;
    assign rled1 = sys_ready;
    assign rled2 = tgt_reset_req;
    assign rled3 = init_done;
    assign rled4 = 1'b0;

endmodule
