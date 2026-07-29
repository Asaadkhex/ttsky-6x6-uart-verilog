/*
 * Copyright (c) 2024 Your Name
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none
//`timescale 1ns/1ps


// =============================================================================
// 6-to-1 multiplexer using only two-input NAND gates.
//
// Select encoding:
//   3'b000 -> d0
//   3'b001 -> d1
//   3'b010 -> d2
//   3'b011 -> d3
//   3'b100 -> d4
//   3'b101 -> d5
//   3'b110 -> 1'b0
//   3'b111 -> 1'b0
//
// Gate count: 20 two-input NAND gates.
// =============================================================================
module mux6_nand (
    input  wire       d0,
    input  wire       d1,
    input  wire       d2,
    input  wire       d3,
    input  wire       d4,
    input  wire       d5,
    input  wire [2:0] sel,
    output wire       y
);
    // Shared select inversions.
    wire sel0_n;
    wire sel1_n;
    wire sel2_n;

    // First-stage internal signals.
    wire d0_term_n;
    wire d1_term_n;
    wire d2_term_n;
    wire d3_term_n;
    wire d4_term_n;
    wire d5_term_n;
    wire a0;
    wire a1;
    wire a2;

    // Second-stage internal signals.
    wire a0_term_n;
    wire a1_term_n;
    wire a2_gate_n;
    wire b0;
    wire b1;

    // Final-stage internal signals.
    wire b0_term_n;
    wire b1_term_n;

    // -------------------------------------------------------------------------
    // First stage: select one signal from each pair using sel[0].
    // -------------------------------------------------------------------------
    nand (sel0_n,   sel[0], sel[0]);

    nand (d0_term_n, d0, sel0_n);
    nand (d1_term_n, d1, sel[0]);
    nand (a0,        d0_term_n, d1_term_n);

    nand (d2_term_n, d2, sel0_n);
    nand (d3_term_n, d3, sel[0]);
    nand (a1,        d2_term_n, d3_term_n);

    nand (d4_term_n, d4, sel0_n);
    nand (d5_term_n, d5, sel[0]);
    nand (a2,        d4_term_n, d5_term_n);

    // -------------------------------------------------------------------------
    // Second stage:
    //   b0 selects between the d0/d1 and d2/d3 pairs using sel[1].
    //   b1 passes the d4/d5 pair only when sel[1] is zero.
    //       If sel[1] is one, b1 is forced to zero.
    // -------------------------------------------------------------------------
    nand (sel1_n,    sel[1], sel[1]);

    nand (a0_term_n, a0, sel1_n);
    nand (a1_term_n, a1, sel[1]);
    nand (b0,        a0_term_n, a1_term_n);

    // b1 = a2 AND NOT(sel[1]), implemented with two NAND gates.
    nand (a2_gate_n, a2, sel1_n);
    nand (b1,        a2_gate_n, a2_gate_n);

    // -------------------------------------------------------------------------
    // Final stage: select the lower group or upper group using sel[2].
    // Codes 110 and 111 produce zero because b1 is zero when sel[1] = 1.
    // -------------------------------------------------------------------------
    nand (sel2_n,    sel[2], sel[2]);
    nand (b0_term_n, b0, sel2_n);
    nand (b1_term_n, b1, sel[2]);
    nand (y,         b0_term_n, b1_term_n);
endmodule


// =============================================================================
// 6x6 NAND-only crossbar switch.
//
// Each output independently selects exactly one of the six inputs. Multiple
// outputs may select the same input simultaneously.
//
// sel0 controls y[0]
// sel1 controls y[1]
// sel2 controls y[2]
// sel3 controls y[3]
// sel4 controls y[4]
// sel5 controls y[5]
//
// Total gate count: 6 channels x 20 NAND gates = 120 two-input NAND gates.
// =============================================================================
module switch6x6_nand (
    input  wire [5:0] x,
    input  wire [2:0] sel0,
    input  wire [2:0] sel1,
    input  wire [2:0] sel2,
    input  wire [2:0] sel3,
    input  wire [2:0] sel4,
    input  wire [2:0] sel5,
    output wire [5:0] y
);
    mux6_nand u_output0 (
        .d0  (x[0]),
        .d1  (x[1]),
        .d2  (x[2]),
        .d3  (x[3]),
        .d4  (x[4]),
        .d5  (x[5]),
        .sel (sel0),
        .y   (y[0])
    );

    mux6_nand u_output1 (
        .d0  (x[0]),
        .d1  (x[1]),
        .d2  (x[2]),
        .d3  (x[3]),
        .d4  (x[4]),
        .d5  (x[5]),
        .sel (sel1),
        .y   (y[1])
    );

    mux6_nand u_output2 (
        .d0  (x[0]),
        .d1  (x[1]),
        .d2  (x[2]),
        .d3  (x[3]),
        .d4  (x[4]),
        .d5  (x[5]),
        .sel (sel2),
        .y   (y[2])
    );

    mux6_nand u_output3 (
        .d0  (x[0]),
        .d1  (x[1]),
        .d2  (x[2]),
        .d3  (x[3]),
        .d4  (x[4]),
        .d5  (x[5]),
        .sel (sel3),
        .y   (y[3])
    );

    mux6_nand u_output4 (
        .d0  (x[0]),
        .d1  (x[1]),
        .d2  (x[2]),
        .d3  (x[3]),
        .d4  (x[4]),
        .d5  (x[5]),
        .sel (sel4),
        .y   (y[4])
    );

    mux6_nand u_output5 (
        .d0  (x[0]),
        .d1  (x[1]),
        .d2  (x[2]),
        .d3  (x[3]),
        .d4  (x[4]),
        .d5  (x[5]),
        .sel (sel5),
        .y   (y[5])
    );
endmodule

// =============================================================================
// 18-bit serial-in shift register with six 3-bit latched outputs
//
// Bit ordering:
//   The newest serial bit shifted in appears at shift_reg[0].
//   After 18 clocks, latch=1 captures:
//     var0 = shift_reg[2:0]
//     var1 = shift_reg[5:3]
//     var2 = shift_reg[8:6]
//     var3 = shift_reg[11:9]
//     var4 = shift_reg[14:12]
//     var5 = shift_reg[17:15]
//
// latch is sampled on the rising edge of clk.
// Outputs remain unchanged while latch=0.
// =============================================================================
module shift_register_18bit (
    input  wire       clk,
    input  wire       rst_n,
    input  wire       data_in,
    input  wire       latch,

    output reg  [2:0] var0,
    output reg  [2:0] var1,
    output reg  [2:0] var2,
    output reg  [2:0] var3,
    output reg  [2:0] var4,
    output reg  [2:0] var5
);

    reg [17:0] shift_reg;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg <= 18'b0;

            var0 <= 3'b000;
            var1 <= 3'b000;
            var2 <= 3'b000;
            var3 <= 3'b000;
            var4 <= 3'b000;
            var5 <= 3'b000;
        end
        else begin
            // Shift toward MSB; newest bit enters bit 0.
            shift_reg <= {shift_reg[16:0], data_in};

            // Transfer the current 18-bit shift-register contents
            // into six independent 3-bit variables.
            if (latch) begin
                var0 <= shift_reg[2:0];
                var1 <= shift_reg[5:3];
                var2 <= shift_reg[8:6];
                var3 <= shift_reg[11:9];
                var4 <= shift_reg[14:12];
                var5 <= shift_reg[17:15];
            end
        end
    end


endmodule


// =============================================================================
// Tiny Tapeout Top Module.
//
// 
// =============================================================================
module tt_um_Asaadkhex_6x6u (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output wire [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output wire [7:0] uio_out,  // IOs: Output path
    output wire [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

	wire  [2:0] out1_sel;
	wire  [2:0] out2_sel;
	wire  [2:0] out3_sel;
	wire  [2:0] out4_sel;
	wire  [2:0] out5_sel;
	wire  [2:0] out6_sel;
	
	// Read the shift register input and parse control commands
	shift_register_18bit shift_register (
		.clk	(clk),
		.rst_n	(rst_n),
		.data_in(ui_in[6]),
		.latch	(ui_in[7]),
		.var0	(out1_sel),
		.var1	(out2_sel),
		.var2	(out3_sel),
		.var3	(out4_sel),
		.var4	(out5_sel),
		.var5	(out6_sel)	
	);

	// Assign control commands for all switches
	switch6x6_nand switch6x6 (
		.x  (ui_in[5:0]),
		.sel0  (out1_sel),
		.sel1  (out2_sel),
		.sel2  (out3_sel),
		.sel3  (out4_sel),
		.sel4  (out5_sel),
		.sel5  (out6_sel),
		.y  (uo_out[5:0])
	);  

	// All output pins must be assigned. If not used, assign to 0.
	assign uio_out = 0;
	assign uio_oe  = 0;
	assign uo_out [6]  = 0;
	assign uo_out [7]  = 0;

	// List all unused inputs to prevent warnings
	wire _unused = &{ena, uio_in, 1'b0};

endmodule
