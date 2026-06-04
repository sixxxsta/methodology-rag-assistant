from __future__ import annotations

from contextvars import ContextVar

_cycle_id_var: ContextVar[int | None] = ContextVar("cycle_id", default=None)


def set_request_cycle_id(cycle_id: int | None) -> object:
    return _cycle_id_var.set(cycle_id)


def reset_request_cycle_id(token: object) -> None:
    _cycle_id_var.reset(token)


def get_request_cycle_id() -> int | None:
    return _cycle_id_var.get()
