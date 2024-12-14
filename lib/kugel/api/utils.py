
import arrow

from kugel.model import Age


def parse_age(age: str) -> int:
    return Age(age).value


def to_age(seconds: int) -> str:
    return Age(seconds).render()


def parse_utc(utc_str: str) -> int:
    return arrow.get(utc_str).int_timestamp


def to_utc(epoch: int) -> str:
    return arrow.get(epoch).to('utc').format('YYYY-MM-DDTHH:mm:ss') + 'Z'