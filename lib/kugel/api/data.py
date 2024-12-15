"""
Decorators and implementation support for user-defined tables and resources.
"""

from kugel.impl.registry import add_domain, add_table


def domain(name: str):
    def wrap(cls):
        add_domain(name, cls)
        return cls
    return wrap


def table(**kwargs):
    def wrap(cls):
        add_table(cls, **kwargs)
        return cls
    return wrap