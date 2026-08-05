import json

import pytest

import feedback_store


def test_records_and_reads_feedback(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    feedback_store.record_feedback(
        "hospital",
        {"title": "Medicaid cuts", "link": "https://example.test/a"},
        "relevant",
        "Direct funding impact",
    )
    entries = feedback_store.recent_feedback("hospital")
    assert entries[0]["label"] == "relevant"
    assert entries[0]["article"]["title"] == "Medicaid cuts"


def test_rejects_unknown_label(tmp_path, monkeypatch):
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path)
    with pytest.raises(ValueError, match="feedback label"):
        feedback_store.record_feedback("hospital", {}, "maybe")
