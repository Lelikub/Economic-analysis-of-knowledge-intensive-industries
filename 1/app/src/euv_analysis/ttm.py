"""Time-to-market economic penalty model from lecture slides 21–22."""

from __future__ import annotations

import math


class TTMInputError(ValueError):
    """Raised for economically meaningless TTM parameters."""


class TTMCalculator:
    """Calculate the multiplicative lost-value share caused by delay."""

    def calculate(
        self,
        delay_years: float,
        discount_rate: float,
        price_erosion_rate: float,
        market_horizon: float,
        market_window_open: int,
    ) -> float:
        """Return a loss share in the closed interval from zero to one."""
        if delay_years < 0:
            raise TTMInputError("delay must be non-negative")
        if discount_rate <= -1:
            raise TTMInputError("discount rate must be greater than -1")
        if market_horizon <= 0:
            raise TTMInputError("market horizon must be greater than zero")
        if market_window_open not in (0, 1):
            raise TTMInputError("market window must be 0 or 1")
        if market_window_open == 0 or delay_years >= market_horizon:
            return 1.0

        retained_value = (
            1.0 / ((1.0 + discount_rate) ** delay_years)
            * math.exp(-price_erosion_rate * delay_years)
            * ((market_horizon - delay_years) / market_horizon)
            * market_window_open
        )
        return min(1.0, max(0.0, 1.0 - retained_value))
