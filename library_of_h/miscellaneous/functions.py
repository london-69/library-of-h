import bisect
import datetime
import string

_UNPRINTABLES = "".join(chr(c) for c in range(128) if chr(c) not in string.printable)
_INVALID_PATHNAME_CHARS = "".join((_UNPRINTABLES, ':*?"<>|\t\n\r\x0b\x0c'))

_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB")
_SIZES = tuple(1024 ** i for i, _ in enumerate(_UNITS))


def utc_to_local(utc_dt: datetime.datetime) -> datetime.datetime:
    """
    Converts UTC time to local time.

    Parameters
    -----------
        utc_dt (datetime.datetime): Date time in UTC.

    Returns:
        datetime.datetime: Date time in local time.
    """
    return utc_dt.replace(tzinfo=datetime.timezone.utc).astimezone(tz=None)


def get_value_and_unit_from_Bytes(Bytes: int, round_to: int = 2) -> tuple[int, str]:
    """
    Converts number of Bytes to appropriate higher unit. One unit is 1024 of the
    smaller unit:
        1024 Bytes -> 1 KiB
        1024 KiB -> 1 MiB
        1024 MiB -> 1 GiB
        1024 GiB -> 1 TiB
        ...

    Parameters
    -----------
        Bytes (int):
            Number of Bytes.
        round_to (int, optional):
            Maximum number of numbers after the decimal point. Defaults to 2.

    Returns
    --------
        tuple[
            (int): Value of Bytes converted to an appropriate higher unit.
            (str): Unit of value.
        ]
    """
    i = max(bisect.bisect(_SIZES, Bytes) - 1, 0)
    unit = _UNITS[i]
    size = round(Bytes / _SIZES[i], round_to)

    return size, unit


def validate_pathname(pathname: str) -> str:
    """
    Replaces invalid characters in a pathname with `_`.

    Parameters
    -----------
        pathname (str):
            Pathname to be validated.

    Returns
    --------
        str: Validated pathname.
    """
    new_pathname = ""
    for char in pathname:
        if char in _INVALID_PATHNAME_CHARS:
            new_pathname = "".join((new_pathname, "-"))
        else:
            new_pathname = "".join((new_pathname, char))

    return new_pathname
