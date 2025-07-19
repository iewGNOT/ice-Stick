// ========================================================================
//  top.v  —  iCEstick voltage-glitcher  •  clean UART relay version
// ========================================================================
default_nettype none

module top (
    // ─────外部时钟──────────────────────────────────────────────────────────
    input  wire clk,          // 12 MHz on iCEstick
    // ─────FTDI UART───────────────────────────────────────────────────────
    input  wire uart_rx,      // FTDI-TX → FPGA
    output wire uart_tx,      // FPGA   → FTDI-RX
    // ─────目标设备 UART───────────────────────────────────────────────────
    input  wire target_rx,    // 目标设备 TX → FPGA
    output wire target_tx,    // FPGA         → 目标设备 RX
    // ─────控制/指示───────────────────────────────────────────────────────
    output wire target_rst,   // 复位脚（经 resetter 延长）
    output wire power_ctrl,   // glitch FET/VCC 选通
    output wire gled1, rled1, rled2, rled3, rled4
);

    // ─────────────────────────────────────────────────────────────────────
    // 1.  时钟/复位
    // ─────────────────────────────────────────────────────────────────────
    wire sys_clk;
    wire pll_locked;
    pll pll_i (
        .clock_in (clk),
        .clock_out(sys_clk),
        .locked   (pll_locked)
    );

    // 上电后再等 500 µs，确保 VCC 稳定
    reg  [15:0] pwrup_cnt = 0;
    wire init_done   = (pwrup_cnt == 16'd50000);   // 100 MHz × 500 µs
    wire sys_ready   = pll_locked & init_done;

    always @(posedge sys_clk)
        if (!pll_locked)
            pwrup_cnt <= 0;
        else if (!init_done)
            pwrup_cnt <= pwrup_cnt + 1;

    // ─────────────────────────────────────────────────────────────────────
    // 2.  Glitch 控制命令处理
    // ─────────────────────────────────────────────────────────────────────
    wire        start_ofs_cnt;
    wire        start_dur_cnt;
    wire [31:0] glitch_ofs;
    wire [31:0] glitch_dur;
    wire        tgt_reset_req;

    command_processor CMD (
        .clk                 (sys_clk),
        .rst                 (!sys_ready),
        .din                 (uart_rx),     // FTDI 指令
        .dout                (target_tx),   // 转发给目标 MCU
        .target_reset        (tgt_reset_req),
        .duration            (glitch_dur),
        .offset              (glitch_ofs),
        .start_offset_counter(start_ofs_cnt)
    );

    // ─────────────────────────────────────────────────────────────────────
    // 3.  复位 & 计数器链
    // ─────────────────────────────────────────────────────────────────────
    resetter RST (
        .clk       (sys_clk),
        .enable    (tgt_reset_req),
        .reset_line(target_rst)    // ≈100 ms 低脉冲
    );

    offset_counter OFS (
        .clk   (sys_clk),
        .reset (tgt_reset_req),
        .enable(start_ofs_cnt),
        .din   (glitch_ofs),
        .done  (start_dur_cnt)
    );

    duration_counter DUR (
        .clk         (sys_clk),
        .reset       (tgt_reset_req),
        .enable      (start_dur_cnt),
        .din         (glitch_dur),
        .power_select(power_ctrl)   // 给外部 MOSFET/VCC
    );

    // ─────────────────────────────────────────────────────────────────────
    // 4.  UART 回送：目标 → PC
    //     目标设备发出的数据仅经过 FPGA **单向复制**到 FTDI-RX。
    //     这里 FPGA 只做输入(target_rx)→输出(uart_tx)的缓冲，
    //     不会驱动 target_rx，引脚始终保持高阻。
    // ─────────────────────────────────────────────────────────────────────
    assign uart_tx = target_rx;

    // ─────────────────────────────────────────────────────────────────────
    // 5.  状态 LED
    // ─────────────────────────────────────────────────────────────────────
    assign gled1 = pll_locked;     // 绿灯：PLL 锁定
    assign rled1 = sys_ready;      // 红1 ：系统就绪
    assign rled2 = tgt_reset_req;  // 红2 ：正在复位目标
    assign rled3 = init_done;      // 红3 ：500 µs 延时完成
    assign rled4 = 1'b0;           // 红4 ：保留

endmodule
