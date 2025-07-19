// ─────────────────────────────────────────────────────────────────────────
//  resetter.v  —  generates active‑low reset pulse (~100 ms default) ------
// ─────────────────────────────────────────────────────────────────────────
module resetter (
    input  wire clk,
    input  wire enable,          // 1 → 开始一次复位脉冲
    output reg  active_low = 1   // 0 → 脉冲有效，1 → 空闲
);
    parameter PULSE_CYCLES = 24'd21_900_000; // ≈100 ms @219 MHz / 调整适配时钟
    reg [23:0] counter = 0;

    always @(posedge clk) begin
        if (enable) begin
            counter     <= 0;
            active_low  <= 1'b0;  // 拉低
        end else if (!active_low) begin
            if (counter < PULSE_CYCLES) begin
                counter <= counter + 1'b1;
            end else begin
                active_low <= 1'b1; // 释放为高阻
            end
        end
    end
endmodule
