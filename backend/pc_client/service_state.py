"""Immutable state and events for the BLE connection lifecycle.

The connection manager is the only consumer of :class:`LifecycleEvent` values.
Keeping these definitions free of Bleak and database code makes state invariants
straightforward to test.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from typing import Any


class ConnectionPhase(str, Enum):
    STOPPED = "STOPPED"
    DISCOVERING = "DISCOVERING"
    SELECTION_REQUIRED = "SELECTION_REQUIRED"
    AUTHENTICATION_REQUIRED = "AUTHENTICATION_REQUIRED"
    PAIRING = "PAIRING"
    CONNECTING = "CONNECTING"
    VERIFYING = "VERIFYING"
    CONNECTED = "CONNECTED"
    RECONNECTING = "RECONNECTING"
    DISCONNECTING = "DISCONNECTING"
    DISCONNECTED = "DISCONNECTED"


class CredentialState(str, Enum):
    MISSING = "MISSING"
    AVAILABLE = "AVAILABLE"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class LifecycleEventType(str, Enum):
    """Inputs that can wake or redirect the connection manager."""

    START = "START"
    INTENT_CHANGED = "INTENT_CHANGED"
    DISCOVERY_RESULT = "DISCOVERY_RESULT"
    LINK_LOST = "LINK_LOST"
    STOP = "STOP"


@dataclass(frozen=True)
class LifecycleEvent:
    kind: LifecycleEventType
    generation: int
    reason: str
    value: Any = None


@dataclass(frozen=True)
class ControllerState:
    phase: ConnectionPhase
    desired_connected: bool
    target: Any
    connected: bool
    ready: bool
    credential_state: CredentialState
    retry_count: int
    next_retry_at_utc: datetime | None
    last_seen_utc: datetime | None
    last_error: str | None
    revision: int
    changed_at_utc: datetime
    reason: str


def transition_state(
    previous: ControllerState,
    now: datetime,
    *,
    phase: ConnectionPhase | None = None,
    reason: str,
    **changes: Any,
) -> ControllerState:
    """Return one validated, immutable lifecycle snapshot."""

    state = replace(
        previous,
        phase=previous.phase if phase is None else phase,
        revision=previous.revision + 1,
        changed_at_utc=now,
        reason=reason,
        **changes,
    )
    if state.ready and not state.connected:
        raise ValueError("a ready BLE service must have a connected transport")
    if state.phase is ConnectionPhase.CONNECTED and not (
        state.connected and state.ready
    ):
        raise ValueError("CONNECTED requires a verified, ready transport")
    if state.phase is ConnectionPhase.STOPPED and state.desired_connected:
        raise ValueError("a stopped service cannot request a connection")
    return state
