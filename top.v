// ========================================================================
//  top.v — iCEstick voltage‑glitcher • tri‑state reset / power outputs
// ========================================================================
`default_nettype none

module top (
    input  wire clk,          // 12 MHz on‑board
    // FTDI UART
    input  wire uart_rx,
    output wire uart_tx,
    // Target‑device UART
    input  wire target_rx,
    output wire target_tx,
    // ——— 两个信号改用 inout，才能做 0/Z 三态 ———
    inout  wire target_rst,   // active‑low reset to target
    inout  wire power_ctrl,   // active‑low glitch MOSFET
    // LEDs
    output wire gled1, rled1, rled2, rled3, rled4
);

    // ─── 1. PLL ─────────────────────────────────────────────────────────
    wire sys_clk, pll_locked;
    pll pll_i (.clock_in(clk), .clock_out(sys_clk), .locked(pll_locked));

    // 500 µs power‑up delay (@100 MHz)
    reg [15:0] pwr_cnt = 0;
    wire init_done = (pwr_cnt == 16'd50000);
    wire sys_ready = pll_locked & init_done;
    always @(posedge sys_clk)
        if (!pll_locked) pwr_cnt <= 0;
        else if (!init_done) pwr_cnt <= pwr_cnt + 1'b1;

    // ─── 2. Command processor ───────────────────────────────────────────
    wire start_ofs_cnt, start_dur_cnt;
    wire [31:0] glitch_ofs, glitch_dur;
    wire tgt_reset_req;

    command_processor CMD (
        .clk(sys_clk), .rst(!sys_ready),
        .din(uart_rx), .dout(target_tx),
        .target_reset(tgt_reset_req),
        .duration(glitch_dur), .offset(glitch_ofs),
        .start_offset_counter(start_ofs_cnt)
    );

    // ─── 3. Reset & counters ────────────────────────────────────────────
    wire rst_n;          // 0 = assert   (active‑low)
    wire glitch_n;       // 0 = glitch window active

    resetter RST (.clk(sys_clk), .enable(tgt_reset_req), .active_low(rst_n));

    offset_counter OFS (
        .clk(sys_clk), .reset(tgt_reset_req),
        .enable(start_ofs_cnt), .din(glitch_ofs), .done(start_dur_cnt)
    );

    duration_counter DUR (
        .clk(sys_clk), .reset(tgt_reset_req),
        .enable(start_dur_cnt), .din(glitch_dur),
        .active_low(glitch_n)
    );

    // ─── 4. Tri‑state buffers  (端口已是 inout) ─────────────────────────
    assign target_rst  = (rst_n   == 1'b0) ? 1'b0 : 1'bz;
    assign power_ctrl  = (glitch_n == 1'b0) ? 1'b0 : 1'bz;

    // ─── 5. UART relay: target → PC ——————————————
    assign uart_tx = target_rx;

    // ─── 6. LEDs ————————————————————————————————
    assign gled1 = pll_locked;
    assign rled1 = sys_ready;
    assign rled2 = tgt_reset_req;
    assign rled3 = init_done;
    assign rled4 = 1'b0;
endmodule
