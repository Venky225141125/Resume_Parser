from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def taxonomy_dir() -> Path:
    return repo_root() / "taxonomy"
