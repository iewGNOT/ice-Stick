// ─────────────────────────────────────────────────────────────────────────
//  duration_counter.v  —  active‑low glitch window -----------------------
// ─────────────────────────────────────────────────────────────────────────
module duration_counter (
    input  wire        clk,
    input  wire        reset,      // 高电平同步复位
    input  wire        enable,     // 1 → 开始计时
    input  wire [31:0] din,        // 时长 N 个 clk 周期
    output reg         active_low = 1 // 0 → glitch 打开
);
    reg [31:0] counter = 0;

    typedef enum logic [1:0] {IDLE=2'd0, RUN=2'd1} state_t;
    state_t state = IDLE;

    always @(posedge clk) begin
        if (reset) begin
            state       <= IDLE;
            active_low  <= 1'b1;
        end else case (state)
            IDLE: begin
                if (enable) begin
                    counter     <= din;
                    active_low  <= 1'b0; // 拉低开始 glitch
                    state       <= RUN;
                end
            end
            RUN: begin
                if (counter != 0) begin
                    counter <= counter - 1'b1;
                end else begin
                    active_low <= 1'b1; // 结束，释放
                    state      <= IDLE;
                end
            end
        endcase
    end
endmodule
