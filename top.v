/1

`default_nettype none

module top (
    input  wire clk,
    input  wire uart_rx,
    output wire uart_tx,
    input  wire target_rx,
    output wire target_tx,
    output wire gled1,
    output wire target_rst,
    output wire power_ctrl
);

    // ── 内部连线 ───────────────────────────────────────────────
    wire sys_clk;                     // system clock (PLL)
    wire locked;                      // PLL lock
    wire target_reset;                // 来自 command_processor 的复位请求（高有效）
    wire start_offset_counter;        // 启动 offset 计数
    wire start_duration_counter;      // 启动 duration 计数
    wire [31:0] glitch_duration;      // 短毛刺 duration
    wire [31:0] glitch_offset;        // 短毛刺 offset

    wire short_active;                // duration_counter 的输出（短毛刺，高=断电）
    wire wide_glitch;                 // resetter 的输出（复位期间为 1，高=断电）

    // ── UART 直通到目标 ───────────────────────────────────────
    assign uart_tx = target_rx;

    // ── 指示灯 ────────────────────────────────────────────────
    assign gled1 = locked;

    // ── PLL ──────────────────────────────────────────────────
    pll my_pll (
        .clock_in  (clk),
        .clock_out (sys_clk),
        .locked    (locked)
    );

    // ── 命令处理 ──────────────────────────────────────────────
    command_processor command_processor (
        .clk                 (sys_clk),
        .din                 (uart_rx),
        .rst                 (!locked),
        .dout                (target_tx),
        .target_reset        (target_reset),
        .duration            (glitch_duration),
        .offset              (glitch_offset),
        .start_offset_counter(start_offset_counter)
    );

    // ── 宽毛刺/复位发生器（nRESET & 供电门控宽毛刺）──────────
    // 注意：resetter 需要有 wide_glitch 这个高有效输出
    resetter resetter (
        .clk        (sys_clk),
        .enable     (target_reset),  // 高电平开始一次宽脉冲
        .reset_line (target_rst),    // 低有效 nRESET → 接目标复位脚
        .wide_glitch(wide_glitch)    // 高有效“宽毛刺” → 用于 power_ctrl
    );

    // ── offset 计数 ───────────────────────────────────────────
    offset_counter offset_counter (
        .clk    (sys_clk),
        .reset  (target_reset),
        .enable (start_offset_counter),
        .din    (glitch_offset),
        .done   (start_duration_counter)
    );

    // ── duration 计数（短毛刺）────────────────────────────────
    duration_counter duration_counter (
        .clk         (sys_clk),
        .reset       (target_reset),
        .enable      (start_duration_counter),
        .din         (glitch_duration),
        .power_select(short_active)      // 高有效 = 断电
    );

    // ── 供电门控：宽毛刺 OR 短毛刺 ────────────────────────────
    // 若外部硬件为高电平=断电：直接 OR
    assign power_ctrl = wide_glitch | short_active;

    // 若你的外部电源开关是“低电平=断电”，改成：
    // assign power_ctrl = ~(wide_glitch | short_active);

endmodule
