module uart_tx #(
  parameter UART_FULL_ETU = 868 // e.g. for 100 MHz / 115200 baud ≈ 868 clocks/bit
) (
  input  wire       clk,
  input  wire       rst,
  output reg        dout,
  input  wire [7:0] data_in,
  input  wire       en,
  output reg        rdy
);

  // state, counters as before…

  always @(posedge clk) begin
    if (rst) begin
      state   <= UART_IDLE;
      dout    <= 1'b1;
      rdy     <= 1'b1;
      etu_cnt <= 0;
      bit_cnt <= 0;
      data    <= 0;
    end else begin
      case (state)
        UART_IDLE: begin
          dout    <= 1'b1;
          etu_cnt <= 0;
          bit_cnt <= 0;
          if (en && rdy) begin              // only start when rdy is high
            data  <= data_in;
            state <= UART_START;
            rdy   <= 1'b0;
          end
        end

        UART_START: begin
          dout <= 1'b0;
          if (etu_cnt == UART_FULL_ETU-1) begin
            etu_cnt <= 0;
            state   <= UART_DATA;
          end else
            etu_cnt <= etu_cnt + 1;
        end

        UART_DATA: begin
          dout <= data[0];
          if (etu_cnt == UART_FULL_ETU-1) begin
            data    <= {1'b0, data[7:1]};
            etu_cnt <= 0;
            bit_cnt <= bit_cnt + 1;
            if (bit_cnt == 7)
              state <= UART_STOP;
          end else
            etu_cnt <= etu_cnt + 1;
        end

        UART_STOP: begin
          dout <= 1'b1;
          if (etu_cnt == UART_FULL_ETU-1) begin
            etu_cnt <= 0;
            state   <= UART_IDLE;
            rdy     <= 1'b1;
          end else
            etu_cnt <= etu_cnt + 1;
        end

        default: begin                     // recover from any bad state
          state   <= UART_IDLE;
          dout    <= 1'b1;
          etu_cnt <= 0;
          bit_cnt <= 0;
          rdy     <= 1'b1;
        end
      endcase
    end
  end
endmodule
