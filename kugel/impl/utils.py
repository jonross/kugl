

from kugel.util import warn


def set_parent(item: dict, parent: dict):
    item["__parent"] = parent


def parent(item: dict):
    parent = item.get("__parent")
    if parent is None:
        warn("Item parent is missing")
    return parent
