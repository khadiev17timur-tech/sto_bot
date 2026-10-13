"""Валидация пользовательского ввода."""
import re

PHONE_RE = re.compile(r"^(\+7|8|7)?[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}$")


def is_valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone.strip()))


def normalize_phone(phone: str) -> str:
    """Приводит номер к виду +7XXXXXXXXXX."""
    digits = re.sub(r"\D", "", phone.strip())
    if len(digits) == 11 and digits[0] in ("7", "8"):
        digits = "7" + digits[1:]
    elif len(digits) == 10:
        digits = "7" + digits
    return "+" + digits


def is_valid_name(name: str) -> bool:
    name = name.strip()
    return 2 <= len(name) <= 50 and not name.isdigit() and not name.startswith("/")


def is_valid_free_text(value: str, min_len: int = 1, max_len: int = 100) -> bool:
    value = value.strip()
    return min_len <= len(value) <= max_len and not value.startswith("/")


TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


def is_valid_time(time_str: str) -> bool:
    return bool(TIME_RE.match(time_str.strip()))
