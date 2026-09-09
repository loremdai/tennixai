from pathlib import Path

from app.config import Settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_default_environment_file_is_at_repository_root():
    assert Path(Settings.model_config["env_file"]) == REPOSITORY_ROOT / ".env"


def test_repository_has_one_environment_example():
    assert (REPOSITORY_ROOT / ".env.example").is_file()
    assert not (REPOSITORY_ROOT / "backend/.env.example").exists()
    assert not (REPOSITORY_ROOT / "frontend/.env.example").exists()
