//2
`default_nettype none

module top (
    input  wire clk,
    input  wire uart_rx,
    output wire uart_tx,
    input  wire target_rx,
    output wire target_tx,
    output wire gled1,
    output wire target_rst,
    output wire power_ctrl
);

    wire sys_clk;
    wire locked;
    wire target_reset;
    wire start_offset_counter;
    wire start_duration_counter;
    wire [31:0] glitch_duration;
    wire [31:0] glitch_offset;
    wire short_active;
    wire wide_glitch;

    assign uart_tx = target_rx;
    assign gled1 = locked;

    pll my_pll (
        .clock_in  (clk),
        .clock_out (sys_clk),
        .locked    (locked)
    );

    command_processor command_processor (
        .clk                 (sys_clk),
        .din                 (uart_rx),
        .rst                 (!locked),
        .dout                (target_tx),
        .target_reset        (target_reset),
        .duration            (glitch_duration),
        .offset              (glitch_offset),
        .start_offset_counter(start_offset_counter)
    );

    resetter resetter (
        .clk        (sys_clk),
        .enable     (target_reset),
        .reset_line (target_rst),
        .wide_glitch(wide_glitch)
    );

    reg wg_d;
    wire wg_fall;
    always @(posedge sys_clk) wg_d <= wide_glitch;
    assign wg_fall = wg_d & ~wide_glitch;

    reg armed;
    always @(posedge sys_clk) begin
        if (target_reset) armed <= 1'b1;
        else if (wg_fall) armed <= 1'b0;
    end

    reg start_pulse;
    always @(posedge sys_clk) begin
        start_pulse <= 1'b0;
        if (wg_fall && armed) start_pulse <= 1'b1;
    end

    wire counters_reset = target_reset | wide_glitch;

    offset_counter offset_counter (
        .clk    (sys_clk),
        .reset  (counters_reset),
        .enable (start_pulse),
        .din    (glitch_offset),
        .done   (start_duration_counter)
    );

    duration_counter duration_counter (
        .clk         (sys_clk),
        .reset       (counters_reset),
        .enable      (start_duration_counter),
        .din         (glitch_duration),
        .power_select(short_active)
    );

    assign power_ctrl = wide_glitch | short_active;

endmodule
