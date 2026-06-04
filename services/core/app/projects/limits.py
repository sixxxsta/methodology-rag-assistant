from __future__ import annotations

MAX_TEAM_MEMBERS = 5
MIN_TEAM_MEMBERS_TO_CLAIM = 3


def clamp_team_size(value: int | None, *, default: int = MAX_TEAM_MEMBERS) -> int:
    if value is None:
        return default
    return max(1, min(MAX_TEAM_MEMBERS, int(value)))


def validate_catalog_publish_params(project) -> None:
    """Raise ValueError if project cannot be published to catalog."""
    if project.team_size is None or int(project.team_size) < 1:
        raise ValueError("укажите размер команды (1–5 человек) перед публикацией в каталог")
    if project.max_teams is None or int(project.max_teams) < 1:
        raise ValueError("укажите число команд (max_teams), которые могут взять проект")
    clamp_team_size(project.team_size)
