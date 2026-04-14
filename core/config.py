"""Config loading and light validation helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import toml as tomllib  # type: ignore

from .errors import ConfigError


def load_toml_config(config_path: str | Path) -> dict:
    """Load a TOML config file into a dictionary."""
    path = Path(config_path)
    mode = "rb" if tomllib.__name__ == "tomllib" else "r"
    with open(path, mode) as handle:
        return tomllib.load(handle)


def require_nested(config: dict, dotted_keys: Iterable[str], *, module_name: str) -> None:
    """Validate that a config contains required dotted keys."""
    missing: list[str] = []
    for dotted_key in dotted_keys:
        current = config
        for part in dotted_key.split("."):
            if not isinstance(current, dict) or part not in current:
                missing.append(dotted_key)
                break
            current = current[part]

    if missing:
        missing_text = ", ".join(sorted(missing))
        raise ConfigError(f"{module_name} config missing required keys: {missing_text}")
