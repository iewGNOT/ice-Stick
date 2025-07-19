// ─────────────────────────────────────────────────────────────────────────
//  duration_counter.v  —  active‑low glitch window -----------------------
// ─────────────────────────────────────────────────────────────────────────
module duration_counter (
    input  wire        clk,
    input  wire        reset,      // 同步高电平复位
    input  wire        enable,     // 1 → 开始计时
    input  wire [31:0] din,        // 时长 N 个 clk 周期
    output reg         active_low = 1 // 0 → glitch 开启
);
    reg [31:0] counter = 32'd0;
    
    // 状态机编码
    parameter S_IDLE = 1'b0;
    parameter S_RUN  = 1'b1;
    reg state = S_IDLE;

    always @(posedge clk) begin
        if (reset) begin
            state      <= S_IDLE;
            active_low <= 1'b1;
        end else begin
            case (state)
                S_IDLE: begin
                    if (enable) begin
                        counter    <= din;
                        active_low <= 1'b0; // 拉低打开 glitch
                        state      <= S_RUN;
                    end
                end
                S_RUN: begin
                    if (counter != 32'd0) begin
                        counter <= counter - 1'b1;
                    end else begin
                        active_low <= 1'b1; // 计时结束
                        state      <= S_IDLE;
                    end
                end
            endcase
        end
    end
endmodule
