"""Writer doors. This is not a second catalogue.

Every name is the function on essay_writer.server.HANDLERS.
A shell imports these; it does not keep its own copies.
"""

from essay_writer.server import HANDLERS

_BY_NAME: dict[str, object] = {}
for _handler in HANDLERS.values():
    _name = _handler.__name__
    if _name in _BY_NAME:
        raise RuntimeError(f"two doors share the function name {_name}")
    _BY_NAME[_name] = _handler

__all__ = sorted(_BY_NAME)


def __getattr__(name: str) -> object:
    try:
        return _BY_NAME[name]
    except KeyError:
        raise AttributeError(name) from None
