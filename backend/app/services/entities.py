import re
import unicodedata

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EntityAlias, Player, ProviderEntity, Sport, Team


def normalize_entity_name(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", ascii_name.lower()).strip()


async def resolve_participant(
    session: AsyncSession,
    *,
    sport: Sport,
    provider: str,
    external_id: str,
    name: str,
) -> str:
    entity_type = "team" if sport.key == "football" else "player"
    mapping = await session.scalar(
        select(ProviderEntity).where(
            ProviderEntity.provider == provider,
            ProviderEntity.entity_type == entity_type,
            ProviderEntity.external_id == external_id,
        )
    )
    if mapping is not None:
        return mapping.internal_id

    normalized = normalize_entity_name(name)
    aliases = set(
        await session.scalars(
            select(EntityAlias.internal_id).where(
                EntityAlias.entity_type == entity_type, EntityAlias.normalized_alias == normalized
            )
        )
    )
    entity: Team | Player | None
    if entity_type == "team":
        entity = await session.scalar(
            select(Team).where(
                Team.sport_id == sport.id,
                Team.normalized_name == normalized,
            )
        )
        if entity is None and len(aliases) == 1:
            entity = await session.scalar(
                select(Team).where(Team.id == next(iter(aliases)), Team.sport_id == sport.id)
            )
        if entity is None:
            entity = Team(sport_id=sport.id, name=name, normalized_name=normalized)
            session.add(entity)
    else:
        entity = await session.scalar(
            select(Player).where(
                Player.sport_id == sport.id,
                Player.normalized_name == normalized,
            )
        )
        if entity is None:
            entity = Player(sport_id=sport.id, name=name, normalized_name=normalized)
            session.add(entity)
    await session.flush()

    session.add(
        ProviderEntity(
            provider=provider,
            entity_type=entity_type,
            external_id=external_id,
            internal_id=entity.id,
            canonical_name=entity.name,
        )
    )
    alias = await session.scalar(
        select(EntityAlias).where(
            EntityAlias.entity_type == entity_type,
            EntityAlias.normalized_alias == normalized,
            EntityAlias.provider == provider,
        )
    )
    if alias is None:
        session.add(
            EntityAlias(
                entity_type=entity_type,
                internal_id=entity.id,
                alias=name,
                normalized_alias=normalized,
                provider=provider,
            )
        )
    return entity.id
