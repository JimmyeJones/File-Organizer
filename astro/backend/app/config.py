from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    data_dir: Path = Path("/data")
    # Ephemeris lives inside the image (downloaded at build time).
    # Override with ASTRO_EPHEMERIS_DIR if you want to supply your own file.
    ephemeris_dir: Path = Path("/ephemeris")
    ephemeris_file: str = "de421.bsp"
    request_timeout: float = 15.0
    user_agent: str = "AstroPlanner/0.1 (astrophotography planning tool)"

    model_config = {"env_prefix": "ASTRO_", "case_sensitive": False}

    @property
    def ephemeris_path(self) -> Path:
        return self.ephemeris_dir / self.ephemeris_file

    @property
    def sites_path(self) -> Path:
        return self.data_dir / "sites" / "sites.json"


settings = Settings()
