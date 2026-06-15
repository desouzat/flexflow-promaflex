"""
FlexFlow - Business Hours SLA Calculator
FF-HARDENING-010: Calculates elapsed time ONLY within configured
business days and business hours (e.g. Mon-Fri, 08:00-18:00).

All datetimes must be timezone-naive or both timezone-aware.
"""

from datetime import datetime, timedelta
from typing import Optional


# Day name to weekday index mapping (Monday=0, Sunday=6)
_DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


def _parse_working_days(working_days_str: str) -> set:
    """
    Parse a working days string into a set of weekday integers (0=Mon, 6=Sun).

    Supported formats:
        "Mon-Fri"       → {0, 1, 2, 3, 4}
        "Mon-Sat"       → {0, 1, 2, 3, 4, 5}
        "Mon,Wed,Fri"   → {0, 2, 4}

    Falls back to Mon-Fri on any parse error.
    """
    raw = (working_days_str or "Mon-Fri").strip()

    if "-" in raw and "," not in raw:
        # Range format: "Mon-Fri"
        parts = [p.strip().lower()[:3] for p in raw.split("-", 1)]
        if len(parts) == 2 and parts[0] in _DAY_MAP and parts[1] in _DAY_MAP:
            start_day = _DAY_MAP[parts[0]]
            end_day = _DAY_MAP[parts[1]]
            if start_day <= end_day:
                return set(range(start_day, end_day + 1))
            # Wraps around (e.g. Fri-Mon) — unusual, fall through to default
    elif "," in raw:
        # Comma-separated list: "Mon,Wed,Fri"
        days = set()
        for token in raw.split(","):
            t = token.strip().lower()[:3]
            if t in _DAY_MAP:
                days.add(_DAY_MAP[t])
        if days:
            return days

    # Default Mon-Fri
    return {0, 1, 2, 3, 4}


def calculate_business_hours(
    start_time: datetime,
    end_time: datetime,
    config: Optional[dict] = None,
) -> float:
    """
    Calculate the number of elapsed business hours between start_time and end_time.

    Only counts time that falls within:
      - Configured working days (default: Mon-Fri)
      - Configured business hours (default: 08:00 – 18:00)

    Args:
        start_time: When the period begins (naive UTC or aware — must match end_time).
        end_time:   When the period ends.
        config:     Dict with optional keys:
                        sla_start_hour   (int, default 8)
                        sla_end_hour     (int, default 18)
                        sla_working_days (str, default "Mon-Fri")
                    Any missing key falls back to its default.

    Returns:
        Float number of business hours elapsed. Never negative.
    """
    if config is None:
        config = {}

    start_hour: int = int(config.get("sla_start_hour", 8))
    end_hour: int   = int(config.get("sla_end_hour", 18))
    working_days = _parse_working_days(str(config.get("sla_working_days", "Mon-Fri")))

    # Guard: degenerate cases
    if end_time <= start_time:
        return 0.0
    if start_hour >= end_hour:
        # Misconfigured — fall back to 8-18
        start_hour, end_hour = 8, 18

    business_minutes_per_day = (end_hour - start_hour) * 60
    total_minutes = 0.0

    # Walk minute-by-minute is too slow for long periods.
    # Instead walk day-by-day and handle partial days at boundaries.

    # Clamp start/end to date boundaries
    current = start_time

    while current < end_time:
        # Check if this is a working day
        if current.weekday() in working_days:
            # Business window for this day
            day_open  = current.replace(hour=start_hour, minute=0, second=0, microsecond=0)
            day_close = current.replace(hour=end_hour,   minute=0, second=0, microsecond=0)

            # Effective overlap with [current, min(end_time, midnight)]
            next_midnight = (current + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            period_end = min(end_time, next_midnight)

            # Intersect [current, period_end] with [day_open, day_close]
            overlap_start = max(current, day_open)
            overlap_end   = min(period_end, day_close)

            if overlap_end > overlap_start:
                total_minutes += (overlap_end - overlap_start).total_seconds() / 60.0

        # Advance to midnight of the next day
        next_day = (current + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        current = next_day

    return round(total_minutes / 60.0, 4)


def get_sla_config_from_db(db, tenant_id) -> dict:
    """
    Fetch all SLA config keys from GlobalConfig for a given tenant.
    Returns a dict with defaults for any missing keys.
    """
    from backend.models import GlobalConfig
    import uuid

    if not isinstance(tenant_id, uuid.UUID):
        tenant_id = uuid.UUID(str(tenant_id))

    SLA_KEYS = [
        "sla_total_hours",
        "sla_area_hours",
        "sla_start_hour",
        "sla_end_hour",
        "sla_working_days",
    ]
    DEFAULTS = {
        "sla_total_hours": 240,
        "sla_area_hours": 24,
        "sla_start_hour": 8,
        "sla_end_hour": 18,
        "sla_working_days": "Mon-Fri",
    }

    rows = db.query(GlobalConfig).filter(
        GlobalConfig.tenant_id == tenant_id,
        GlobalConfig.config_key.in_(SLA_KEYS),
    ).all()

    result = dict(DEFAULTS)
    for row in rows:
        try:
            result[row.config_key] = row.get_typed_value()
        except (ValueError, TypeError):
            pass  # keep default on bad data

    return result
