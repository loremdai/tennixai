"""P3 persistence schema tests (T58).

Deterministic metadata inspection: exact table names, foreign keys, JSONB
evidence columns, timezone-aware timestamps and the exact unique constraints
that make the paper ledger idempotent and one-shot. No database required.
"""

from sqlalchemy import Index

from app.persistence.models import (
    Base,
    DecisionObservationRow,
    MarketExternalIdRow,
    MarketMatchLinkRow,
    MarketObservationRow,
    MarketResolutionRow,
    MarketRow,
    MarketRuleRow,
    PaperFillRow,
    PaperOrderIntentRow,
    PaperPositionRow,
    PaperTrackResultRow,
    PredictionSnapshotRow,
)

P3_TABLE_NAMES = {
    "markets",
    "market_external_ids",
    "market_rules",
    "market_match_links",
    "market_observations",
    "prediction_snapshots",
    "decision_observations",
    "paper_order_intents",
    "paper_fills",
    "paper_positions",
    "paper_track_results",
    "market_resolutions",
}

P3_ROW_MODELS = (
    MarketRow,
    MarketExternalIdRow,
    MarketRuleRow,
    MarketMatchLinkRow,
    MarketObservationRow,
    PredictionSnapshotRow,
    DecisionObservationRow,
    PaperOrderIntentRow,
    PaperFillRow,
    PaperPositionRow,
    PaperTrackResultRow,
    MarketResolutionRow,
)


def _unique_column_sets(table) -> set[tuple[str, ...]]:
    return {
        tuple(sorted(column.name for column in constraint.columns))
        for constraint in table.constraints
        if constraint.__class__.__name__ == "UniqueConstraint"
    }


def test_all_twelve_p3_tables_exist_with_exact_names():
    assert P3_TABLE_NAMES <= set(Base.metadata.tables)
    for row_model in P3_ROW_MODELS:
        assert row_model.__tablename__ in P3_TABLE_NAMES


def test_every_p3_timestamp_column_is_timezone_aware():
    for table_name in P3_TABLE_NAMES:
        table = Base.metadata.tables[table_name]
        for column in table.columns:
            column_type = column.type.__class__.__name__
            if column_type == "DateTime":
                assert column.type.timezone, (
                    f"{table_name}.{column.name} must be timestamptz"
                )


def test_evidence_and_payload_columns_are_jsonb():
    jsonb_columns = {
        ("market_match_links", "evidence"),
        ("market_observations", "payload"),
        ("prediction_snapshots", "payload"),
        ("decision_observations", "payload"),
        ("paper_order_intents", "quote"),
        ("market_resolutions", "payouts"),
    }
    for table_name, column_name in jsonb_columns:
        column = Base.metadata.tables[table_name].columns[column_name]
        assert column.type.__class__.__name__ == "JSONB", (
            f"{table_name}.{column_name} must be JSONB"
        )
        assert not column.nullable, f"{table_name}.{column_name} must be NOT NULL"


def test_provider_identifiers_are_confined_to_the_external_mapping_table():
    forbidden_fragments = ("condition", "token", "external", "provider_event")
    for table_name in P3_TABLE_NAMES - {"market_external_ids"}:
        table = Base.metadata.tables[table_name]
        for column in table.columns:
            lowered = column.name.lower()
            for fragment in forbidden_fragments:
                assert fragment not in lowered, (
                    f"{table_name}.{column.name} leaks provider identity "
                    "outside market_external_ids"
                )
    mapping = Base.metadata.tables["market_external_ids"]
    for required in ("provider_event_id", "condition_id", "token_a_id", "token_b_id"):
        assert required in mapping.columns


def test_unique_constraints_enforce_one_shot_ledger_and_single_mappings():
    assert _unique_column_sets(Base.metadata.tables["market_external_ids"]) >= {
        ("market_id",),
        ("condition_id", "provider"),
    }
    assert _unique_column_sets(Base.metadata.tables["market_rules"]) >= {
        ("market_id", "rules_hash"),
        ("market_id", "version"),
    }
    assert _unique_column_sets(Base.metadata.tables["market_match_links"]) >= {
        ("market_id",),
    }
    assert _unique_column_sets(Base.metadata.tables["decision_observations"]) >= {
        ("match_id", "observation_version"),
    }
    assert _unique_column_sets(Base.metadata.tables["prediction_snapshots"]) >= {
        ("input_state_version", "match_id", "model_version"),
    }
    assert _unique_column_sets(Base.metadata.tables["paper_order_intents"]) >= {
        ("idempotency_key",),
        ("match_id", "side"),
    }
    assert _unique_column_sets(Base.metadata.tables["paper_fills"]) >= {("intent_id",)}
    assert _unique_column_sets(Base.metadata.tables["paper_positions"]) >= {
        ("match_id",),
    }
    assert _unique_column_sets(Base.metadata.tables["paper_track_results"]) >= {
        ("position_id", "track"),
    }


def test_exactly_one_active_link_per_match_via_partial_unique_index():
    indexes: set[Index] = set(MarketMatchLinkRow.__table__.indexes)
    active_indexes = [
        index
        for index in indexes
        if index.unique and [column.name for column in index.columns] == ["match_id"]
    ]
    assert len(active_indexes) == 1
    where = active_indexes[0].dialect_kwargs.get("postgresql_where")
    assert where is not None and "active" in str(where)


def test_foreign_keys_connect_the_ledger():
    def fk_target(table_name: str, column_name: str) -> str | None:
        column = Base.metadata.tables[table_name].columns[column_name]
        return next(iter(column.foreign_keys), None) and str(
            next(iter(column.foreign_keys)).target_fullname
        )

    assert fk_target("market_external_ids", "market_id") == "markets.id"
    assert fk_target("market_rules", "market_id") == "markets.id"
    assert fk_target("market_match_links", "market_id") == "markets.id"
    assert fk_target("market_observations", "market_id") == "markets.id"
    assert fk_target("paper_order_intents", "market_id") == "markets.id"
    assert fk_target("paper_order_intents", "match_id") == "matches.id"
    assert fk_target("paper_fills", "intent_id") == "paper_order_intents.id"
    assert fk_target("paper_positions", "match_id") == "matches.id"
    assert fk_target("paper_track_results", "position_id") == "paper_positions.id"
    assert fk_target("market_resolutions", "market_id") == "markets.id"
    assert fk_target("decision_observations", "market_id") == "markets.id"


def test_market_resolution_uses_market_as_primary_key():
    table = Base.metadata.tables["market_resolutions"]
    primary_key_columns = [column.name for column in table.primary_key.columns]
    assert primary_key_columns == ["market_id"]
