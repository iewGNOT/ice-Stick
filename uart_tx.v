default_nettype none

module uart_tx (
    input wire       clk,
    input wire       rst,
    output reg       dout = 1'b1,
    input wire [7:0] data_in,
    input wire       en,
    output reg       rdy = 1'b1
);

parameter [1:0] UART_IDLE   = 2'd0;
parameter [1:0] UART_START  = 2'd1;
parameter [1:0] UART_DATA   = 2'd2;
parameter [1:0] UART_STOP   = 2'd3;

reg [1:0] state = UART_IDLE;
reg [2:0] bit_cnt = 3'd0;
reg [9:0] etu_cnt = 10'd0;
reg [7:0] data = 8'd0;

wire etu_full;
assign etu_full = (etu_cnt == UART_FULL_ETU);

always @ (posedge clk) begin
    if (rst) begin
        state <= UART_IDLE;
        dout <= 1'b1;
        rdy <= 1'b1;
        etu_cnt <= 10'd0;
        bit_cnt <= 3'd0;
        data <= 8'd0;
    end else begin
        case (state)
            UART_IDLE: begin
                dout <= 1'b1;
                etu_cnt <= 10'd0;
                bit_cnt <= 3'd0;
                if (en) begin
                    data <= data_in;
                    state <= UART_START;
                    rdy <= 1'b0;
                end else begin
                    rdy <= 1'b1;
                end
            end

            UART_START: begin
                dout <= 1'b0; // Start bit
                if (etu_full) begin
                    etu_cnt <= 10'd0;
                    state <= UART_DATA;
                end else begin
                    etu_cnt <= etu_cnt + 1;
                end
            end

            UART_DATA: begin
                dout <= data[0];
                if (etu_full) begin
                    data <= {1'b0, data[7:1]};
                    etu_cnt <= 10'd0;
                    bit_cnt <= bit_cnt + 1;
                    if (bit_cnt == 3'd7)
                        state <= UART_STOP;
                end else begin
                    etu_cnt <= etu_cnt + 1;
                end
            end

            UART_STOP: begin
                dout <= 1'b1; // Stop bit
                if (etu_full) begin
                    etu_cnt <= 10'd0;
                    state <= UART_IDLE;
                    rdy <= 1'b1;
                end else begin
                    etu_cnt <= etu_cnt + 1;
                end
            end
        endcase
    end
end

endmodule


