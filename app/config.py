from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./data/trials.db"
    ctgov_base_url: str = "https://clinicaltrials.gov/api/v2"
    ctgov_page_size: int = 1000
    harvest_delay: float = 1.3
    # Scheduler: hourly incremental, daily full sweep
    hourly_interval: int = 3600  # seconds between incremental harvests
    daily_interval: int = 86400  # seconds between full-sweep harvests
    # Overlap buffers to avoid missing trials at boundaries
    hourly_lookback_hours: int = 2  # fetch 2h back on hourly runs
    daily_lookback_hours: int = 48  # fetch 48h back on daily runs

    model_config = {"env_prefix": "CT_"}


settings = Settings()
