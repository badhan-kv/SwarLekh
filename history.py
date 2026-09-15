"""Per-dictation record logging to a JSON file under history/, with retention.

The active directory can be overridden by the user (tray menu "Change save
location..." or config.set_history_dir()) — current_history_dir() resolves
that dynamically on every call, not just once at import time, so a change
takes effect immediately without restarting the app.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import config

HISTORY_DIR = Path(__file__).parent / "history"  # default, if no override is set

DEFAULT_RETENTION_DAYS = 30


def current_history_dir() -> Path:
    """The directory records are actually saved to right now: a user
    override if one is set, else the default HISTORY_DIR."""
    override = config.get_history_dir()
    return Path(override) if override else HISTORY_DIR


def record_dictation(mode: str, raw_transcript: str, output: str, base_dir: Path | None = None) -> Path:
    """Write one JSON record for a single dictation event and return its path."""
    base_dir = base_dir if base_dir is not None else current_history_dir()
    base_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M%S")
    path = base_dir / f"{timestamp}.json"
    record = {
        "timestamp": now.isoformat(),
        "mode": mode,
        "raw_transcript": raw_transcript,
        "output": output,
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def load_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def list_records(base_dir: Path | None = None) -> list[dict]:
    """Return all dictation records, newest first."""
    base_dir = base_dir if base_dir is not None else current_history_dir()
    if not base_dir.exists():
        return []
    files = sorted(base_dir.glob("*.json"), reverse=True)
    return [load_record(f) for f in files]


def records_older_than(days: int, base_dir: Path | None = None, now: datetime | None = None) -> list[Path]:
    """Return record file paths older than `days` days, based on filename timestamp."""
    base_dir = base_dir if base_dir is not None else current_history_dir()
    now = now or datetime.now()
    cutoff = now - timedelta(days=days)
    if not base_dir.exists():
        return []
    matches = [
        f for f in base_dir.glob("*.json")
        if datetime.strptime(f.stem, "%Y-%m-%d_%H%M%S") < cutoff
    ]
    return sorted(matches, reverse=True)


def delete_records(paths: list[Path]) -> int:
    """Delete the given record files. Returns how many were actually removed."""
    count = 0
    for p in paths:
        if p.exists():
            p.unlink()
            count += 1
    return count


def purge_older_than(
    days: int = DEFAULT_RETENTION_DAYS, base_dir: Path | None = None, now: datetime | None = None
) -> int:
    """Delete dictation records older than `days` days. Returns count deleted."""
    base_dir = base_dir if base_dir is not None else current_history_dir()
    return delete_records(records_older_than(days, base_dir=base_dir, now=now))
