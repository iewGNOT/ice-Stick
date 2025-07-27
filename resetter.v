module resetter #(
    parameter integer PULSE_CYCLES = 5_000_000  // 50 ms @ 100 MHz
)(
    input  wire clk,
    input  wire enable,
    output reg  reset_line,   // 低有效：0=复位中 (接芯片 nRESET)
    output reg  wide_glitch   // 高有效：1=复位中 (并到 power_ctrl)
);
    reg [31:0] cnt = 0;
    always @(posedge clk) begin
        if (enable) begin
            cnt <= PULSE_CYCLES;
        end else if (cnt != 0) begin
            cnt <= cnt - 1'b1;
        end
        reset_line <= (cnt != 0) ? 1'b0 : 1'b1;  // nRESET 低有效
        wide_glitch <= (cnt != 0) ? 1'b1 : 1'b0; // power_ctrl 高有效
    end
endmodule
