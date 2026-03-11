from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

# .env is at the project root (one level above backend/)
_ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    # Gemini API Key (from Vertex AI Studio → Settings → API Keys)
    google_api_key: str = ""

    # GCP Core
    google_cloud_project: str = "the-bird-364803"
    google_cloud_location: str = "us-central1"
    google_application_credentials: str = "./service-account.json"

    @property
    def service_account_path(self) -> str:
        """Absolute path to the service account JSON, resolved relative to backend/."""
        p = Path(self.google_application_credentials)
        if p.is_absolute():
            return str(p)
        return str(Path(__file__).parent / p)

    # Vertex AI Search
    # NOTE: Discovery Engine always uses 'global' location regardless of project region
    vertex_ai_datastore_id: str = "fincampaign-rag-datastore"
    vertex_ai_search_engine_id: str = "fincampaign-search-engine"

    # GCS
    gcs_bucket_name: str = "the-bird-364803-fincampaign-results"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    # Comma-separated origins, e.g.: http://localhost:3000,http://localhost:5173
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse cors_origins string into a list for the CORS middleware."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "Campain"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_ssl: bool = False

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Models (gemini-2.5-flash-lite is available on this project via API key)
    orchestrator_model: str = "gemini-2.5-flash-lite"
    risk_analyst_model: str = "gemini-2.5-flash-lite"
    campaign_model: str = "gemini-2.5-flash-lite"
    compliance_model: str = "gemini-2.5-flash-lite"

    @property
    def datastore_parent(self) -> str:
        """Resource path for document operations. Always uses 'global' location."""
        return (
            f"projects/{self.google_cloud_project}"
            f"/locations/global"
            f"/collections/default_collection"
            f"/dataStores/{self.vertex_ai_datastore_id}"
        )

    @property
    def serving_config(self) -> str:
        """Full resource path for SearchRequest. Always uses 'global' location."""
        return f"{self.datastore_parent}/servingConfigs/default_config"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "case_sensitive": False, "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
