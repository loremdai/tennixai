from app.identity import MemoryIdentityRepository


def test_internal_id_is_stable_in_process_and_reversible() -> None:
    repository = MemoryIdentityRepository()
    first = repository.get_or_create("match", "livetennis", "21131")
    second = repository.get_or_create("match", "livetennis", "21131")

    assert first == second
    assert first.startswith("mat_")
    assert "21131" not in first
    assert repository.external_id("match", "livetennis", first) == "21131"


def test_internal_ids_differ_across_entities_and_providers() -> None:
    repository = MemoryIdentityRepository()
    match_id = repository.get_or_create("match", "livetennis", "100")
    player_id = repository.get_or_create("player", "livetennis", "100")
    other_provider = repository.get_or_create("match", "fake", "100")

    assert match_id.startswith("mat_")
    assert player_id.startswith("ply_")
    assert match_id != other_provider
    assert repository.external_id("match", "livetennis", other_provider) is None


def test_unknown_internal_id_returns_none() -> None:
    repository = MemoryIdentityRepository()

    assert repository.external_id("tournament", "livetennis", "trn_missing") is None


def test_tournament_prefix() -> None:
    repository = MemoryIdentityRepository()
    tournament_id = repository.get_or_create("tournament", "livetennis", "1217")

    assert tournament_id.startswith("trn_")
    assert "1217" not in tournament_id
    assert repository.external_id("tournament", "livetennis", tournament_id) == "1217"
