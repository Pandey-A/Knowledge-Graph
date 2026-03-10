from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    neo4j_uri: str = Field(default="bolt://localhost:7687", validation_alias=AliasChoices("NEO4J_URI"))
    neo4j_user: str = Field(
        default="neo4j",
        validation_alias=AliasChoices("NEO4J_USER", "NEO4J_USERNAME"),
    )
    neo4j_password: str = Field(
        default="password123",
        validation_alias=AliasChoices("NEO4J_PASSWORD"),
    )
    neo4j_database: str | None = Field(
        default=None,
        validation_alias=AliasChoices("NEO4J_DATABASE"),
    )

    openai_api_key: str | None = Field(default=None, validation_alias=AliasChoices("OPENAI_API_KEY"))
    embedding_model: str = Field(default="text-embedding-3-small", validation_alias=AliasChoices("EMBEDDING_MODEL"))
    sentence_transformer_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        validation_alias=AliasChoices("SENTENCE_TRANSFORMER_MODEL"),
    )

    pinecone_api_key: str | None = Field(default=None, validation_alias=AliasChoices("PINECONE_API_KEY"))
    pinecone_index: str | None = Field(default=None, validation_alias=AliasChoices("PINECONE_INDEX"))
    app_env: str = Field(default="development", validation_alias=AliasChoices("APP_ENV"))


settings = Settings()