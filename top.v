`default_nettype none

module top (
    input  wire clk,
    input  wire uart_rx,
    output wire uart_tx,
    input  wire target_rx,
    output wire target_tx,
    output wire gled1,
    output wire rled1,
    output wire rled2,
    output wire rled3,
    output wire rled4,
    output wire target_rst,
    output wire power_ctrl
);

    wire sys_clk;
    wire pll_locked;

    pll my_pll (
        .clock_in (clk),
        .clock_out(sys_clk),
        .locked   (pll_locked)
    );

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

    wire pulse_done;

    duration_counter DUR (
        .clk         (sys_clk),
        .reset       (tgt_reset_req),
        .enable      (start_dur_cnt),
        .din         (glitch_dur),
        .power_select(power_ctrl),
        .pulse_done  (pulse_done)
    );

    assign uart_tx = target_rx;

    assign gled1 = pll_locked;
    assign rled1 = 1'b0;
    assign rled2 = 1'b0;
    assign rled3 = 1'b0;
    assign rled4 = 1'b0;

endmodule
