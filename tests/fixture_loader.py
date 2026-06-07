from pathlib import Path


FIXTURE_DIR = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURE_DIR / name


def require_fixture(name: str) -> Path:
    path = fixture_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing fixture {name}. Put it at {FIXTURE_DIR / name}."
        )
    return path
