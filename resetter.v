module resetter (
    input wire clk,
    input wire enable,
    output reg reset_line
);

    reg [23:0] counter = 0;
    reg active = 0;

    always @(posedge clk) begin
        if (enable) begin
            counter     <= 0;
            active      <= 1;
            reset_line  <= 1'b0;  // 输出低电平开始复位
        end else if (active && counter < 24'd21_900_000) begin
            counter     <= counter + 1;
            reset_line  <= 1'b0;  // 保持复位期间为低
        end else begin
            active      <= 0;
            reset_line  <= 1'b1;  // 复位完成，释放为高电平
        end
    end

endmodule
