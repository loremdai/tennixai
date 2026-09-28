from datetime import UTC, datetime, timedelta

from app.markets.rules_index import MarketRulesIndex, RuleAuthorization

NOW = datetime(2026, 9, 28, 8, 0, tzinfo=UTC)


def test_rules_are_unavailable_until_a_complete_scan_is_published():
    clock = [NOW]
    index = MarketRulesIndex(now=lambda: clock[0], max_age=timedelta(minutes=4))

    assert index.get("mkt_1") is None
    index.publish({"mkt_1": RuleAuthorization(rules_hash="hash_a", version=1)})

    assert index.get("mkt_1") == RuleAuthorization(rules_hash="hash_a", version=1)


def test_invalidation_and_old_scan_fail_closed():
    clock = [NOW]
    index = MarketRulesIndex(now=lambda: clock[0], max_age=timedelta(minutes=4))
    index.publish({"mkt_1": RuleAuthorization(rules_hash="hash_a", version=1)})

    index.invalidate()
    assert index.get("mkt_1") is None

    index.publish({"mkt_1": RuleAuthorization(rules_hash="hash_a", version=1)})
    clock[0] += timedelta(minutes=4, microseconds=1)
    assert index.get("mkt_1") is None


def test_returned_rule_versions_are_flagged_for_review():
    clock = [NOW]
    index = MarketRulesIndex(now=lambda: clock[0], max_age=timedelta(minutes=4))
    index.publish({"mkt_1": RuleAuthorization(rules_hash="hash_a", version=3)})

    state = index.get("mkt_1")
    assert state is not None
    assert state.rules_changed is True
