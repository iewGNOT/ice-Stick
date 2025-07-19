// ─────────────────────────────────────────────────────────────────────────
//  resetter.v  —  active‑low reset pulse (≈100 ms) -----------------------
// ─────────────────────────────────────────────────────────────────────────
module resetter (
    input  wire clk,
    input  wire enable,         // 同步高电平触发一次脉冲
    output reg  active_low = 1  // 输出，0 = 复位有效
);
    parameter PULSE_CYCLES = 24'd21_900_000; // 根据 sys_clk 调节

    reg [23:0] counter = 24'd0;
    reg busy = 1'b0;

    always @(posedge clk) begin
        if (enable) begin
            busy       <= 1'b1;
            counter    <= 24'd0;
            active_low <= 1'b0;       // 拉低开始复位
        end else if (busy) begin
            if (counter < PULSE_CYCLES) begin
                counter <= counter + 1'b1;
            end else begin
                busy       <= 1'b0;
                active_low <= 1'b1;   // 释放为高阻
            end
        end
    end
endmodule
