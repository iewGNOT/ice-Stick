`default_nettype none

module top (
    input wire clk,
    input wire uart_rx,
    output wire uart_tx,
    input wire target_rx,
    output wire target_tx,
    output wire gled1,
    output wire rled1,
    output wire rled2,
    output wire rled3,
    output wire rled4,
    output wire target_rst,
    output wire power_ctrl
);

    // UART loopback to target
    assign uart_tx = target_rx;

    wire sys_clk;
    wire locked;
    wire target_reset;
    wire start_offset_counter;
    wire start_duration_counter;
    wire [31:0] glitch_duration;
    wire [31:0] glitch_offset;

    // 状态LED
    assign gled1 = locked;
    assign rled1 = system_ready;
    assign rled2 = target_reset;
    assign rled3 = init_done;
    assign rled4 = 1'b0;

    // PLL for 100 MHz system clock
    pll my_pll (
        .clock_in(clk),
        .clock_out(sys_clk),
        .locked(locked)
    );

    // 延迟系统初始化：500 us
    reg [15:0] delay_counter = 0;
    wire init_done = (delay_counter >= 16'd50000);  // @100MHz ≈ 500us
    wire system_ready = locked && init_done;

    always @(posedge sys_clk) begin
        if (!locked)
            delay_counter <= 0;
        else if (!init_done)
            delay_counter <= delay_counter + 1;
    end

    // command processor
    command_processor command_processor (
        .clk(sys_clk),
        .din(uart_rx),
        .rst(!system_ready),
        .dout(target_tx),
        .target_reset(target_reset),
        .duration(glitch_duration),
        .offset(glitch_offset),
        .start_offset_counter(start_offset_counter)
    );

    // improved resetter: ~100ms
    resetter resetter (
        .clk(sys_clk),
        .enable(target_reset),
        .reset_line(target_rst)
    );

    offset_counter offset_counter (
        .clk(sys_clk),
        .reset(target_reset),
        .enable(start_offset_counter),
        .din(glitch_offset),
        .done(start_duration_counter)
    );

    duration_counter duration_counter (
        .clk(sys_clk),
        .reset(target_reset),
        .enable(start_duration_counter),
        .din(glitch_duration),
        .power_select(power_ctrl)
    );

endmodule
