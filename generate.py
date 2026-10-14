"""Generate the demo datasets: python generate.py [--out data]."""
import argparse
from pathlib import Path

from generator import eu_shop

GENERATORS = {"eu_shop": eu_shop.generate}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent / "data")
    args = parser.parse_args()
    for name, generate in GENERATORS.items():
        generate(args.out / name)
        print(f"{name}: written to {args.out / name}")


if __name__ == "__main__":
    main()
