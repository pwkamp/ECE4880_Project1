"""Small, dependency-light loaders and atomic JSON writers."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class DataFileError(ValueError):
    """Raised when a versioned runner data file cannot be decoded."""


def load_data(path: Path) -> Any:
    """Load JSON or YAML. Generated manifests use JSON, a YAML subset."""
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError as json_error:
        try:
            import yaml  # type: ignore
        except ImportError as error:
            raise DataFileError(
                f"{path} is not JSON; install PyYAML to author general YAML"
            ) from error
        try:
            return yaml.safe_load(text)
        except Exception as error:
            raise DataFileError(f"could not parse {path}: {error}") from json_error


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    atomic_write_text(path, json.dumps(value, indent=2, sort_keys=False) + "\n")
