`timescale 1ns / 1ps

module command_processor(
    input  wire clk,
    input  wire rst,
    input  wire din,
    output wire dout,
    output reg  target_reset,
    output reg  [7:0] data_out,
    output reg  [31:0] duration = 32'd0,
    output reg  [31:0] offset   = 32'd0,
    output reg  start_offset_counter,
    input  wire tx_release
);

    wire [7:0] uart_rx_data;
    wire [7:0] uart_tx_data;
    wire uart_valid;
    wire uart_tx_ready;
    wire fifo_empty;
    reg  fifo_write_enable;
    reg  [7:0] fifo_data_in;
    reg  glitch_trigger = 1'b0;

    uart_rx rxi(
        .clk(clk),
        .rst(rst),
        .din(din),
        .data_out(uart_rx_data),
        .valid(uart_valid)
    );

    uart_tx txi (
        .clk(clk),
        .rst(rst),
        .dout(dout),
        .data_in(uart_tx_data),
        .en(!fifo_empty & tx_release),
        .rdy(uart_tx_ready)
    );

    fifo fifo_uart (
        .clk(clk),
        .rst(rst),
        .data_in(fifo_data_in),
        .wen(fifo_write_enable),
        .ren(uart_tx_ready & tx_release),
        .empty(fifo_empty),
        .data_out(uart_tx_data)
    );

    parameter [7:0] PASSTHROUGH  = 8'h00;
    parameter [7:0] RESET        = 8'h01;
    parameter [7:0] SET_DURATION = 8'h02;
    parameter [7:0] SET_OFFSET   = 8'h03;
    parameter [7:0] START_GLITCH = 8'h04;

    reg [7:0] num_bytes = 8'd0;

    parameter [4:0] STATE_IDLE         = 4'd0;
    parameter [4:0] STATE_PASSTHROUGH  = 4'd1;
    parameter [4:0] STATE_PIPE         = 4'd2;
    parameter [4:0] STATE_SET_DURATION = 4'd4;
    parameter [4:0] STATE_SET_OFFSET   = 4'd5;
    parameter [4:0] STATE_START_GLITCH = 4'd6;
    parameter [4:0] STATE_STOP_GLITCH  = 4'd7;

    reg [4:0] state = STATE_IDLE;

    always @(posedge clk)
    begin
        state <= state;
        num_bytes <= num_bytes;
        fifo_data_in <= fifo_data_in;
        fifo_write_enable <= 1'b0;
        target_reset <= 1'b0;
        start_offset_counter <= 1'b0;
        duration <= duration;
        offset <= offset;
        glitch_trigger <= glitch_trigger;

        case (state)
            STATE_IDLE:
            begin
                if (uart_valid)
                begin
                    case (uart_rx_data)
                        PASSTHROUGH:
                        begin
                            state <= STATE_PASSTHROUGH;
                        end
                        RESET:
                        begin
                            target_reset <= 1'b1;
                        end
                        SET_DURATION:
                        begin
                            num_bytes <= 8'd4;
                            state <= STATE_SET_DURATION;
                        end
                        SET_OFFSET:
                        begin
                            num_bytes <= 8'd4;
                            state <= STATE_SET_OFFSET;
                        end
                        START_GLITCH:
                        begin
                            state <= STATE_START_GLITCH;
                            glitch_trigger <= 1'b1;
                        end
                    endcase
                end
            end

            STATE_PASSTHROUGH:
            begin
                if (uart_valid)
                begin
                    num_bytes <= uart_rx_data;
                    state <= STATE_PIPE;
                    if (glitch_trigger)
                    begin
                        start_offset_counter <= 1'b1;
                        glitch_trigger <= 1'b0;
                    end
                end
            end

            STATE_PIPE:
            begin
                if (uart_valid)
                begin
                    num_bytes <= num_bytes - 1'b1;
                    fifo_data_in <= uart_rx_data;
                    fifo_write_enable <= 1'b1;
                    if (num_bytes == 1)
                    begin
                        state <= STATE_IDLE;
                    end
                end
            end

            STATE_SET_DURATION:
            begin
                if (uart_valid)
                begin
                    num_bytes <= num_bytes - 1'b1;
                    duration <= {uart_rx_data, duration[31:8]};
                    if (num_bytes == 8'd1)
                    begin
                        state <= STATE_IDLE;
                    end
                end
            end

            STATE_SET_OFFSET:
            begin
                if (uart_valid)
                begin
                    num_bytes <= num_bytes - 1'b1;
                    offset <= {uart_rx_data, offset[31:8]};
                    if (num_bytes == 1)
                    begin
                        state <= STATE_IDLE;
                    end
                end
            end

            STATE_START_GLITCH:
            begin
                glitch_trigger <= 1'b1;
                state <= STATE_IDLE;
            end
        endcase
    end
endmodule

