"""Hero structured JSONL logging.

Usage:
    from hero.logging import get_logger

    logger = get_logger("spawn")
    logger.info("Spawned soldier", sandbox="sook-pro", task_id="abc123")
    logger.error("Spawn failed", sandbox="sook-pro", error="timeout")
"""

from hero.logging.handler import Logger as _Logger

_loggers: dict[str, _Logger] = {}


def get_logger(name: str) -> _Logger:
    """Get or create a named logger instance.

    Args:
        name: Logger namespace (typically the module name).

    Returns:
        A Logger instance that writes structured JSONL to ~/.hero/logs/hero.jsonl.
    """
    if name not in _loggers:
        _loggers[name] = _Logger(name)
    return _loggers[name]


__all__ = ["get_logger"]
