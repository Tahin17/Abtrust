"""Run local verification and save a machine-readable execution record.

    python scripts/verify.py --integration --full

Full mode regenerates authoritative core, supplemental stress, and application
reports. Default mode sends quick Monte Carlo output to scratch_reports instead.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from abtrust.provenance import runtime_provenance, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--integration", action="store_true", help="enable actual Streamlit AppTest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / "reports/verification/execution.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1")
    env["ABTRUST_RUN_STREAMLIT_INTEGRATION"] = "1" if args.integration else "0"
    commands = [
        ["-m", "ruff", "check", ".", "--no-cache"],
        ["-m", "pytest", "-q"],
        ["-m", "abtrust.cli", "--version"],
        ["-m", "abtrust.cli", "plan", "--baseline", "0.10", "--mde", "0.05", "--relative", "--daily", "20000"],
        ["-m", "abtrust.cli", "validate", *([] if args.full else ["--scale", "0.05", "--out", "scratch_reports"])],
    ]
    if args.full:
        commands += [["-m", "abtrust.cli", "stress"], ["scripts/case_study.py"]]
        if (root / "data/hillstrom.csv").exists():
            commands.append(["scripts/hillstrom.py", "--csv", "data/hillstrom.csv"])
    record = {"started_at_utc": utc_now(), "runtime": runtime_provenance(),
              "full_budget": args.full, "streamlit_enabled": args.integration, "checks": []}
    for command in commands:
        print("Running: python " + " ".join(command), flush=True)
        started = utc_now()
        result = subprocess.run([sys.executable, *command], cwd=root, env=env, check=False)
        record["checks"].append({"command": ["python", *command], "started_at_utc": started,
                                  "finished_at_utc": utc_now(), "exit_code": result.returncode})
        record["finished_at_utc"] = utc_now()
        output.write_text(json.dumps(record, indent=2), encoding="utf-8")
        if result.returncode:
            return result.returncode
    record["real_data_run"] = any(c[0] == "scripts/hillstrom.py" for c in commands)
    record["all_checks_passed"] = True
    output.write_text(json.dumps(record, indent=2), encoding="utf-8")
    print(f"Execution record: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
