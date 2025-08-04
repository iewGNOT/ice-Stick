`include "src/uart_defs.v"
`default_nettype none

module uart_tx #(
    parameter integer DATA_BITS   = 8,
    parameter integer STOP_BITS   = 1,   // 1 or 2
    parameter         PARITY_EN   = 1'b1,// 0=No parity, 1=Enable parity
    parameter         PARITY_EVEN = 1'b1 // When PARITY_EN=1: 1=Even, 0=Odd
)(
    input  wire             clk,
    input  wire             rst,
    output reg              dout = 1'b1, // 空闲为高
    input  wire [7:0]       data_in,
    input  wire             en,
    output reg              rdy = 1'b1
);

localparam [2:0] UART_START  = 3'd0;
localparam [2:0] UART_DATA   = 3'd1;
localparam [2:0] UART_PAR    = 3'd2;  // optional parity
localparam [2:0] UART_STOP   = 3'd3;
localparam [2:0] UART_IDLE   = 3'd4;

reg [7:0] data_lat = 8'd0;
reg [7:0] shreg    = 8'd0;
reg [3:0] bit_cnt  = 4'd0;
reg [1:0] stop_cnt = 2'd0;
reg [2:0] state    = UART_START;
reg [9:0] etu_cnt  = 10'd0;

wire etu_full = (etu_cnt == `UART_FULL_ETU);

// 预计算校验位：基于起始时刻锁存的原始数据
wire parity_bit_even = ^data_lat;     // even parity 位 = ^data
wire parity_bit_odd  = ~^data_lat;    // odd  parity 位 = ~^data
wire parity_bit      = PARITY_EVEN ? parity_bit_even : parity_bit_odd;

always @(posedge clk) begin
    if (rst) begin
        state    <= UART_START;
        dout     <= 1'b1;
        rdy      <= 1'b1;
        etu_cnt  <= 10'd0;
        bit_cnt  <= 4'd0;
        stop_cnt <= 2'd0;
        shreg    <= 8'd0;
        data_lat <= 8'd0;
    end else begin
        etu_cnt <= etu_cnt + 10'd1;

        case (state)
        // 等待使能
        UART_START: begin
            if (en) begin
                // 起始位为低
                dout     <= 1'b0;
                rdy      <= 1'b0;
                etu_cnt  <= 10'd0;
                bit_cnt  <= 4'd0;
                stop_cnt <= 2'd0;
                data_lat <= data_in;
                // LSB-first 发送：先把 data_in 放入移位寄存器
                shreg    <= data_in;
                state    <= UART_DATA;
            end
        end

        // 发送 DATA_BITS（LSB first）
        UART_DATA: begin
            if (etu_full) begin
                etu_cnt <= 10'd0;
                dout    <= shreg[0];              // 先发 LSB
                shreg   <= {1'b0, shreg[7:1]};    // 右移，引入 0
                bit_cnt <= bit_cnt + 4'd1;

                if (bit_cnt == (DATA_BITS-1)) begin
                    if (PARITY_EN)
                        state <= UART_PAR;
                    else begin
                        state    <= UART_STOP;
                        stop_cnt <= 2'd0;
                    end
                end
            end
        end

        // 发送奇偶校验位（可选）
        UART_PAR: begin
            if (etu_full) begin
                etu_cnt <= 10'd0;
                dout    <= parity_bit;
                state   <= UART_STOP;
                stop_cnt<= 2'd0;
            end
        end

        // 发送一个或两个停止位（高）
        UART_STOP: begin
            if (etu_full) begin
                etu_cnt  <= 10'd0;
                dout     <= 1'b1;          // 停止位为高
                stop_cnt <= stop_cnt + 2'd1;
                if (stop_cnt == (STOP_BITS-1)) begin
                    state <= UART_IDLE;
                end
            end
        end

        // 一个 bit 时长的 idle，再回到 START 把 rdy 拉高
        UART_IDLE: begin
            if (etu_full) begin
                etu_cnt <= 10'd0;
                rdy     <= 1'b1;
                state   <= UART_START;
            end
        end

        default: begin
            state <= UART_START;
        end
        endcase
    end
end

endmodule
