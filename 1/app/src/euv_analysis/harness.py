"""Backward-compatible aliases for the renamed numeric reconciliation API."""

from .reconciliation import (
    MetricsReconciler as MetricsHarness,
    ReconciliationEntry as HarnessEntry,
)

__all__ = ["HarnessEntry", "MetricsHarness"]
