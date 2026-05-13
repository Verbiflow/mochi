"""Shared path validation helpers for tool implementations.

Extracts the ``resolve() + relative_to()`` and ``..`` traversal check
patterns previously duplicated across skill_manager_tool, skills_tool,
skills_hub, cronjob_tools, and credential_files.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def validate_within_dir(path: Path, root: Path) -> Optional[str]:
    """Ensure *path* resolves to a location within *root*.

    Returns an error message string if validation fails, or ``None`` if the
    path is safe.  Uses ``Path.resolve()`` to follow symlinks and normalize
    ``..`` components.

    Usage::

        error = validate_within_dir(user_path, allowed_root)
        if error:
            return json.dumps({"error": error})
    """
    try:
        resolved = path.resolve()
        root_resolved = root.resolve()
        resolved.relative_to(root_resolved)
    except (ValueError, OSError) as exc:
        return f"Path escapes allowed directory: {exc}"
    return None


def has_traversal_component(path_str: str) -> bool:
    """Return True if *path_str* contains ``..`` traversal components.

    Quick check for obvious traversal attempts before doing full resolution.
    """
    parts = Path(path_str).parts
    return ".." in parts


def is_gateway_auth_path(path: str | Path) -> bool:
    """True when *path* resolves under ~/.flage/gateway-auth.

    Gateway auth dirs hold per-remote-user browser cookies, MCP auth tokens,
    and action state. The Mac mini agent can technically read them, so file
    tools must enforce this boundary explicitly.
    """
    try:
        resolved = Path(os.path.expanduser(str(path))).resolve()
        root = (Path.home() / ".flage" / "gateway-auth").resolve()
        resolved.relative_to(root)
        return True
    except (ValueError, OSError):
        return False


def gateway_auth_path_error(path: str | Path) -> str | None:
    if is_gateway_auth_path(path):
        return (
            f"Access denied: {path} is under ~/.flage/gateway-auth, which "
            "contains scoped gateway auth and browser session state."
        )
    return None
