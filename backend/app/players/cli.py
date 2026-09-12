"""Explicit local player directory commands.

Usage:
    uv run python -m app.players.cli sync
    uv run python -m app.players.cli status

Output is aggregate counts only: no credentials, no vendor IDs, no payloads.
"""

import argparse
import asyncio
import sys
from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.errors import AppError
from app.persistence.database import Database
from app.persistence.player_directory import PostgresPlayerDirectoryRepository
from app.persistence.repositories import PostgresIdentityRepository
from app.providers.api_tennis import ApiTennisProvider
from app.players.sync import PlayerDirectorySync


async def _run_sync() -> int:
    settings = Settings()
    api_key = settings.api_tennis_api_key
    if api_key is None or not api_key.get_secret_value().strip():
        print("directory sync unavailable: API-Tennis key not configured")
        return 2
    database = Database(settings.database_url)
    client = httpx.AsyncClient(base_url=settings.api_tennis_base_url, timeout=20.0)
    try:
        provider = ApiTennisProvider(
            client=client,
            identities=PostgresIdentityRepository(database),
            api_key=api_key.get_secret_value(),
            now=lambda: datetime.now(timezone.utc),
        )
        repository = PostgresPlayerDirectoryRepository(database)
        sync = PlayerDirectorySync(
            provider, repository, now=lambda: datetime.now(timezone.utc)
        )
        rankings = await sync.sync_rankings()
        aliases = await sync.sync_known_player_aliases()
        print(
            "sync rankings: "
            f"discovered={rankings.discovered} updated={rankings.updated} "
            f"failed={rankings.failed}"
        )
        print(
            "sync aliases: "
            f"inserted={aliases.aliases_inserted} skipped={aliases.skipped}"
        )
        return 1 if rankings.failed else 0
    except AppError as error:
        print(f"directory sync failed: {error.code}")
        return 1
    finally:
        await client.aclose()
        await database.dispose()


async def _run_status() -> int:
    settings = Settings()
    database = Database(settings.database_url)
    try:
        repository = PostgresPlayerDirectoryRepository(database)
        counts = await repository.directory_counts()
        print(
            "directory: "
            f"players={counts['players']} localized={counts['localized']} "
            f"aliases={counts['aliases']} ranked_atp={counts['ranked_atp']} "
            f"ranked_wta={counts['ranked_wta']}"
        )
        return 0
    except AppError as error:
        print(f"directory status failed: {error.code}")
        return 1
    finally:
        await database.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.players.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("sync", help="sync ATP/WTA rankings and derive aliases")
    subparsers.add_parser("status", help="print aggregate directory counts")
    args = parser.parse_args(argv)
    if args.command == "sync":
        return asyncio.run(_run_sync())
    if args.command == "status":
        return asyncio.run(_run_status())
    return 2


if __name__ == "__main__":
    sys.exit(main())
