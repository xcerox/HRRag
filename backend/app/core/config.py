from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # JWT
    secret_key: str = "dev-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_days: int = 7

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "hrrag"
    postgres_user: str = "hrrag"
    postgres_password: str = "hrrag"

    # Embeddings / retrieval
    embedding_dim: int = 768
    ollama_embedding_model: str = "nomic-embed-text"
    n_results: int = 6
    min_similarity: float = 0.45

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:14b"
    ollama_temperature: float = 0.1
    ollama_timeout: float = 120.0

    # Storage
    upload_dir: str = "./storage/uploads"
    max_file_size_mb: int = 50

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()
