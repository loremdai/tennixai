"""Single mapping from API-Tennis `event_type_type` to canonical facets.

Rules stay deliberately broad (spec §5.1): recognized tour families map to
their tier; everything else becomes `other`/`unknown`. Exact ATP 250/500/1000
or Grand Slam grades are never inferred from names.
"""

from app.domain import CircuitTier, Discipline, Gender


def classify_event_type(event_type: str | None) -> tuple[CircuitTier, Gender, Discipline]:
    text = (event_type or "").casefold()

    if "atp" in text:
        circuit = CircuitTier.ATP
    elif "wta" in text:
        circuit = CircuitTier.WTA
    elif "challenger" in text:
        circuit = CircuitTier.CHALLENGER
    elif "itf" in text:
        circuit = CircuitTier.ITF
    else:
        circuit = CircuitTier.OTHER

    if "mixed" in text or " mix" in text or text.endswith("mix"):
        gender = Gender.MIXED
    elif "women" in text or "wta" in text:
        gender = Gender.WOMEN
    elif "men" in text or "atp" in text:
        gender = Gender.MEN
    else:
        # Boys/Girls junior events are not confirmably mapped to men/women.
        gender = Gender.UNKNOWN

    if "doubles" in text:
        discipline = Discipline.DOUBLES
    elif "singles" in text:
        discipline = Discipline.SINGLES
    elif "teams" in text:
        discipline = Discipline.TEAM
    else:
        discipline = Discipline.UNKNOWN

    return circuit, gender, discipline
