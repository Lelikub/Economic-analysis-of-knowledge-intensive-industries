"""Structured implementation-problem journal used by the deliverables."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HarnessLogEntry:
    number: int
    stage: str
    task: str
    code_fragment: str
    issue: str
    cause: str
    resolution: str
    recheck_result: str


class HarnessLogDataError(ValueError):
    """Raised when the structured Harness Log source violates its schema."""


class HarnessLogLoader:
    """Load and validate the implementation journal from UTF-8 JSON."""

    _fields = frozenset(HarnessLogEntry.__dataclass_fields__)
    _text_fields = _fields - {"number"}

    def load(self, path: Path) -> tuple[HarnessLogEntry, ...]:
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise HarnessLogDataError(f"Cannot load Harness Log: {exc}") from exc

        if not isinstance(payload, list):
            raise HarnessLogDataError("Harness Log must be a JSON array")

        entries: list[HarnessLogEntry] = []
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise HarnessLogDataError(f"Row {index} must be an object")

            keys = set(item)
            missing = self._fields - keys
            unknown = keys - self._fields
            if missing:
                raise HarnessLogDataError(
                    f"Row {index} has missing fields: {', '.join(sorted(missing))}"
                )
            if unknown:
                raise HarnessLogDataError(
                    f"Row {index} has unknown fields: {', '.join(sorted(unknown))}"
                )

            number = item["number"]
            if type(number) is not int or number <= 0:
                raise HarnessLogDataError(f"Row {index} number must be a positive integer")
            for field in self._text_fields:
                value = item[field]
                if not isinstance(value, str) or not value.strip():
                    raise HarnessLogDataError(
                        f"Row {index} field {field!r} must be a non-empty string"
                    )

            entries.append(HarnessLogEntry(**item))

        actual_numbers = [entry.number for entry in entries]
        expected_numbers = list(range(1, len(entries) + 1))
        if actual_numbers != expected_numbers:
            raise HarnessLogDataError(
                "Harness Log number sequence must be consecutive from 1"
            )

        return tuple(entries)
