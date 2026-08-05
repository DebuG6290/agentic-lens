import digest_store
import evaluation
import feedback_store


def test_digest_history_and_feedback_metrics(tmp_path, monkeypatch):
    monkeypatch.setattr(digest_store, "DIGEST_DIR", tmp_path / "digests")
    monkeypatch.setattr(feedback_store, "FEEDBACK_DIR", tmp_path / "feedback")

    article = {"title": "Medicaid cuts", "link": "https://example.test/a"}
    feedback_store.record_feedback("hospital", article, "relevant")
    digest_store.record_digest(
        "hospital",
        [{**article, "relevant": True, "confidence": 0.8, "reason": "funding impact"}],
    )

    metrics = evaluation.evaluate_lens("hospital")
    assert metrics["labeled"] == 1
    assert metrics["precision"] == 1.0
    assert metrics["recall"] == 1.0
