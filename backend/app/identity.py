from typing import Protocol
from uuid import uuid4


class IdentityRepository(Protocol):
    """Async contract shared by in-memory test repositories and the durable
    PostgreSQL repository (P2). Internal IDs keep the mat_/ply_/trn_ prefixes
    and never contain provider identifiers."""

    async def get_or_create(self, entity: str, provider: str, external_id: str) -> str:
        raise NotImplementedError

    async def external_id(
        self, entity: str, provider: str, internal_id: str
    ) -> str | None:
        raise NotImplementedError


class MemoryIdentityRepository:
    PREFIXES = {"match": "mat", "player": "ply", "tournament": "trn"}

    def __init__(self) -> None:
        self._forward: dict[tuple[str, str, str], str] = {}
        self._reverse: dict[tuple[str, str, str], str] = {}

    async def get_or_create(self, entity: str, provider: str, external_id: str) -> str:
        prefix = self.PREFIXES[entity]
        key = (entity, provider, str(external_id))
        if key not in self._forward:
            internal_id = f"{prefix}_{uuid4().hex}"
            self._forward[key] = internal_id
            self._reverse[(entity, provider, internal_id)] = str(external_id)
        return self._forward[key]

    async def external_id(
        self, entity: str, provider: str, internal_id: str
    ) -> str | None:
        return self._reverse.get((entity, provider, internal_id))
