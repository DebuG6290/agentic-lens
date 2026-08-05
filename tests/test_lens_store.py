import json

import pytest

import lens_store


def test_save_load_and_list_lens(tmp_path, monkeypatch):
    monkeypatch.setattr(lens_store, "LENS_DIR", tmp_path)
    mechanism = {"entity": "Trump", "user_context": "hospital business"}

    lens_store.save_lens("hospital", "Trump affects my hospital business", mechanism)

    assert lens_store.list_lenses() == ["hospital"]
    assert lens_store.load_lens("hospital")["mechanism_object"] == mechanism
    assert json.loads((tmp_path / "hospital.json").read_text())["user_intent"].startswith("Trump")


def test_lens_names_cannot_escape_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(lens_store, "LENS_DIR", tmp_path)
    with pytest.raises(ValueError):
        lens_store.save_lens("../outside", "intent", {})


def test_missing_lens_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(lens_store, "LENS_DIR", tmp_path)
    with pytest.raises(ValueError, match="lens not found"):
        lens_store.load_lens("missing")
