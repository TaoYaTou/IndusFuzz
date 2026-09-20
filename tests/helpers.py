"""Shared test helpers — conftest and test files both import from here.

Kept tiny on purpose: only the cross-cutting isolation primitives that every
test file may need. No fixtures (those live in conftest.py).
"""

import sys

_BUILTIN_PROTOCOL_MODS = [
    "src.protocols.modbus",
    "src.protocols.s7comm",
    "src.protocols.dnp3",
    "src.protocols.iec104",
    "src.protocols.iec61850",
    "src.protocols.enip",
    "src.protocols.opcua",
]


def reset_and_reload_all():
    """Clear registry, evict all built-in protocol modules from sys.modules,
    then call auto_load_builtin so every __init__.py re-runs register_protocol().

    This is the only reliable way to get a fully-populated registry inside
    a fixture — import caching prevents register_protocol from firing a
    second time unless we pop the modules first.
    """
    from src.protocols import registry as _r

    _r._PROTOCOLS.clear()
    for mod in _BUILTIN_PROTOCOL_MODS:
        sys.modules.pop(mod, None)
    _r.auto_load_builtin()
    return _r
