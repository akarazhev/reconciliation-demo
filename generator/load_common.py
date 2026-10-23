"""Shared helpers for the load check datasets: truth rows keyed by entity and column, four decimals."""
from dataclasses import dataclass
from decimal import Decimal

LOAD_TRUTH_HEADER = ["dataset", "entity", "cause", "key", "column_name", "difference"]


@dataclass(frozen=True)
class LoadTruth:
    """One planted difference. `difference` is target minus source for numbers, hours for times, -1 for a row
    missing in the target and 1 for an extra row; None for text. `column_name` is None for whole rows."""
    dataset: str
    entity: str
    cause: str
    key: str
    column_name: str | None
    difference: Decimal | None


def load_truth_rows(truth: list[LoadTruth]) -> list[list[str]]:
    ordered = sorted(truth, key=lambda t: (t.entity, t.cause, t.key, t.column_name or ""))
    return [[t.dataset, t.entity, t.cause, t.key, t.column_name or "",
             "" if t.difference is None else f"{t.difference:.4f}"] for t in ordered]
