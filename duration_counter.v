`timescale 1ns / 1ps

module duration_counter(
    input  wire        clk,
    input  wire        reset,
    input  wire        enable,
    input  wire [31:0] din,
    output reg         power_select,
    output reg         pulse_done
);

    reg [31:0] counter;

    parameter [2:0] STATE_IDLE = 2'd0;
    parameter [2:0] STATE_RUNNING = 2'd1;
    parameter [2:0] STATE_DONE = 2'd2;

    reg [2:0] state = STATE_IDLE;

    always @(posedge clk) begin
        state         <= state;
        counter       <= counter;
        power_select  <= 1'b0;
        pulse_done    <= 1'b0;

        if (reset)
            state <= STATE_IDLE;

        case (state)
            STATE_IDLE: begin
                if (enable) begin
                    counter <= din;
                    state <= STATE_RUNNING;
                end
            end
            STATE_RUNNING: begin
                power_select <= 1'b1;
                counter <= counter - 1'b1;
                if (counter == 1) begin
                    state <= STATE_DONE;
                    pulse_done <= 1'b1;
                end
            end
            STATE_DONE: begin
                state <= STATE_IDLE;
            end
        endcase
    end

endmodule
