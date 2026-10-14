"""Shared helpers for the demo data generator: money, CSV writing, truth rows."""
import csv
import datetime as dt
import random
import string
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

CENT = Decimal("0.01")
TRUTH_HEADER = ["level", "cause", "key", "kind", "difference"]
_ALPHABET = string.ascii_letters + string.digits


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def token(rng: random.Random, length: int = 14) -> str:
    return "".join(rng.choice(_ALPHABET) for _ in range(length))


def days(first: dt.date, last: dt.date) -> list[dt.date]:
    return [first + dt.timedelta(n) for n in range((last - first).days + 1)]


def write_csv(path: Path, header: list[str], rows: list[list], delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=delimiter, lineterminator="\n")
        writer.writerow(header)
        writer.writerows(rows)


@dataclass(frozen=True)
class Truth:
    level: str
    cause: str
    key: str
    kind: str
    difference: Decimal


def truth_rows(truth: list[Truth]) -> list[list]:
    ordered = sorted(truth, key=lambda t: (t.level, t.cause, t.key, t.kind))
    return [[t.level, t.cause, t.key, t.kind, f"{t.difference:.2f}"] for t in ordered]
