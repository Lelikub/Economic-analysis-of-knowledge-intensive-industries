from __future__ import annotations

import pytest

from euv_analysis.ttm import TTMCalculator, TTMInputError


def test_ttm_zero_delay_has_zero_penalty():
    """Catches a nonzero economic loss for an on-time launch."""
    assert TTMCalculator().calculate(0.0, 0.10, 0.15, 3.0, 1) == pytest.approx(0.0)


@pytest.mark.parametrize("delay", [3.0, 3.5])
def test_ttm_at_or_after_horizon_is_total_loss(delay):
    """Catches negative retained-value factors beyond the market horizon."""
    assert TTMCalculator().calculate(delay, 0.10, 0.15, 3.0, 1) == pytest.approx(1.0)


def test_ttm_closed_window_is_total_loss():
    """Catches revenue retained after the market window has closed."""
    assert TTMCalculator().calculate(0.5, 0.10, 0.15, 3.0, 0) == pytest.approx(1.0)


def test_ttm_matches_lecture_scenario():
    """Catches omission of discount, erosion, or horizon channels."""
    assert TTMCalculator().calculate(0.5, 0.10, 0.15, 3.0, 1) == pytest.approx(
        0.26285941114120437
    )


def test_csv_ttm_scenario_remains_separate():
    """Catches accidental replacement of CSV rates with assignment rates."""
    assert TTMCalculator().calculate(0.5, 0.12, 0.18, 3.0, 1) == pytest.approx(
        0.2803468358172122
    )


@pytest.mark.parametrize(
    ("args", "message"),
    [
        ((-0.1, 0.10, 0.15, 3.0, 1), "delay"),
        ((0.5, -1.0, 0.15, 3.0, 1), "discount"),
        ((0.5, 0.10, 0.15, 0.0, 1), "horizon"),
        ((0.5, 0.10, 0.15, 3.0, 2), "window"),
    ],
)
def test_ttm_rejects_invalid_inputs(args, message):
    """Catches silent calculation of economically meaningless TTM inputs."""
    with pytest.raises(TTMInputError, match=message):
        TTMCalculator().calculate(*args)
