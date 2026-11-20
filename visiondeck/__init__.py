"""Player-facing intelligence. Reads what the company can see."""

from open_late.visiondeck.observations import collect_observations, inventory_observations
from open_late.visiondeck.signals import detect, stockout_alerts

__all__ = ["collect_observations", "detect", "inventory_observations", "stockout_alerts"]
