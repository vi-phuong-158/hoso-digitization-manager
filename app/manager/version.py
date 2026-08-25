"""Application identity shared by the UI, health endpoint, and packaging."""

from __future__ import annotations

import os
import json
from pathlib import Path


APP_NAME = "Hồ sơ Digitization Manager"
APP_VERSION = os.environ.get("HOSO_APP_VERSION", "0.2.0")


def _build_sha() -> str:
    value = os.environ.get("HOSO_BUILD_SHA")
    if value:
        return value
    try:
        metadata = json.loads(Path(__file__).with_name("build_identity.json").read_text(encoding="utf-8"))
        return str(metadata.get("build_sha") or "unknown")
    except (OSError, ValueError, TypeError):
        return "unknown"


BUILD_SHA = _build_sha()
