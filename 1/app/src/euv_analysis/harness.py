"""Numeric comparison between cached Excel and Python reference values."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class HarnessEntry:
    """One auditable spreadsheet-versus-Python comparison."""

    metric: str
    excel_value: float | None
    python_value: float | None
    absolute_delta: float | None
    relative_delta: float | None
    tolerance: float
    status: str
    probable_cause: str
    timestamp: str


class MetricsHarness:
    """Compare independent results using a centralized absolute tolerance."""

    def __init__(self, tolerance: float = 1e-9) -> None:
        if tolerance < 0:
            raise ValueError("tolerance must be non-negative")
        self.tolerance = tolerance

    def compare(
        self,
        excel_values: dict[str, float | None],
        python_values: dict[str, float | None],
    ) -> list[HarnessEntry]:
        """Compare all names present in either result mapping."""
        timestamp = datetime.now(timezone.utc).isoformat()
        entries: list[HarnessEntry] = []
        for metric in sorted(set(excel_values) | set(python_values)):
            excel_value = excel_values.get(metric)
            python_value = python_values.get(metric)
            if excel_value is None or python_value is None:
                missing_side = "Excel" if excel_value is None else "Python"
                entries.append(
                    HarnessEntry(
                        metric,
                        excel_value,
                        python_value,
                        None,
                        None,
                        self.tolerance,
                        "NOT_COMPUTABLE",
                        f"{missing_side} value is unavailable",
                        timestamp,
                    )
                )
                continue

            absolute_delta = abs(excel_value - python_value)
            relative_delta = (
                absolute_delta / abs(excel_value) if excel_value != 0 else None
            )
            passed = absolute_delta <= self.tolerance
            entries.append(
                HarnessEntry(
                    metric,
                    excel_value,
                    python_value,
                    absolute_delta,
                    relative_delta,
                    self.tolerance,
                    "PASS" if passed else "FAIL",
                    "" if passed else "Formula, input, or cached Excel value differs",
                    timestamp,
                )
            )
        return entries

