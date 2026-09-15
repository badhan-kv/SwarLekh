from datetime import datetime, timedelta

import config
import history


def test_current_history_dir_uses_default_when_no_override(monkeypatch):
    monkeypatch.setattr(config, "get_history_dir", lambda: None)
    assert history.current_history_dir() == history.HISTORY_DIR


def test_current_history_dir_uses_override_when_set(monkeypatch, tmp_path):
    custom = tmp_path / "my_notes"
    monkeypatch.setattr(config, "get_history_dir", lambda: str(custom))
    assert history.current_history_dir() == custom


def test_record_dictation_uses_override_when_no_base_dir_given(monkeypatch, tmp_path):
    custom = tmp_path / "my_notes"
    monkeypatch.setattr(config, "get_history_dir", lambda: str(custom))
    path = history.record_dictation("transcribe", "raw", "clean")
    assert path.parent == custom
    assert path.exists()


def test_record_dictation_writes_expected_fields(tmp_path):
    path = history.record_dictation("transcribe", "raw text", "clean text", base_dir=tmp_path)
    assert path.exists()
    record = history.load_record(path)
    assert record["mode"] == "transcribe"
    assert record["raw_transcript"] == "raw text"
    assert record["output"] == "clean text"
    assert "timestamp" in record


def test_list_records_newest_first(tmp_path, monkeypatch):
    times = iter(
        [
            datetime(2026, 1, 1, 10, 0, 0),
            datetime(2026, 1, 2, 10, 0, 0),
        ]
    )

    class _FakeDatetime(datetime):
        @classmethod
        def now(cls):
            return next(times)

    monkeypatch.setattr(history, "datetime", _FakeDatetime)

    history.record_dictation("transcribe", "first", "first out", base_dir=tmp_path)
    history.record_dictation("notes", "second", "second out", base_dir=tmp_path)

    records = history.list_records(base_dir=tmp_path)
    assert len(records) == 2
    assert records[0]["raw_transcript"] == "second"
    assert records[1]["raw_transcript"] == "first"


def test_list_records_empty_dir_returns_empty_list(tmp_path):
    assert history.list_records(base_dir=tmp_path / "does_not_exist") == []


def _write_record_at(base_dir, when: datetime, content="x"):
    base_dir.mkdir(parents=True, exist_ok=True)
    path = base_dir / f"{when.strftime('%Y-%m-%d_%H%M%S')}.json"
    path.write_text(
        f'{{"timestamp": "{when.isoformat()}", "mode": "transcribe", '
        f'"raw_transcript": "{content}", "output": "{content}"}}',
        encoding="utf-8",
    )
    return path


def test_records_older_than_boundary(tmp_path):
    now = datetime(2026, 9, 12, 12, 0, 0)
    old = _write_record_at(tmp_path, now - timedelta(days=31))
    recent = _write_record_at(tmp_path, now - timedelta(days=1))
    exactly_30 = _write_record_at(tmp_path, now - timedelta(days=30))

    older = history.records_older_than(30, base_dir=tmp_path, now=now)

    assert old in older
    assert recent not in older
    assert exactly_30 not in older  # exactly at the boundary is kept, not purged


def test_purge_older_than_deletes_and_returns_count(tmp_path):
    now = datetime(2026, 9, 12, 12, 0, 0)
    old = _write_record_at(tmp_path, now - timedelta(days=45))
    recent = _write_record_at(tmp_path, now - timedelta(days=2))

    deleted = history.purge_older_than(30, base_dir=tmp_path, now=now)

    assert deleted == 1
    assert not old.exists()
    assert recent.exists()
