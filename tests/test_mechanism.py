from mechanism import is_mechanism_object, mechanism_signals


def test_valid_causal_mechanism_is_accepted():
    mechanism = {
        "entity": "Trump administration",
        "user_context": "US pharmaceutical export business",
        "mechanisms": [
            {
                "id": "trade_costs",
                "name": "Tariffs and trade restrictions",
                "causal_chain": ["new tariffs", "higher input costs", "lower margins"],
                "signals": ["tariffs", "duties"],
                "affected_assets": ["pharmaceutical exports"],
                "exclusions": ["general political commentary"],
            }
        ],
    }
    assert is_mechanism_object(mechanism)
    assert mechanism_signals(mechanism) == ["tariffs", "duties"]


def test_invalid_causal_chain_is_rejected():
    mechanism = {
        "entity": "Trump",
        "user_context": "hospital business",
        "mechanisms": [
            {
                "id": "policy",
                "name": "Healthcare policy",
                "causal_chain": ["policy"],
                "signals": ["Medicaid"],
            }
        ],
    }
    assert not is_mechanism_object(mechanism)


def test_legacy_v1_object_remains_supported():
    legacy = {
        "entity": "Trump",
        "user_context": "hospital business",
        "reasoning_paths": [{"path": "healthcare policy", "keywords": ["Medicaid"]}],
    }
    assert is_mechanism_object(legacy)
    assert mechanism_signals(legacy) == ["Medicaid"]
