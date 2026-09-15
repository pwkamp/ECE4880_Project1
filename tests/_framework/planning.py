"""Test selection and non-mutating execution planning."""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

from tests._framework.capabilities import check_capabilities
from tests._framework.models import PlannedTest, TestManifest, TestStatus


def group_for(test_id: str) -> str:
    return test_id.split("-", 1)[0].lower()


def select_tests(
    manifests: Sequence[TestManifest],
    test_ids: Sequence[str] = (),
    group: Optional[str] = None,
    requirement: Optional[str] = None,
    uid: Optional[str] = None,
    feasibility: Optional[str] = None,
    changed_component: Optional[str] = None,
) -> List[TestManifest]:
    selected = list(manifests)
    if test_ids:
        requested = {value.upper() for value in test_ids}
        selected = [item for item in selected if item.test_id in requested]
    if group:
        selected = [item for item in selected if group_for(item.test_id) == group.lower()]
    if requirement:
        selected = [item for item in selected if any(ref.jira == requirement for ref in item.requirements)]
    if uid:
        selected = [item for item in selected if any(ref.uid == uid for ref in item.requirements)]
    if feasibility:
        selected = [item for item in selected if feasibility.lower() in item.feasibility.lower()]
    if changed_component:
        selected = [
            item
            for item in selected
            if changed_component.lower()
            in {owner.lower() for owner in item.owners}
        ]
    return selected


def plan_tests(manifests: Iterable[TestManifest], profile_name: str) -> List[PlannedTest]:
    plans: List[PlannedTest] = []
    for manifest in manifests:
        profile = manifest.profiles.get(profile_name)
        if profile is None:
            plans.append(PlannedTest(manifest, None, TestStatus.SKIP, f"profile {profile_name!r} is not defined", []))
            continue
        capabilities = check_capabilities(profile.capabilities)
        missing = [item for item in capabilities if not item.available]
        if missing:
            reason = "; ".join(item.detail for item in missing)
            plans.append(PlannedTest(manifest, profile, TestStatus.BLOCKED, reason, capabilities))
        elif profile.automation == "manual":
            plans.append(PlannedTest(manifest, profile, TestStatus.MANUAL_REQUIRED, "profile requires a human operator", capabilities))
        else:
            plans.append(PlannedTest(manifest, profile, TestStatus.PASS, "ready to run", capabilities))
    return plans
