from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("/data")
    ephemeris_file: str = "de421.bsp"
    request_timeout: float = 15.0
    user_agent: str = "AstroPlanner/0.1 (astrophotography planning tool)"

    model_config = {"env_prefix": "ASTRO_", "case_sensitive": False}

    @property
    def ephemeris_path(self) -> Path:
        return self.data_dir / "ephemeris" / self.ephemeris_file

    @property
    def sites_path(self) -> Path:
        return self.data_dir / "sites" / "sites.json"


settings = Settings()
