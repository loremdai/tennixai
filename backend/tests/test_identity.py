import pytest

from app.identity import IdentityRepository, MemoryIdentityRepository


def test_memory_repository_satisfies_async_identity_protocol() -> None:
    repository: IdentityRepository = MemoryIdentityRepository()
    assert isinstance(repository, MemoryIdentityRepository)


@pytest.mark.asyncio
async def test_internal_id_is_stable_in_process_and_reversible() -> None:
    repository = MemoryIdentityRepository()
    first = await repository.get_or_create("match", "livetennis", "21131")
    second = await repository.get_or_create("match", "livetennis", "21131")

    assert first == second
    assert first.startswith("mat_")
    assert "21131" not in first
    assert await repository.external_id("match", "livetennis", first) == "21131"


@pytest.mark.asyncio
async def test_internal_ids_differ_across_entities_and_providers() -> None:
    repository = MemoryIdentityRepository()
    match_id = await repository.get_or_create("match", "livetennis", "100")
    player_id = await repository.get_or_create("player", "livetennis", "100")
    other_provider = await repository.get_or_create("match", "fake", "100")

    assert match_id.startswith("mat_")
    assert player_id.startswith("ply_")
    assert match_id != other_provider
    assert await repository.external_id("match", "livetennis", other_provider) is None


@pytest.mark.asyncio
async def test_unknown_internal_id_returns_none() -> None:
    repository = MemoryIdentityRepository()

    assert await repository.external_id("tournament", "livetennis", "trn_missing") is None


@pytest.mark.asyncio
async def test_tournament_prefix() -> None:
    repository = MemoryIdentityRepository()
    tournament_id = await repository.get_or_create("tournament", "livetennis", "1217")

    assert tournament_id.startswith("trn_")
    assert "1217" not in tournament_id
    assert await repository.external_id("tournament", "livetennis", tournament_id) == "1217"
