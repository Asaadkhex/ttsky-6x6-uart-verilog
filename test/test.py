# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

"""
Comprehensive cocotb test for tt_um_Asaadkhex_6x6u.

Tests:
  1. Reset / initialization
  2. Selector-field ordering with mapping:
         OUT0<-IN0, OUT1<-IN1, ..., OUT5<-IN5
  3. Full 6x6 routing matrix:
         every input selection is checked on every output
  4. Isolation:
         unselected inputs must not affect outputs

TinyTapeout pin mapping assumed:
    ui_in[0:5] = six switch inputs IN0..IN5
    ui_in[6]   = serial configuration data_in
    ui_in[7]   = configuration latch
    uo_out[0:5] = six switch outputs OUT0..OUT5

Configuration word:
    six 3-bit selector fields in an 18-bit word

        bits [2:0]   -> OUT0 selector
        bits [5:3]   -> OUT1 selector
        bits [8:6]   -> OUT2 selector
        bits [11:9]  -> OUT3 selector
        bits [14:12] -> OUT4 selector
        bits [17:15] -> OUT5 selector

Selector values:
    000 -> IN0
    001 -> IN1
    010 -> IN2
    011 -> IN3
    100 -> IN4
    101 -> IN5

The 18-bit configuration word is shifted MSB-first.

Clock:
    10 kHz = 100 us period
"""

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


NUM_INPUTS = 6
NUM_OUTPUTS = 6

SWITCH_INPUT_MASK = 0x3F

DATA_IN_BIT = 6
LATCH_BIT = 7

CLOCK_PERIOD_US = 100  # 10 kHz


class TT6x6TB:
    def __init__(self, dut):
        self.dut = dut
        self.ui_value = 0

    # ------------------------------------------------------------------
    # ui_in helpers
    # ------------------------------------------------------------------

    def write_ui(self) -> None:
        self.dut.ui_in.value = self.ui_value

    def set_ui_bit(self, bit_index: int, value: int) -> None:
        """Set one ui_in bit while preserving all other ui_in bits."""
        if value:
            self.ui_value |= 1 << bit_index
        else:
            self.ui_value &= ~(1 << bit_index)

        self.write_ui()

    def set_switch_inputs(self, value: int) -> None:
        """
        Set ui_in[5:0] while preserving serial-data and latch bits.
        """
        self.ui_value = (
            (self.ui_value & ~SWITCH_INPUT_MASK)
            | (value & SWITCH_INPUT_MASK)
        )
        self.write_ui()

    # ------------------------------------------------------------------
    # Configuration helpers
    # ------------------------------------------------------------------

    @staticmethod
    def pack_selectors(selectors) -> int:
        """
        Pack six 3-bit selectors into one 18-bit configuration word.

        selectors[0] -> bits [2:0]   -> OUT0
        selectors[1] -> bits [5:3]   -> OUT1
        ...
        selectors[5] -> bits [17:15] -> OUT5
        """
        if len(selectors) != NUM_OUTPUTS:
            raise ValueError("Exactly six selectors are required")

        word = 0

        for output_index, selector in enumerate(selectors):
            if not 0 <= selector < NUM_INPUTS:
                raise ValueError(
                    f"Invalid selector {selector} for OUT{output_index}"
                )

            word |= selector << (3 * output_index)

        return word

    async def shift_word(self, word: int) -> None:
        """
        Shift an 18-bit configuration word into ui_in[6], MSB first.
        """
        if not 0 <= word < (1 << 18):
            raise ValueError("Configuration word must be 18 bits")

        for bit_index in range(17, -1, -1):
            await FallingEdge(self.dut.clk)

            bit_value = (word >> bit_index) & 1
            self.set_ui_bit(DATA_IN_BIT, bit_value)

            # DUT samples serial data on rising clock edge.
            await RisingEdge(self.dut.clk)

        # Return serial-data input low.
        await FallingEdge(self.dut.clk)
        self.set_ui_bit(DATA_IN_BIT, 0)

    async def latch_outputs(self) -> None:
        """
        Pulse latch high for one rising clock edge.

        Latch is asserted only after all 18 serial bits have been shifted.
        """
        await FallingEdge(self.dut.clk)
        self.set_ui_bit(LATCH_BIT, 1)

        await RisingEdge(self.dut.clk)

        await FallingEdge(self.dut.clk)
        self.set_ui_bit(LATCH_BIT, 0)

        # Allow combinational switch outputs to settle after new config.
        await Timer(1, unit="us")

    async def configure(self, selectors) -> int:
        """
        Program all six output selectors and latch them.
        Returns the packed 18-bit configuration word.
        """
        word = self.pack_selectors(selectors)

        self.dut._log.info(
            "Config selectors OUT0..OUT5 = %s | word = 0x%05X",
            list(selectors),
            word,
        )

        await self.shift_word(word)
        await self.latch_outputs()

        return word

    # ------------------------------------------------------------------
    # Output checking helpers
    # ------------------------------------------------------------------

    def read_outputs(self) -> int:
        """Read uo_out[5:0], failing clearly if X/Z is present."""
        raw = self.dut.uo_out.value

        try:
            return int(raw) & SWITCH_INPUT_MASK
        except ValueError as exc:
            raise AssertionError(
                f"uo_out contains unresolved X/Z bits: {raw}"
            ) from exc

    async def drive_and_check(
        self,
        input_value: int,
        expected_output: int,
        description: str,
    ) -> None:
        """
        Drive six switch inputs and verify all six switch outputs.
        """
        self.set_switch_inputs(input_value)

        # The switch network is combinational; give it settling time.
        await Timer(1, unit="us")

        actual = self.read_outputs()
        expected = expected_output & SWITCH_INPUT_MASK

        assert actual == expected, (
            f"{description}: "
            f"input=0b{input_value:06b}, "
            f"expected OUT=0b{expected:06b}, "
            f"actual OUT=0b{actual:06b}"
        )

        self.dut._log.info(
            "PASS: %-32s IN=%06s OUT=%06s",
            description,
            format(input_value, "06b"),
            format(actual, "06b"),
        )


@cocotb.test()
async def test_full_6x6_switch_matrix(dut):
    """
    Verify all 36 input-to-output routing paths of the 6x6 switch.
    """

    tb = TT6x6TB(dut)

    # ================================================================
    # Initial conditions
    # ================================================================

    dut.clk.value = 0
    dut.rst_n.value = 0
    dut.ena.value = 1

    dut.ui_in.value = 0
    dut.uio_in.value = 0
    tb.ui_value = 0

    # 10 kHz clock:
    #     f = 10,000 Hz
    #     T = 1/f = 100 us
    clock = Clock(dut.clk, CLOCK_PERIOD_US, unit="us")
    cocotb.start_soon(clock.start(start_high=False))

    # ================================================================
    # Test 1: Reset
    # ================================================================

    # Hold reset for two complete 10 kHz clock periods.
    await Timer(2 * CLOCK_PERIOD_US, unit="us")
    dut.rst_n.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="us")

    tb.set_switch_inputs(0)

    dut._log.info("PASS: Reset released")

    # ================================================================
    # Test 2: Verify selector field ordering
    #
    # OUT0 <- IN0
    # OUT1 <- IN1
    # OUT2 <- IN2
    # OUT3 <- IN3
    # OUT4 <- IN4
    # OUT5 <- IN5
    #
    # Then drive each input one at a time. The corresponding output
    # must be the only output asserted.
    # ================================================================

    dut._log.info("========================================")
    dut._log.info("TEST: Selector field ordering")
    dut._log.info("========================================")

    await tb.configure([0, 0, 0, 0, 0, 0])

    for input_index in range(NUM_INPUTS):
        one_hot = 1 << input_index

        await tb.drive_and_check(
            input_value=one_hot,
            expected_output=one_hot,
            description=f"identity route IN{input_index}",
        )

    await tb.drive_and_check(
        input_value=0,
        expected_output=0,
        description="identity route all LOW",
    )

    # ================================================================
    # Test 3: Full 6x6 routing matrix
    #
    # For each selected input:
    #   - route that input to ALL six outputs
    #   - drive each of the six inputs separately
    #
    # If the currently selected input is HIGH:
    #       OUT[5:0] must be 111111
    #
    # If any unselected input is HIGH:
    #       OUT[5:0] must remain 000000
    #
    # This executes 6 configurations x 6 driven inputs = 36 cases.
    # Each case checks all six output bits.
    # ================================================================

    dut._log.info("========================================")
    dut._log.info("TEST: Full 6x6 routing matrix")
    dut._log.info("========================================")

    case_count = 0

    for selected_input in range(NUM_INPUTS):

        # Route selected_input to every output.
        selectors = [selected_input] * NUM_OUTPUTS
        await tb.configure(selectors)

        dut._log.info(
            "Testing IN%d -> OUT0..OUT5",
            selected_input,
        )

        for driven_input in range(NUM_INPUTS):
            case_count += 1

            input_value = 1 << driven_input

            if driven_input == selected_input:
                expected_output = SWITCH_INPUT_MASK
            else:
                expected_output = 0

            await tb.drive_and_check(
                input_value=input_value,
                expected_output=expected_output,
                description=(
                    f"case {case_count:02d}: "
                    f"SEL=IN{selected_input}, "
                    f"drive IN{driven_input}"
                ),
            )

        # Check LOW state after each selector configuration.
        await tb.drive_and_check(
            input_value=0,
            expected_output=0,
            description=f"SEL=IN{selected_input}, all inputs LOW",
        )

    assert case_count == 36

    # ================================================================
    # Test 4: Simultaneous arbitrary routing pattern
    #
    # Additional asymmetric configuration to exercise all selector
    # fields with a nontrivial permutation:
    #
    # OUT0 <- IN5
    # OUT1 <- IN4
    # OUT2 <- IN3
    # OUT3 <- IN2
    # OUT4 <- IN1
    # OUT5 <- IN0
    # ================================================================

    dut._log.info("========================================")
    dut._log.info("TEST: Reverse mapping")
    dut._log.info("========================================")

    reverse_selectors = [5, 4, 3, 2, 1, 0]
    await tb.configure(reverse_selectors)

    for input_index in range(NUM_INPUTS):
        input_value = 1 << input_index

        # Reverse mapping:
        # IN0 -> OUT5
        # IN1 -> OUT4
        # ...
        # IN5 -> OUT0
        expected_output = 1 << (5 - input_index)

        await tb.drive_and_check(
            input_value=input_value,
            expected_output=expected_output,
            description=f"reverse route IN{input_index}",
        )

    # ================================================================
    # Final result
    # ================================================================

    tb.set_switch_inputs(0)
    await Timer(1, unit="us")

    dut._log.info("========================================")
    dut._log.info("ALL 6x6 SWITCH TESTS PASSED")
    dut._log.info("36 routing matrix cases verified")
    dut._log.info("Clock frequency: 10 kHz")
    dut._log.info("========================================")
