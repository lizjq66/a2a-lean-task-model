"""Verify installed source provenance before attributing results to an SDK commit."""
from __future__ import annotations

import importlib.metadata
import json
from pathlib import Path
import subprocess
from urllib.parse import unquote, urlparse


def require_revision(distribution, expected):
    dist = importlib.metadata.distribution(distribution)
    raw = dist.read_text("direct_url.json")
    if raw is None:
        raise RuntimeError(f"{distribution} needs an installation from the pinned Git source")
    source = json.loads(raw)
    if "vcs_info" in source:
        actual = source["vcs_info"]["commit_id"]
    else:
        url = urlparse(source["url"])
        if url.scheme != "file":
            raise RuntimeError("Unsupported source provenance")
        checkout = Path(unquote(url.path))
        actual = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "-C", str(checkout), "diff", "HEAD", "--", "src"], text=True)
        if dirty:
            raise RuntimeError("Local SDK source has tracked modifications")
    if actual != expected:
        raise RuntimeError(f"Expected {distribution} commit {expected}, got {actual}")
    return actual
