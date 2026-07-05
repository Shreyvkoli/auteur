import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_env: str = "development"
    app_secret_key: str
    frontend_url: str = "http://localhost:3000"
    dev_api_url: str = "http://localhost:8000"

    @property
    def dev_mode(self) -> bool:
        """Single source of truth for dev mode across all services."""
        return self.app_env == "development"

    @property
    def dev_storage_path(self) -> str:
        """Path to local dev_uploads directory, derived from backend/."""
        return os.path.join(os.path.dirname(os.path.dirname(__file__)), "dev_uploads")

    @property
    def openai_configured(self) -> bool:
        """Check if OpenAI API key is actually configured (not a placeholder)."""
        return bool(self.openai_api_key) and not self.openai_api_key.startswith("sk-your-")

    @property
    def cloudinary_configured(self) -> bool:
        """Check if Cloudinary is actually configured (not a placeholder)."""
        return self.cloudinary_cloud_name not in ("your-cloud-name", "")

    @property
    def assets_base_url(self) -> str:
        """Base URL for meme sounds, music tracks, and other static assets."""
        if self.dev_mode:
            return f"{self.dev_api_url}/api/assets"
        return f"https://res.cloudinary.com/{self.cloudinary_cloud_name}/video/upload"

    # Supabase (auth + DB)
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str

    # OpenAI — GPT-4o + Whisper (or Ollama for local dev)
    openai_api_key: str
    openai_base_url: Optional[str] = None  # e.g. http://localhost:11434/v1 for Ollama
    openai_model: str = "gpt-4o"  # model name (llama3.2, etc. for local LLMs)

    # Cloudinary — primary video storage
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    # Redis — job queue
    redis_url: str = "redis://localhost:6379"

    # Cloudflare R2 — asset storage
    r2_account_id: Optional[str] = None
    r2_access_key_id: Optional[str] = None
    r2_secret_access_key: Optional[str] = None
    r2_bucket_name: str = "auteur-vault"
    r2_public_url: Optional[str] = None

    # Payments
    razorpay_key_id: Optional[str] = None
    razorpay_key_secret: Optional[str] = None
    razorpay_webhook_secret: Optional[str] = None
    stripe_secret_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None
    stripe_publishable_key: Optional[str] = None

    # Video processing
    max_video_size_mb: int = 2048
    max_video_duration_seconds: int = 3600
    ffmpeg_threads: int = 4
    max_ffmpeg_processes: int = 4
    compress_threshold_mb: int = 90  # compress if > 90MB before upload
    thumb_interval: int = 2
    thumb_width: int = 120
    thumb_height: int = 68

    # Quality engine
    quality_threshold: float = 6.0     # min avg score to pass
    max_regeneration_attempts: int = 2 # how many times to retry bad plans

    # Edit state
    max_chunk_duration_seconds: int = 300  # vlog chunk size (5 min)
    segment_cache_ttl_hours: int = 24

    # Preview rendering
    preview_resolution: str = "480p"
    preview_preset: str = "ultrafast"
    preview_crf: int = 28
    preview_max_seconds: int = 60  # max preview duration

    # Intelligence layer
    max_self_critique_passes: int = 2
    story_confidence_threshold: float = 6.0
    vlog_chunk_overlap_seconds: float = 7.5
    max_history_versions: int = 50

    # Queue
    job_timeout_seconds: int = 600

    # Dev auth (overridable for local dev)
    dev_user_id: str = "dev-user-001"
    dev_user_email: str = "dev@auteur.local"
    dev_user_name: str = "Dev User"
    dev_user_plan: str = "pro"

    # Metrics
    metrics_retention_days: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()