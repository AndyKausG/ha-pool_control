"""Diagnostics support for Pool Control."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import PoolConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PoolConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    decision = coordinator.data
    return {
        "options": dict(entry.options),
        "state": coordinator.state.to_dict(),
        "decision": asdict(decision) if decision else None,
        "problems": coordinator.diagnostics_problems(),
        "snapshot": asdict(coordinator.snapshot()),
    }
