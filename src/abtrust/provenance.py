"""Local, JSON-serializable provenance for simulations and data analyses."""

from __future__ import annotations

import hashlib
import platform
import subprocess
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def runtime_provenance() -> dict[str, Any]:
    dependencies = {}
    for name in ("abtrust", "numpy", "scipy", "pandas", "matplotlib", "streamlit"):
        try:
            dependencies[name] = version(name)
        except PackageNotFoundError:
            dependencies[name] = None
    root = Path(__file__).resolve().parents[2]
    git: dict[str, Any] = {"commit": None, "dirty": None}
    if (root / ".git").exists():
        try:
            options = dict(cwd=root, capture_output=True, text=True, timeout=5, check=True)
            git["commit"] = subprocess.run(["git", "rev-parse", "HEAD"], **options).stdout.strip()
            git["dirty"] = bool(subprocess.run(["git", "status", "--porcelain"], **options).stdout.strip())
        except (OSError, subprocess.SubprocessError):
            pass
    # The hash also identifies uncommitted source, without collecting local IDs,
    # environment variables, private Git configuration or absolute user paths.
    digest = hashlib.sha256()
    sources = sorted(p for folder in ("src/abtrust", "scripts", "app")
                     for p in (root / folder).glob("*.py")) if (root / "pyproject.toml").exists() else []
    for path in sources:
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return {"python": platform.python_version(), "platform": platform.system(),
            "dependencies": dependencies, "git": git,
            "source_sha256": digest.hexdigest() if sources else None}


def write_analysis_manifest(
    output: str | Path, *, data_kind: str, settings: dict[str, Any], input_path: str | Path | None = None
) -> Path:
    import json

    if data_kind not in {"simulation", "real_data", "user_supplied"}:
        raise ValueError("data_kind must explicitly identify simulation, real_data, or user_supplied")
    manifest = {"schema_version": 1, "analyzed_at_utc": utc_now(), "data_kind": data_kind,
                "settings": settings, "runtime": runtime_provenance()}
    if input_path is not None:
        path = Path(input_path)
        manifest["input"] = {"file": path.name, "sha256": file_sha256(path)}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False), encoding="utf-8")
    return output
