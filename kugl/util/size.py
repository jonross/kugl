import re
from typing import Union

SIZE_RE = re.compile(r"([0-9\.]+)(([KMGTP]i?)?)")
SIZE_MULTIPLIERS = dict(K=10**3, M=10**6, G=10**9, T=10**12,
                        Ki=2**10, Mi=2**20, Gi=2**30, Ti=2**40)


def parse_size(x: Union[str, int, None]):
    """
    Translate a string a la 10K, 5Mb, 3Gi to # of bytes.  Returns an int if the result
    can be represented as an int, else a float.
    """
    if x is None:
        return None
    if isinstance(x, int):
        return x
    m = SIZE_RE.fullmatch(x)
    if m is None:
        raise ValueError(f"Can't translate '{x}' to bytes")
    amount, suffix = m.group(1), m.group(2)
    amount = float(amount) if "." in amount else int(amount)
    if suffix == "":
        return amount
    multiplier = SIZE_MULTIPLIERS.get(suffix)
    if multiplier is None:
        raise ValueError(f"Unknown size suffix in '{x}'")
    return int(amount * multiplier)


def to_size(nbytes: int, iec=False):
    """
    Given a byte count, render it as a string in the most appropriate units, suffixed by KB, MB, GB, etc.
    Larger sizes will use the appropriate unit.  The result may have a maximum of one digit after the
    decimal point.  If iec is True, use IEC binary units (KiB, MiB, etc).
    """
    one_k = 1024 if iec else 1000
    bytes = "i" if iec else ""
    if nbytes < one_k:
        return f"{nbytes}"
    elif nbytes < one_k ** 2:
        size, suffix = nbytes / one_k, "K" + bytes
    elif nbytes < one_k ** 3:
        size, suffix = nbytes / one_k ** 2, "M" + bytes
    elif nbytes < one_k ** 4:
        size, suffix = nbytes / one_k ** 3, "G" + bytes
    else:
        size, suffix = nbytes / one_k ** 4, "T" + bytes
    if size < 10:
        return f"{size:.1f}{suffix}"
    else:
        return f"{round(size)}{suffix}"


def parse_cpu(x: Union[str, float, int, None]) -> float:
    """
    Translate a "number of CPUs" field like "2", "1.5", or "300m" to float.
    """
    if x is None or isinstance(x, float) or isinstance(x, int):
        return x
    if x.endswith("m"):
        return float(x[:-1]) / 1000
    return float(x)
