"""Single versioned name normalization and deterministic alias derivation.

Every repository write and resolver query must use `normalize_player_name`;
no second normalizer may appear in service or frontend code.
"""

import re
import unicodedata

from app.players.models import (
    DirectoryPlayer,
    PlayerAlias,
    PlayerAliasKind,
    PlayerAliasSource,
)

NORMALIZATION_VERSION = "player-name-v1"

_PUNCTUATION_TO_SPACE = re.compile(r"[.'’´`˙_\-–—/\\,;:!?(){}\[\]\"“”+*=<>|~^]+")
_CJK_SEPARATORS = re.compile(r"[\s·.・\-_]+")
_COMPOSITE_TOKENS = (" vs ", "&", "/")


def _has_cjk(text: str) -> bool:
    """True when any character sits in CJK ideograph or CJK punctuation blocks."""
    return any(
        0x3000 <= ord(char) <= 0x303F
        or ord(char) == 0x30FB
        or 0x3400 <= ord(char) <= 0x4DBF
        or 0x4E00 <= ord(char) <= 0x9FFF
        or 0xF900 <= ord(char) <= 0xFAFF
        for char in text
    )


def normalize_player_name(value: str) -> str:
    """NFKC → casefold → strip Latin accents → collapse punctuation/spacing.

    CJK names drop separators and whitespace entirely; Latin names turn
    punctuation into single spaces.
    """
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold()
    decomposed = unicodedata.normalize("NFD", text)
    text = "".join(char for char in decomposed if unicodedata.category(char) != "Mn")
    if _has_cjk(text):
        text = _CJK_SEPARATORS.sub("", text)
    else:
        text = _PUNCTUATION_TO_SPACE.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
    return unicodedata.normalize("NFC", text)


def _is_composite(name: str) -> bool:
    lowered = name.casefold()
    return any(token in lowered for token in _COMPOSITE_TOKENS)


def derive_english_aliases(
    player: DirectoryPlayer, provider_names: tuple[str, ...] = ()
) -> tuple[PlayerAlias, ...]:
    """Deterministic aliases for one directory player.

    Surname/reordered/abbreviated forms are derived only when tokenization is
    unambiguous; composite (doubles-style) names are excluded entirely. The
    original accented display spelling is preserved while the normalized form
    is unaccented.
    """
    name = player.player.name or ""
    if not name.strip() or _is_composite(name):
        return ()

    aliases: list[PlayerAlias] = []
    seen: set[tuple[PlayerAliasKind, str]] = set()

    def add(kind: PlayerAliasKind, display: str, source: PlayerAliasSource) -> None:
        normalized = normalize_player_name(display)
        if not normalized:
            return
        key = (kind, normalized)
        if key in seen:
            return
        seen.add(key)
        aliases.append(
            PlayerAlias(
                player_id=player.player.id,
                locale="en",
                alias=display.strip(),
                normalized_alias=normalized,
                kind=kind,
                source=source,
            )
        )

    add(PlayerAliasKind.FULL, name, PlayerAliasSource.DERIVED)

    tokens = name.split()
    if len(tokens) >= 2 and all(re.fullmatch(r"[\w.-]+", token) for token in tokens):
        first, last = tokens[0], tokens[-1]
        add(PlayerAliasKind.SURNAME, last, PlayerAliasSource.DERIVED)
        add(PlayerAliasKind.REORDERED, f"{last} {first}", PlayerAliasSource.DERIVED)
        initial = first[0]
        add(PlayerAliasKind.ABBREVIATED, f"{initial}. {last}", PlayerAliasSource.DERIVED)

    for provider_name in provider_names:
        if provider_name.strip():
            add(PlayerAliasKind.PROVIDER, provider_name, PlayerAliasSource.PROVIDER)

    return tuple(aliases)
