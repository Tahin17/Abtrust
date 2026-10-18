"""Create explicitly synthetic CSV fixtures for local browser acceptance."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="scratch_qa")
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(314)
    base = pd.DataFrame({"user_id": np.arange(1000), "variant": ["control"] * 200 + ["treatment"] * 800,
                         "converted": rng.binomial(1, 0.1, 1000).astype(float),
                         "complaints": rng.binomial(1, 0.02, 1000)})
    base.to_csv(out / "synthetic_20_80.csv", index=False)
    for name in ("duplicate_ids", "missing_arm", "missing_outcomes", "infinite_outcome"):
        frame = base.copy()
        if name == "duplicate_ids":
            frame.loc[1, "user_id"] = frame.loc[0, "user_id"]
        elif name == "missing_arm":
            frame.loc[0, "variant"] = None
        elif name == "missing_outcomes":
            frame.loc[:39, "converted"] = np.nan
        else:
            frame.loc[0, "converted"] = np.inf
        frame.to_csv(out / f"synthetic_{name}.csv", index=False)
    (out / "empty.csv").write_bytes(b"")
    base[["converted"]].to_csv(out / "one_column.csv", index=False)
    (out / "README.md").write_text(
        "# Synthetic browser QA fixtures\n\nAll customers and IDs are generated test data, not real people. "
        "The designed fixture allocation is 20% control and 80% treatment. Use custom 20/80 in the dashboard. "
        "These files test software behavior; do not report their effects as a real experiment.\n", encoding="utf-8")
    print(f"Synthetic fixtures written to {out}")


if __name__ == "__main__":
    main()
