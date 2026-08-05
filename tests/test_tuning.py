import digest_store
import feedback_store
import lens_store
from tuning import apply_tuning_suggestion, build_tuning_report


def test_build_report_suggests_repeated_relevant_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(lens_store, "LENS_DIR", tmp_path / "lenses")
    monkeypatch.setattr(digest_store, "DIGEST_DIR", tmp_path / "digests")
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path / "feedback")
    lens_store.save_lens("hospital", "hospital policy", {
        "entity": "hospital",
        "mechanisms": [{"id": "policy", "signals": ["existing"], "exclusions": []}],
    })
    for index in (1, 2):
        article = {"title": f"Policy {index}", "link": f"https://example.test/{index}"}
        feedback_store.record_feedback("hospital", article, "relevant")
        digest_store.record_digest("hospital", [{
            **article, "_matched_signals": ["new reimbursement signal"], "relevant": True,
        }])

    report = build_tuning_report("hospital")

    assert report["labeled"] == 2
    assert report["suggestions"][0]["action"] == "add_signal"
    assert report["suggestions"][0]["term"] == "new reimbursement signal"


def test_apply_suggestion_is_audited(tmp_path, monkeypatch):
    monkeypatch.setattr(lens_store, "LENS_DIR", tmp_path)
    lens_store.save_lens("hospital", "hospital policy", {
        "entity": "hospital",
        "mechanisms": [{"id": "policy", "signals": [], "exclusions": []}],
    })

    apply_tuning_suggestion("hospital", {
        "id": "add_signal:reimbursement", "action": "add_signal", "term": "reimbursement",
    })
    lens = lens_store.load_lens("hospital")

    assert lens["mechanism_object"]["mechanisms"][0]["signals"] == ["reimbursement"]
    assert lens["tuning_history"][0]["suggestion_id"] == "add_signal:reimbursement"


def test_report_suggests_repeated_exclusion_signal(tmp_path, monkeypatch):
    monkeypatch.setattr(lens_store, "LENS_DIR", tmp_path / "lenses")
    monkeypatch.setattr(digest_store, "DIGEST_DIR", tmp_path / "digests")
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path / "feedback")
    lens_store.save_lens("hospital", "hospital policy", {
        "entity": "hospital",
        "mechanisms": [{"id": "policy", "signals": ["existing"], "exclusions": []}],
    })
    for index in (1, 2):
        article = {"title": f"Noise {index}", "link": f"https://example.test/noise/{index}"}
        feedback_store.record_feedback("hospital", article, "not_relevant")
        digest_store.record_digest("hospital", [{
            **article, "_matched_signals": ["noise signal"], "relevant": False,
        }])

    report = build_tuning_report("hospital")

    assert report["suggestions"][0]["action"] == "add_exclusion"
    assert report["suggestions"][0]["term"] == "noise signal"
