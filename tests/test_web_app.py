from web_app import source_config_from_form


def test_source_settings_preserve_connector_values_when_fields_are_omitted():
    current = {
        "rss_urls": ["https://example.test/rss"],
        "openalex": {"enabled": True, "lookback_days": 12, "max_results": 7},
        "pubmed": {"enabled": True, "lookback_days": 21, "max_results": 8},
        "crossref": {"enabled": False, "lookback_days": 45, "max_results": 9},
    }

    updated = source_config_from_form({"openalex": ["on"]}, current)

    assert updated["pubmed"] == {"enabled": False, "lookback_days": 21, "max_results": 8}
    assert updated["crossref"] == {"enabled": False, "lookback_days": 45, "max_results": 9}


def test_source_settings_accept_connector_values():
    updated = source_config_from_form({
        "pubmed": ["on"], "pubmed_days": ["14"], "pubmed_max": ["4"],
        "crossref_days": ["60"], "crossref_max": ["6"],
    }, {})

    assert updated["pubmed"] == {"enabled": True, "lookback_days": 14, "max_results": 4}
    assert updated["crossref"] == {"enabled": False, "lookback_days": 60, "max_results": 6}
