"""Standard thresholds. Calm and stern move them in balance.py."""

# A move smaller than this share of the prior reading stays off the alert list.
MATERIAL_PERCENT = 10

# Walked-away counts under this are ordinary noise.
LOST_PRICE_MIN = 5

# Turned away at or above this is a critical shelf, not a moderate one.
STOCKOUT_CRITICAL = 6
