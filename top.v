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

    wire uart_rx_gated;

    command_processor command_processor (
        .clk                 (sys_clk),
        .din                 (uart_rx_gated),
        .rst                 (!locked),
        .dout                (target_tx),
        .target_reset        (target_reset),
        .duration            (glitch_duration),
        .offset              (glitch_offset),
        .start_offset_counter()
    );

    resetter resetter (
        .clk        (sys_clk),
        .enable     (target_reset),
        .reset_line (target_rst),
        .wide_glitch(wide_glitch)
    );

    reg wg_d;
    always @(posedge sys_clk) wg_d <= wide_glitch;
    wire wg_fall =  wg_d & ~wide_glitch;
    wire wg_rise = ~wg_d &  wide_glitch;

    reg armed;
    always @(posedge sys_clk) begin
        if (wg_rise) armed <= 1'b1;
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

    localparam integer HS_DELAY_CYCLES = 100000;
    reg        hs_hold;
    reg        hs_pending;
    reg [31:0] hs_cnt;

    always @(posedge sys_clk) begin
        if (wg_rise) begin
            hs_hold    <= 1'b1;
            hs_pending <= 1'b1;
            hs_cnt     <= HS_DELAY_CYCLES;
        end else if (hs_pending) begin
            if (wide_glitch || short_active) begin
                hs_cnt <= HS_DELAY_CYCLES;
            end else if (hs_cnt != 0) begin
                hs_cnt <= hs_cnt - 1'b1;
            end else begin
                hs_hold    <= 1'b0;
                hs_pending <= 1'b0;
            end
        end
    end

    assign uart_rx_gated = hs_hold ? 1'b1 : uart_rx;

endmodule
