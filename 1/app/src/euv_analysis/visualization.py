"""OPEX structure visualization from lecture slide 25."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


OPEX_SHARES: dict[str, float] = {
    "Сырье и прекурсоры": 0.25,
    "Утилиты": 0.20,
    "Персонал": 0.30,
    "ТОиР": 0.15,
    "Compliance / качество / метрология": 0.10,
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
        axis.set_title("Структура OPEX в High-Tech производстве", pad=16)
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
