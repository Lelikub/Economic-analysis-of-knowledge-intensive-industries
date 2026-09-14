"""OPEX structure visualization from lecture slide 25."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .models import MetricsResult


OPEX_SHARES: dict[str, float] = {
    "Сырьё и прекурсоры": 0.25,
    "Утилиты": 0.20,
    "Персонал": 0.30,
    "ТОиР": 0.15,
    "Комплаенс, качество и метрология": 0.10,
}


class OpexVisualizer:
    """Create a deterministic bar chart for the lecture OPEX structure."""

    def create(self, path: Path) -> Path:
        """Validate shares and save the chart as a PNG."""
        total = sum(OPEX_SHARES.values())
        if abs(total - 1.0) > 1e-12:
            raise ValueError(f"OPEX shares must sum to 1.0, got {total}")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        categories = list(OPEX_SHARES)
        percentages = [share * 100 for share in OPEX_SHARES.values()]
        figure, axis = plt.subplots(figsize=(11, 6), dpi=160)
        bars = axis.bar(
            categories,
            percentages,
            color=["#31688E", "#35B779", "#FDE725", "#440154", "#21918C"],
        )
        axis.set_title(
            "Структура OPEX в высокотехнологичном производстве", pad=16
        )
        axis.set_xlabel("Категории расходов")
        axis.set_ylabel("Доля OPEX, %")
        axis.set_ylim(0, 35)
        axis.grid(axis="y", alpha=0.25)
        axis.tick_params(axis="x", rotation=18)
        axis.bar_label(bars, labels=[f"{value:.0f}%" for value in percentages], padding=4)
        figure.tight_layout()
        figure.savefig(path, bbox_inches="tight")
        plt.close(figure)
        return path


class EfficiencyComparisonVisualizer:
    """Compare calculated production-efficiency metrics across scenarios."""

    def create(
        self,
        path: Path,
        baseline: MetricsResult,
        stress: MetricsResult,
    ) -> Path:
        """Save a grouped FPY/OEE/TEEP chart without recalculating metrics."""
        metric_pairs = (
            ("FPY", baseline.fpy.value, stress.fpy.value),
            ("OEE", baseline.oee.value, stress.oee.value),
            ("TEEP", baseline.teep.value, stress.teep.value),
        )
        if any(base is None or stressed is None for _, base, stressed in metric_pairs):
            raise ValueError("Для графика эффективности нужны рассчитанные FPY, OEE и TEEP")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        labels = [name for name, _, _ in metric_pairs]
        baseline_values = [float(value) * 100 for _, value, _ in metric_pairs]
        stress_values = [float(value) * 100 for _, _, value in metric_pairs]
        positions = list(range(len(labels)))
        width = 0.36

        figure, axis = plt.subplots(figsize=(9, 5.5), dpi=160)
        baseline_bars = axis.bar(
            [position - width / 2 for position in positions],
            baseline_values,
            width,
            label="Базовый сценарий",
            color="#31688E",
        )
        stress_bars = axis.bar(
            [position + width / 2 for position in positions],
            stress_values,
            width,
            label="Стрессовый сценарий",
            color="#D1495B",
        )
        axis.set_title("Сравнение показателей эффективности", pad=14)
        axis.set_ylabel("Значение, %")
        axis.set_xticks(positions, labels)
        axis.set_ylim(0, 100)
        axis.grid(axis="y", alpha=0.25)
        axis.legend()
        axis.bar_label(
            baseline_bars,
            labels=[f"{value:.1f}%" for value in baseline_values],
            padding=3,
        )
        axis.bar_label(
            stress_bars,
            labels=[f"{value:.1f}%" for value in stress_values],
            padding=3,
        )
        figure.tight_layout()
        figure.savefig(path, bbox_inches="tight")
        plt.close(figure)
        return path
