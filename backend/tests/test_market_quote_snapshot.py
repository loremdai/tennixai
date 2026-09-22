"""Latest-quote projection schema and canonical quote display tests (T85)."""

from app.persistence.models import Base, MarketQuoteSnapshotRow


def test_market_quote_snapshots_table_shape():
    table = Base.metadata.tables["market_quote_snapshots"]
    assert MarketQuoteSnapshotRow.__tablename__ == "market_quote_snapshots"
    assert [column.name for column in table.primary_key.columns] == ["market_id"]
    for name in (
        "source",
        "quote_state",
        "book_hash",
        "as_of",
        "expires_at",
        "payload",
        "updated_at",
    ):
        assert name in table.columns
    # Display statistics are stored explicitly so a missing side is a NULL
    # column, never a fabricated zero.
    for name in (
        "outcome_a_bid",
        "outcome_a_ask",
        "outcome_b_bid",
        "outcome_b_ask",
        "spread",
        "depth_usd",
    ):
        assert name in table.columns
        assert table.columns[name].nullable
    for name in ("as_of", "expires_at", "updated_at"):
        assert table.columns[name].type.timezone
    # Provider identity never enters the projection.
    for name in ("token", "condition_id", "provider_event_id"):
        assert all(name not in column.name for column in table.columns)