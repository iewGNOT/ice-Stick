`default_nettype none
module duration_counter (
    input  wire        clk,
    input  wire        reset,
    input  wire        enable,
    input  wire [31:0] din,
    output reg         active_low = 1'b1   // 0 → glitch 打开
);
    reg [31:0] counter = 0;
    typedef enum logic [1:0] {IDLE=2'd0, RUN=2'd1} state_t;
    state_t st = IDLE;

    always @(posedge clk) begin
        if (reset) begin
            st         <= IDLE;
            active_low <= 1'b1;
        end else case (st)
            IDLE: if (enable) begin
                counter     <= din;
                active_low  <= 1'b0;
                st          <= RUN;
            end
            RUN: if (counter == 0) begin
                active_low <= 1'b1;
                st         <= IDLE;
            end else
                counter <= counter - 1'b1;
        endcase
    end
endmodule
