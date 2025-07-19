/*
  iCEstick Glitcher (top.v)

  by Matthias Deeg (@matthiasdeeg, matthias.deeg@syss.de)

  Simple voltage glitcher for a Lattice iCEstick Evaluation Kit

  Based on and inspired by glitcher implementations
  by Dmitry Nedospasov (@nedos) and Grazfather (@Grazfather)
*/

`default_nettype none

module top
(
    input  wire clk,         // 12 MHz on iCEstick
    input  wire uart_rx,     // FTDI‑TX → FPGA
    output wire uart_tx,     // FPGA   → FTDI‑RX
    input  wire target_rx,   // Target TX → FPGA
    output wire target_tx,   // FPGA       → Target RX

    output wire gled1,       // green LED
    output wire rled1,
    output wire rled2,
    output wire rled3,
    output wire rled4,

    output wire target_rst,  // active‑low reset pulse to target
    output wire power_ctrl   // active‑low glitch MOSFET / VCC switch
);

    /* ───────────────────────────────
       1.  Clock PLL (default 100 MHz)
       ─────────────────────────────── */
    wire sys_clk;
    wire pll_locked;

    pll my_pll (
        .clock_in (clk),
        .clock_out(sys_clk),
        .locked   (pll_locked)
    );

    /* ───────────────────────────────
       2.  Command‑processor (USB‑UART)
       ─────────────────────────────── */
    wire        tgt_reset_req;
    wire        start_ofs_cnt;
    wire        start_dur_cnt;
    wire [31:0] glitch_ofs;
    wire [31:0] glitch_dur;

    command_processor CMD (
        .clk                 (sys_clk),
        .rst                 (!pll_locked),
        .din                 (uart_rx),
        .dout                (target_tx),
        .target_reset        (tgt_reset_req),
        .duration            (glitch_dur),
        .offset              (glitch_ofs),
        .start_offset_counter(start_ofs_cnt)
    );

    /* ───────────────────────────────
       3.  Reset & glitch timing chain
       ─────────────────────────────── */
    resetter RST (
        .clk        (sys_clk),
        .enable     (tgt_reset_req),
        .reset_line (target_rst)
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
        .power_select(power_ctrl)
    );

    /* ───────────────────────────────
       4.  UART relay: target → PC
       ─────────────────────────────── */
    assign uart_tx = target_rx;

    /* ───────────────────────────────
       5.  LEDs (same as原版)
       ─────────────────────────────── */
    assign gled1 = pll_locked;  // green LED shows PLL lock
    assign rled1 = 1'b0;
    assign rled2 = 1'b0;
    assign rled3 = 1'b0;
    assign rled4 = 1'b0;

endmodule
