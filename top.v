`default_nettype none

module top (
    input wire          clk,
    input wire          uart_rx,
    output wire         uart_tx,
    input wire          target_rx,
    output wire         target_tx,
    output wire         gled1,
    output wire         rled1,
    output wire         rled2,
    output wire         rled3,
    output wire         rled4,
    output wire         target_rst,
    output wire         power_ctrl
);

    wire sys_clk;
    wire locked;
    wire target_reset;
    wire start_offset_counter;
    wire start_duration_counter;
    wire [31:0] glitch_duration;
    wire [31:0] glitch_offset;
    wire uart_rx_internal;

    assign uart_tx = target_rx;
    assign gled1 = locked;
    assign rled1 = 1'b0;
    assign rled2 = 1'b0;
    assign rled3 = 1'b0;
    assign rled4 = 1'b0;

    SB_IO #(
        .PIN_TYPE(6'b000001),
        .PULLUP(1'b1)
    ) sb_uart_rx (
        .PACKAGE_PIN(uart_rx),
        .D_IN_0(uart_rx_internal)
    );

    pll my_pll(
        .clock_in(clk),
        .clock_out(sys_clk),
        .locked(locked)
    );

    command_processor command_processor (
        .clk(sys_clk),
        .din(uart_rx_internal),
        .rst(!locked),
        .dout(target_tx),
        .target_reset(target_reset),
        .duration(glitch_duration),
        .offset(glitch_offset),
        .start_offset_counter(start_offset_counter)
    );

    resetter resetter(
        .clk(sys_clk),
        .enable(target_reset),
        .reset_line(target_rst)
    );

    offset_counter offset_counter(
        .clk(sys_clk),
        .reset(target_reset),
        .enable(start_offset_counter),
        .din(glitch_offset),
        .done(start_duration_counter)
    );

    duration_counter duration_counter(
        .clk(sys_clk),
        .reset(target_reset),
        .enable(start_duration_counter),
        .din(glitch_duration),
        .power_select(power_ctrl)
    );

endmodule
