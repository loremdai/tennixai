"""Name normalization and deterministic English alias derivation tests."""

import pytest

from app.domain import Gender, Player
from app.players.models import (
    DirectoryPlayer,
    PlayerAliasKind,
    PlayerAliasSource,
)
from app.players.normalization import (
    NORMALIZATION_VERSION,
    derive_english_aliases,
    normalize_player_name,
)


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        (" B.  Shelton ", "b shelton"),
        ("BEN-SHELTON", "ben shelton"),
        ("Lehečka, Jiří", "lehecka jiri"),
        ("本·谢尔顿", "本谢尔顿"),
        ("郑 钦文", "郑钦文"),
    ],
)
def test_normalize_player_name(raw: str, normalized: str) -> None:
    assert normalize_player_name(raw) == normalized


def test_normalization_version_is_stable() -> None:
    assert NORMALIZATION_VERSION == "player-name-v1"


def _directory(name: str, localized_name: str | None = None) -> DirectoryPlayer:
    return DirectoryPlayer(
        player=Player(id="ply_x", name=name, localized_name=localized_name),
        gender=Gender.MEN,
    )


def test_derive_english_aliases_covers_full_surname_reordered_abbreviated() -> None:
    aliases = derive_english_aliases(_directory("Ben Shelton"), provider_names=("B. Shelton",))
    pairs = {(alias.kind, alias.normalized_alias) for alias in aliases}

    assert (PlayerAliasKind.FULL, "ben shelton") in pairs
    assert (PlayerAliasKind.SURNAME, "shelton") in pairs
    assert (PlayerAliasKind.REORDERED, "shelton ben") in pairs
    assert (PlayerAliasKind.ABBREVIATED, "b shelton") in pairs
    assert (PlayerAliasKind.PROVIDER, "b shelton") in pairs

    for alias in aliases:
        expected = (
            PlayerAliasSource.PROVIDER
            if alias.kind is PlayerAliasKind.PROVIDER
            else PlayerAliasSource.DERIVED
        )
        assert alias.source is expected
        assert alias.locale == "en"

    display = {alias.kind: alias.alias for alias in aliases}
    assert display[PlayerAliasKind.FULL] == "Ben Shelton"


def test_derive_aliases_keep_accented_display_with_unaccented_normalized() -> None:
    aliases = derive_english_aliases(_directory("Lehečka Jiří"))
    full = [alias for alias in aliases if alias.kind is PlayerAliasKind.FULL][0]
    assert full.alias == "Lehečka Jiří"
    assert full.normalized_alias == "lehecka jiri"


@pytest.mark.parametrize("name", ["Anna / Beta", "Anna & Beta", "Anna vs Beta"])
def test_composite_names_are_excluded_from_singles_aliases(name: str) -> None:
    assert derive_english_aliases(_directory(name)) == ()


def test_single_token_names_only_derive_full_alias() -> None:
    aliases = derive_english_aliases(_directory("Xscape"))
    assert {alias.kind for alias in aliases} == {PlayerAliasKind.FULL}


def test_derive_aliases_are_deduplicated() -> None:
    aliases = derive_english_aliases(
        _directory("Ben Shelton"), provider_names=("Ben Shelton", "ben  shelton")
    )
    keys = {(alias.kind, alias.normalized_alias) for alias in aliases}
    assert len(keys) == len(aliases)
