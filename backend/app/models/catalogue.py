from sqlalchemy import ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Sport(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sports"

    key: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(default=True)


class Competition(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "competitions"
    __table_args__ = (UniqueConstraint("sport_id", "name", name="sport_name"),)

    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    country: Mapped[str | None] = mapped_column(String(80))
    level: Mapped[str | None] = mapped_column(String(40))
    surface: Mapped[str | None] = mapped_column(String(30))
    external_key: Mapped[str | None] = mapped_column(String(120), index=True)


class Team(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "teams"
    __table_args__ = (Index("ix_teams_sport_normalized", "sport_id", "normalized_name"),)

    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    country: Mapped[str | None] = mapped_column(String(80))


class Player(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "players"
    __table_args__ = (Index("ix_players_sport_normalized", "sport_id", "normalized_name"),)

    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(160))
    normalized_name: Mapped[str] = mapped_column(String(160))
    country: Mapped[str | None] = mapped_column(String(80))
    ranking: Mapped[int | None] = mapped_column(Integer)


class ProviderEntity(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "provider_entities"
    __table_args__ = (
        UniqueConstraint("provider", "entity_type", "external_id", name="provider_type_external"),
    )

    provider: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    external_id: Mapped[str] = mapped_column(String(180))
    internal_id: Mapped[str] = mapped_column(String(36), index=True)
    canonical_name: Mapped[str] = mapped_column(String(180))


class EntityAlias(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_type", "normalized_alias", "provider", name="alias_provider"),
    )

    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    internal_id: Mapped[str] = mapped_column(String(36), index=True)
    alias: Mapped[str] = mapped_column(String(180))
    normalized_alias: Mapped[str] = mapped_column(String(180))
    provider: Mapped[str | None] = mapped_column(String(80))
