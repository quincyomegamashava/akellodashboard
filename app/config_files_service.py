"""Allowlisted project config file read/write for Schema Studio (super-admin)."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app

SETTING_KEY_FILE_EDITS = "allow_web_file_edits"

# Relative to project root (parent of app/)
ALLOWED_FILES: dict[str, dict[str, str]] = {
    ".env": {
        "label": "Environment (.env)",
        "description": "Runtime secrets and feature flags. Restart the app after saving for most keys.",
        "mode": "sh",
        "kind": "env",
    },
    ".env.example": {
        "label": "Environment example",
        "description": "Template for .env — safe to commit; no real secrets.",
        "mode": "sh",
        "kind": "env",
    },
    "requirements.txt": {
        "label": "requirements.txt",
        "description": "Python dependencies.",
        "mode": "text",
        "kind": "text",
    },
    "notes": {
        "label": "notes",
        "description": "Local developer notes (optional).",
        "mode": "markdown",
        "kind": "text",
    },
}

_SENSITIVE_KEY_RE = re.compile(
    r"(PASSWORD|SECRET|API_KEY|TOKEN|PRIVATE|PASS\b|CREDENTIAL)",
    re.I,
)


def project_root() -> Path:
    # app/ is one level under project root
    return Path(current_app.root_path).resolve().parent


def _normalize_rel(rel_path: str) -> str:
    key = (rel_path or "").replace("\\", "/").strip()
    while key.startswith("./"):
        key = key[2:]
    return key


def _resolve_allowed(rel_path: str) -> Path | None:
    key = _normalize_rel(rel_path)
    if key not in ALLOWED_FILES:
        return None
    root = project_root()
    target = (root / key).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target


def _truthy(val: str | None) -> bool:
    return str(val or "").strip().lower() in ("true", "1", "t", "yes", "y", "on")


def env_file_edits_enabled() -> bool:
    return bool(current_app.config.get("ALLOW_WEB_FILE_EDITS", False))


def db_file_edits_enabled() -> bool:
    try:
        from app.models import AppSetting
        return _truthy(AppSetting.get_value(SETTING_KEY_FILE_EDITS, "false"))
    except Exception:
        return False


def files_enabled() -> bool:
    """True if env flag OR super-admin DB toggle is on."""
    return env_file_edits_enabled() or db_file_edits_enabled()


def file_edits_status() -> dict[str, Any]:
    env_on = env_file_edits_enabled()
    db_on = db_file_edits_enabled()
    enabled = env_on or db_on
    if env_on and db_on:
        source = "env+db"
    elif env_on:
        source = "env"
    elif db_on:
        source = "db"
    else:
        source = "off"
    return {
        "enabled": enabled,
        "env_enabled": env_on,
        "db_enabled": db_on,
        "source": source,
    }


def set_db_file_edits_enabled(enabled: bool, user_id: int | None = None) -> dict[str, Any]:
    from app.models import AppSetting
    AppSetting.set_value(
        SETTING_KEY_FILE_EDITS,
        "true" if enabled else "false",
        user_id=user_id,
        description="Allow Schema Studio Files panel to edit allowlisted project files (.env, etc.)",
    )
    return file_edits_status()


def list_config_files() -> list[dict[str, Any]]:
    root = project_root()
    rows = []
    for rel, meta in ALLOWED_FILES.items():
        path = root / rel
        exists = path.is_file()
        rows.append({
            "path": rel,
            "label": meta["label"],
            "description": meta["description"],
            "mode": meta["mode"],
            "kind": meta["kind"],
            "exists": exists,
            "size": path.stat().st_size if exists else 0,
            "modified": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z" if exists else None,
        })
    return rows


def parse_env_content(text: str) -> list[dict[str, Any]]:
    """Parse .env into editable rows while preserving comments/blanks in raw mode."""
    rows: list[dict[str, Any]] = []
    for i, line in enumerate(text.splitlines()):
        raw = line
        stripped = line.strip()
        if not stripped:
            rows.append({"type": "blank", "line": i + 1, "raw": raw})
            continue
        if stripped.startswith("#"):
            rows.append({"type": "comment", "line": i + 1, "raw": raw, "text": stripped[1:].lstrip()})
            continue
        if "=" not in stripped:
            rows.append({"type": "raw", "line": i + 1, "raw": raw})
            continue
        key, _, val = stripped.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        rows.append({
            "type": "entry",
            "line": i + 1,
            "key": key,
            "value": val,
            "sensitive": bool(_SENSITIVE_KEY_RE.search(key)),
            "raw": raw,
        })
    return rows


def serialize_env_entries(entries: list[dict[str, Any]]) -> str:
    """Build .env text from key/value entries (form editor). Comments optional."""
    lines: list[str] = []
    for item in entries or []:
        kind = (item.get("type") or "entry").strip().lower()
        if kind == "blank":
            lines.append("")
        elif kind == "comment":
            text = str(item.get("text") or item.get("raw") or "").lstrip("#").strip()
            lines.append(f"# {text}" if text else "#")
        elif kind == "entry":
            key = str(item.get("key") or "").strip()
            if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            val = str(item.get("value") if item.get("value") is not None else "")
            if re.search(r'[\s#"\'\\]', val) or val == "":
                # quote values with spaces / specials
                escaped = val.replace("\\", "\\\\").replace('"', '\\"')
                lines.append(f'{key}="{escaped}"')
            else:
                lines.append(f"{key}={val}")
        else:
            raw = str(item.get("raw") or "")
            if raw:
                lines.append(raw)
    return "\n".join(lines) + ("\n" if lines else "")


def read_config_file(rel_path: str) -> dict[str, Any]:
    path = _resolve_allowed(rel_path)
    if path is None:
        raise ValueError("File is not in the allowlist.")
    key = _normalize_rel(rel_path)
    meta = ALLOWED_FILES[key]
    if not path.is_file():
        return {
            "path": key,
            "exists": False,
            "content": "",
            "entries": [],
            **meta,
        }
    content = path.read_text(encoding="utf-8", errors="replace")
    payload: dict[str, Any] = {
        "path": key,
        "exists": True,
        "content": content,
        "size": path.stat().st_size,
        "modified": datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z",
        **meta,
    }
    if meta.get("kind") == "env":
        payload["entries"] = parse_env_content(content)
    return payload


def _backup(path: Path) -> str | None:
    if not path.is_file():
        return None
    bak_dir = project_root() / ".studio_backups"
    bak_dir.mkdir(exist_ok=True)
    stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    dest = bak_dir / f"{path.name}.{stamp}.bak"
    shutil.copy2(path, dest)
    return str(dest.relative_to(project_root())).replace("\\", "/")


def write_config_file(
    rel_path: str,
    *,
    content: str | None = None,
    entries: list[dict[str, Any]] | None = None,
    reload_env: bool = True,
) -> dict[str, Any]:
    if not files_enabled():
        raise PermissionError(
            "Web file edits are disabled. Enable the Files toggle in Schema Studio "
            "or set ALLOW_WEB_FILE_EDITS=true."
        )
    key = _normalize_rel(rel_path)
    path = _resolve_allowed(key)
    if path is None:
        raise ValueError("File is not in the allowlist.")
    meta = ALLOWED_FILES[key]

    if entries is not None and meta.get("kind") == "env":
        text = serialize_env_entries(entries)
    elif content is not None:
        text = str(content)
        if not text.endswith("\n"):
            text += "\n"
    else:
        raise ValueError("Provide content or entries.")

    # Basic size guard (2 MB)
    if len(text.encode("utf-8")) > 2_000_000:
        raise ValueError("File too large to save via Studio (max 2MB).")

    backup = _backup(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")

    reloaded = False
    if reload_env and path.name == ".env":
        try:
            from dotenv import load_dotenv
            load_dotenv(path, override=True)
            reloaded = True
        except Exception:
            reloaded = False

    return {
        "path": key,
        "saved": True,
        "backup": backup,
        "bytes": len(text.encode("utf-8")),
        "reloaded_env": reloaded,
        "hint": "Restart the application process for all settings to take full effect."
        if path.name == ".env"
        else None,
    }
