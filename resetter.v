`default_nettype none
module resetter (
    input  wire clk,
    input  wire enable,            // 1 → 触发一次复位
    output reg  active_low = 1'b1  // 输出：低脉冲
);
    parameter PULSE_CYCLES = 24'd21_900_000; // ≈100 ms @100 MHz
    reg [23:0] cnt = 0;

    always @(posedge clk) begin
        if (enable) begin
            active_low <= 1'b0;
            cnt        <= 0;
        end else if (!active_low) begin
            if (cnt < PULSE_CYCLES)
                cnt <= cnt + 1'b1;
            else
                active_low <= 1'b1;   // 释放，高阻由顶层生成
        end
    end
endmodule
