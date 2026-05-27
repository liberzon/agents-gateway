def str_to_bool(value: str) -> bool:
    return value.lower() in ("1", "true", "yes", "on")


__all__ = ["str_to_bool"]
