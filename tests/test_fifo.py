"""Invariant tests for the taint distributors (FIFO / haircut / poison)."""

import pytest

from src.tracer import fifo_distribute, distribute


def _vin(value):
    return {"prevout": {"value": value}}


def _vout(value):
    return {"value": value}


def test_codex_worked_example_single_input():
    # one input of 10 sats, first 3 tainted; two 5-sat outputs.
    # Strict positional FIFO: output 0 takes the 3 tainted + 2 clean = 3 tainted.
    # Output 1 takes 5 clean = 0 tainted.
    vins = [_vin(10)]
    vouts = [_vout(5), _vout(5)]
    assert fifo_distribute(vins, vouts, [3]) == [3, 0]


def test_strict_fifo_pushes_taint_to_first_output():
    # 8 tainted + 2 clean, two outputs [6, 4]. Output 0 gets 6 tainted.
    vins = [_vin(8), _vin(2)]
    vouts = [_vout(6), _vout(4)]
    assert fifo_distribute(vins, vouts, [8, 0]) == [6, 2]


def test_taint_conservation_for_arbitrary_split():
    vins = [_vin(50), _vin(50), _vin(50)]
    vouts = [_vout(40), _vout(60), _vout(50)]
    input_taints = [50, 0, 0]
    out = fifo_distribute(vins, vouts, input_taints)
    assert sum(out) == sum(input_taints)


def test_taint_conservation_for_multi_tainted():
    vins = [_vin(50), _vin(50), _vin(50)]
    vouts = [_vout(40), _vout(60), _vout(50)]
    input_taints = [50, 50, 0]
    out = fifo_distribute(vins, vouts, input_taints)
    assert sum(out) == sum(input_taints)


def test_pizza_consolidation_at_depth_3():
    # The real consolidation: 20 inputs, 1 output of 11022, with tainted inputs at
    # positions 10 (4223 fully tainted) and 15 (5777 fully tainted).
    vals = [150, 51, 1, 50, 50, 18.98, 50, 28, 0.01, 50,
            4223, 250, 0.01, 100, 1,
            5777, 50, 50, 100, 22]
    # convert to sats
    SAT = 100_000_000
    vins = [_vin(int(v * SAT)) for v in vals]
    vouts = [_vout(int(11022 * SAT))]
    input_taints = [0] * 20
    input_taints[10] = int(4223 * SAT)
    input_taints[15] = int(5777 * SAT)
    out = fifo_distribute(vins, vouts, input_taints)
    assert out[0] == int(10000 * SAT)


def test_pizza_consolidation_spend_strict_fifo():
    # The split after consolidation: input 11022 BTC (10000 tainted), outputs [5500, 5522].
    # Strict positional FIFO: output 0 gets all 5500 from the first 5500 tainted sats;
    # output 1 gets the remaining 4500 tainted + 1022 clean.
    SAT = 100_000_000
    vins = [_vin(11022 * SAT)]
    vouts = [_vout(5500 * SAT), _vout(5522 * SAT)]
    out = fifo_distribute(vins, vouts, [10000 * SAT])
    assert out == [5500 * SAT, 4500 * SAT]


def test_clean_input_first_then_tainted():
    # If the tainted input is positioned after a clean input that fills the first
    # output, that first output gets 0 tainted, the second gets the taint.
    vins = [_vin(5), _vin(10)]
    vouts = [_vout(5), _vout(10)]
    out = fifo_distribute(vins, vouts, [0, 5])
    assert out == [0, 5]


def test_zero_taint_no_op():
    vins = [_vin(100)]
    vouts = [_vout(50), _vout(50)]
    out = fifo_distribute(vins, vouts, [0])
    assert out == [0, 0]


# -------- fee absorption (Codex review block 1A) ----------------------------

def test_fee_absorption_conserves_taint_fifo():
    # 10 tainted, two outputs totalling 7, fee = 3. Under strict FIFO the
    # first 7 tainted go to outputs, the remaining 3 tainted go to the fee.
    vins = [_vin(10)]
    vouts = [_vout(4), _vout(3)]
    out, fee = distribute(vins, vouts, [10], convention="fifo")
    assert out == [4, 3]
    assert fee == 3
    assert sum(out) + fee == 10


def test_fee_absorption_conserves_taint_haircut():
    # Haircut: 10 tainted of 10, fee 3. Each output gets value*1.0 tainted;
    # fee gets the remainder (3).
    vins = [_vin(10)]
    vouts = [_vout(4), _vout(3)]
    out, fee = distribute(vins, vouts, [10], convention="haircut")
    assert sum(out) + fee == 10
    assert out == [4, 3]
    assert fee == 3


def test_fee_absorption_conserves_taint_poison():
    vins = [_vin(10)]
    vouts = [_vout(4), _vout(3)]
    out, fee = distribute(vins, vouts, [10], convention="poison")
    # Poison: every output is fully tainted, fee is fully tainted
    assert out == [4, 3]
    assert fee == 3
    assert sum(out) + fee == 10


def test_convention_divergence_with_clean_inputs():
    # Tainted input first, then clean input. Strict FIFO sends the taint to
    # the first output completely; haircut spreads it; poison taints everything
    # because at least one input is tainted.
    vins = [_vin(5), _vin(5)]
    vouts = [_vout(5), _vout(5)]
    fifo_out, fifo_fee = distribute(vins, vouts, [5, 0], convention="fifo")
    hair_out, hair_fee = distribute(vins, vouts, [5, 0], convention="haircut")
    pois_out, pois_fee = distribute(vins, vouts, [5, 0], convention="poison")

    assert fifo_out == [5, 0] and fifo_fee == 0
    # haircut: total_taint=5, total_in=10, each output gets value * 0.5 = 2 + 2,
    # remainder of 1 sat goes to fee
    assert sum(hair_out) + hair_fee == 5
    # poison: all 10 sats of outputs are tainted, fee = 0
    assert pois_out == [5, 5]
    # poison conservation is bounded by output_value + fee, not input_taint
    assert pois_fee == 0


def test_unknown_convention_raises():
    vins = [_vin(10)]
    vouts = [_vout(10)]
    with pytest.raises(ValueError):
        distribute(vins, vouts, [10], convention="lifo")
