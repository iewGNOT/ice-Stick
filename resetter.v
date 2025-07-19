module resetter (
    input wire clk,
    input wire enable,
    output reg reset_line
);

    reg [23:0] counter = 0;
    reg active = 0;

    always @(posedge clk) begin
        if (enable) begin
            counter <= 0;
            active <= 1;
        end else if (active && counter < 24'd21_900_000) begin
            counter <= counter + 1;
        end else begin
            active <= 0;
        end
    end

    always @(*) begin
        reset_line = active;
    end

endmodule
