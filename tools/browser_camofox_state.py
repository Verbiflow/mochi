"""Hermes-managed Camofox state helpers.

Provides profile-scoped identity and state directory paths for Camofox
persistent browser profiles.  When managed persistence is enabled, Hermes
sends a deterministic userId derived from the active profile so that
Camofox can map it to the same persistent browser profile directory
across restarts.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Dict, Optional

from hermes_constants import get_hermes_home

CAMOFOX_STATE_DIR_NAME = "browser_auth"
CAMOFOX_STATE_SUBDIR = "camofox"


def get_camofox_state_dir() -> Path:
    """Return the profile-scoped root directory for Camofox persistence."""
    try:
        from gateway.session_context import get_session_env

        hosted_root = get_session_env("MOCHI_HOSTED_BROWSER_PROFILE_ROOT", "").strip()
        if hosted_root:
            return Path(hosted_root).expanduser() / CAMOFOX_STATE_SUBDIR
    except Exception:
        hosted_root = ""
    if os.getenv("MOCHI_HOSTED_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        raise RuntimeError("Hosted browser profile root is not set; refusing to use global Camofox state.")
    return get_hermes_home() / CAMOFOX_STATE_DIR_NAME / CAMOFOX_STATE_SUBDIR


def get_camofox_identity(task_id: Optional[str] = None) -> Dict[str, str]:
    """Return the stable Hermes-managed Camofox identity for this profile.

    The user identity is profile-scoped (same Hermes profile = same userId).
    The session key is scoped to the logical browser task so newly created
    tabs within the same profile reuse the same identity contract.
    """
    scope_root = str(get_camofox_state_dir())
    logical_scope = task_id or "default"
    user_digest = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"camofox-user:{scope_root}",
    ).hex[:10]
    session_digest = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"camofox-session:{scope_root}:{logical_scope}",
    ).hex[:16]
    return {
        "user_id": f"hermes_{user_digest}",
        "session_key": f"task_{session_digest}",
    }
