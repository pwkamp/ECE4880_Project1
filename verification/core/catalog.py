"""Load and validate the version-controlled verification catalogs.

The ``.yaml`` catalogs intentionally contain JSON, which is a strict YAML 1.2
subset.  Keeping the parser in the standard library makes the qualification
runner usable from a clean Python installation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ALLOWED_OUTCOMES = {"PASS", "FAIL", "BLOCKED", "SKIPPED", "NOT_APPLICABLE"}
ALLOWED_METHODS = {"automated", "semi-automated", "manual"}
PROFILES = ("software", "integration", "hil", "full")
CATALOG_ROOT = Path(__file__).resolve().parents[1]
HASHED_CATALOGS = {"requirements.yaml", "tests.yaml", "setup_groups.yaml"}


class CatalogError(ValueError):
    """Raised when a qualification catalog could permit an invalid run."""


def load_catalog(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CatalogError(f"cannot load catalog {path}: {exc}") from exc


def catalog_hash(path: Path) -> str:
    resolved = path.resolve()
    if resolved.parent != CATALOG_ROOT or resolved.name not in HASHED_CATALOGS:
        raise CatalogError(f"refusing to hash a path outside the verification catalog: {path}")
    return hashlib.sha256(resolved.read_bytes()).hexdigest()


def validate_catalogs(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    requirements = load_catalog(root / "requirements.yaml")
    tests = load_catalog(root / "tests.yaml")
    fixtures = load_catalog(root / "fixtures.yaml")
    setup_groups = load_catalog(root / "setup_groups.yaml")
    if not isinstance(requirements, list) or not isinstance(tests, list) or not isinstance(fixtures, dict):
        raise CatalogError("requirements/tests must be arrays and fixtures must be an object")

    requirement_ids = [item.get("uid") for item in requirements]
    test_ids = [item.get("id") for item in tests]
    if None in requirement_ids or len(set(requirement_ids)) != len(requirement_ids):
        raise CatalogError("requirement UIDs must be present and unique")
    if None in test_ids or len(set(test_ids)) != len(test_ids):
        raise CatalogError("test IDs must be present and unique")

    known_requirements = set(requirement_ids)
    known_fixtures = set(fixtures)
    known_setup_groups = set(setup_groups)
    if "software" not in known_setup_groups:
        raise CatalogError("setup_groups.yaml must define the software group")
    for group_id, group in setup_groups.items():
        if not isinstance(group.get("order"), int):
            raise CatalogError(f"setup group {group_id}: integer order is required")
        if not isinstance(group.get("instructions"), list) or not group["instructions"]:
            raise CatalogError(f"setup group {group_id}: instructions are required")
    mapped: set[str] = set()
    for test in tests:
        method = test.get("method")
        if method not in ALLOWED_METHODS:
            raise CatalogError(f"{test['id']}: invalid method {method!r}")
        setup_group = test.get("setup_group", "software" if method == "automated" else None)
        if setup_group not in known_setup_groups:
            raise CatalogError(f"{test['id']}: invalid or missing setup_group {setup_group!r}")
        instruments = " ".join(test.get("instrumentation", [])).casefold()
        if setup_group == "power_cycle_no_uart" and ("uart" in instruments or "serial" in instruments):
            raise CatalogError(f"{test['id']}: power-cycle tests cannot require UART/serial instrumentation")
        if setup_group == "uart_live" and "uart" not in instruments and "serial" not in instruments:
            raise CatalogError(f"{test['id']}: uart_live tests must declare UART/serial instrumentation")
        profiles = set(test.get("profiles", []))
        if not profiles or not profiles.issubset(PROFILES):
            raise CatalogError(f"{test['id']}: invalid or empty profiles")
        unknown_requirements = set(test.get("requirements", [])) - known_requirements
        if unknown_requirements:
            raise CatalogError(f"{test['id']}: unknown requirements {sorted(unknown_requirements)}")
        unknown_fixtures = set(test.get("fixtures", [])) - known_fixtures
        if unknown_fixtures:
            raise CatalogError(f"{test['id']}: unknown fixtures {sorted(unknown_fixtures)}")
        if method != "automated" and not test.get("human_intervention"):
            raise CatalogError(f"{test['id']}: manual work must be described explicitly")
        for field in ("title", "description", "rationale"):
            if not isinstance(test.get(field), str) or not test[field].strip():
                raise CatalogError(f"{test['id']}: {field} must be a non-empty string")
        if not test.get("requirements"):
            raise CatalogError(f"{test['id']}: at least one requirement must be mapped")
        if not isinstance(test.get("pass_policy"), dict) or not test["pass_policy"]:
            raise CatalogError(f"{test['id']}: pass_policy must explicitly define acceptance")
        mapped.update(test.get("requirements", []))

    active = {item["uid"] for item in requirements if item.get("status", "active").lower() == "active"}
    unmapped = active - mapped
    if unmapped:
        raise CatalogError(f"active requirements are unmapped: {sorted(unmapped)}")
    return requirements, tests, fixtures
