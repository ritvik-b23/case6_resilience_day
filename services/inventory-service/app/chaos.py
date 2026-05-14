import asyncio
import logging
import random

logger = logging.getLogger(__name__)

ALLOWED_MODES = {"normal", "slow", "error", "flaky", "unavailable"}

_current_mode: str = "normal"


def get_mode() -> str:
    return _current_mode


def set_mode(mode: str) -> None:
    global _current_mode
    if mode not in ALLOWED_MODES:
        raise ValueError(f"Invalid chaos mode: {mode}. Allowed: {ALLOWED_MODES}")
    _current_mode = mode
    logger.info("chaos_mode_changed", extra={"mode": mode})


async def apply_chaos() -> None:
    """Apply current chaos behaviour. Raises or sleeps as configured."""
    mode = _current_mode
    if mode == "slow":
        logger.info("chaos_slow_mode_sleep")
        await asyncio.sleep(3)
    elif mode == "error":
        logger.info("chaos_error_mode_500")
        raise ChaosError("Chaos error mode active")
    elif mode == "flaky":
        if random.random() < 0.5:
            logger.info("chaos_flaky_mode_fail")
            raise ChaosError("Chaos flaky mode: random failure")
        logger.info("chaos_flaky_mode_pass")
    elif mode == "unavailable":
        logger.info("chaos_unavailable_mode")
        raise ChaosUnavailableError("Inventory unavailable")
    # normal: do nothing


class ChaosError(Exception):
    """Signals that a 500 should be returned."""


class ChaosUnavailableError(Exception):
    """Signals that inventory is not available (still 200 but unavailable)."""
