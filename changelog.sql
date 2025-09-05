-- liquibase formatted sql

-- changeset bot:init-player-cards-table
CREATE TABLE player_cards (
    discord_id TEXT PRIMARY KEY,
    cards JSONB NOT NULL
);
