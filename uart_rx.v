`include "src/uart_defs.v"
`default_nettype none

module uart_rx #(
    parameter integer DATA_BITS   = 8,
    parameter integer STOP_BITS   = 1,   // 1 or 2
    parameter         PARITY_EN   = 1'b1,// 0=No parity, 1=Enable parity
    parameter         PARITY_EVEN = 1'b1 // When PARITY_EN=1: 1=Even, 0=Odd
)(
    input  wire             clk,
    input  wire             rst,
    input  wire             din,
    output reg  [7:0]       data_out,
    output reg              valid
);

localparam [2:0] UART_START  = 3'd0;
localparam [2:0] UART_DATA   = 3'd1;
localparam [2:0] UART_PAR    = 3'd2;  // optional parity
localparam [2:0] UART_STOP   = 3'd3;
localparam [2:0] UART_IDLE   = 3'd4;

reg [2:0] state   = UART_START;
reg [3:0] bit_cnt = 4'd0;
reg [1:0] stop_cnt= 2'd0;
reg [9:0] etu_cnt = 10'd0;

reg       parity_ok;
reg       stop_ok;

wire etu_full = (etu_cnt == `UART_FULL_ETU);
wire etu_half = (etu_cnt == `UART_HALF_ETU);

// 说明：这里按 LSB-first 采样到 data_out（与 TX 保持一致）
// 每到一个整 ETU，就把当前 din 作为下一个 bit（LSB）移入。
always @(posedge clk) begin
    if (rst) begin
        state    <= UART_START;
        data_out <= 8'd0;
        valid    <= 1'b0;
        bit_cnt  <= 4'd0;
        stop_cnt <= 2'd0;
        etu_cnt  <= 10'd0;
        parity_ok<= 1'b1;
        stop_ok  <= 1'b1;
    end else begin
        // 默认
        valid   <= 1'b0;
        etu_cnt <= etu_cnt + 10'd1;

        case (state)
        // 等待起始位（低）
        UART_START: begin
            if (din == 1'b0) begin
                if (etu_half) begin
                    state    <= UART_DATA;
                    etu_cnt  <= 10'd0;
                    bit_cnt  <= 4'd0;
                    data_out <= {DATA_BITS{1'b0}};
                end
            end else begin
                etu_cnt <= 10'd0;
            end
        end

        // 接收 DATA_BITS 个数据位（LSB first）
        UART_DATA: begin
            if (etu_full) begin
                etu_cnt  <= 10'd0;
                // shift-right，把新采样的 din 放到 MSB？——
                // 为了与 TX 的 LSB-first 对齐，这里把 din 放到 data_out[bit_cnt] 更直观。
                // 但为尽量少改动原结构，我们保持移位式写法（LSB first）：
                data_out <= {din, data_out[7:1]}; // 兼容原实现；奇偶校验用归约 XOR，不受顺序影响
                bit_cnt  <= bit_cnt + 4'd1;

                if (bit_cnt == (DATA_BITS-1)) begin
                    if (PARITY_EN)
                        state <= UART_PAR;
                    else begin
                        state    <= UART_STOP;
                        stop_cnt <= 2'd0;
                        stop_ok  <= 1'b1;
                    end
                end
            end
        end

        // 可选奇偶校验位
        UART_PAR: begin
            if (etu_full) begin
                etu_cnt  <= 10'd0;
                // 对 data_out 做归约 XOR：^data_out 为 1 表示数据位里 1 的个数为奇数
                // Even parity:  期望 parity_bit == ^data_out
                // Odd parity :  期望 parity_bit == ~^data_out
                if (PARITY_EVEN)
                    parity_ok <= (din == ^data_out);
                else
                    parity_ok <= (din == ~^data_out);

                state    <= UART_STOP;
                stop_cnt <= 2'd0;
                stop_ok  <= 1'b1;
            end
        end

        // 一个或两个停止位（高）
        UART_STOP: begin
            if (etu_full) begin
                etu_cnt  <= 10'd0;
                stop_ok  <= stop_ok & din; // 停止位必须为高
                stop_cnt <= stop_cnt + 2'd1;

                if (stop_cnt == (STOP_BITS-1)) begin
                    // 全部停止位采样完毕
                    if ((!PARITY_EN || parity_ok) && stop_ok)
                        valid <= 1'b1; // 一帧成功
                    state <= UART_START;
                end
            end
        end

        default: begin
            state <= UART_START;
        end
        endcase
    end
end

endmodule
