import pytest
from src.protocols import registry as _reg

from helpers import reset_and_reload_all, _BUILTIN_PROTOCOL_MODS


class _FakeProto:
    pass


class TestRegisterManualOps:
    """register_protocol / get_protocol / list_protocols manual operations."""

    def test_register_adds(self):
        _reg._PROTOCOLS.clear()
        _reg.register_protocol("fake", _FakeProto)
        assert "fake" in _reg._PROTOCOLS

    def test_register_duplicate_overwrites(self):
        _reg._PROTOCOLS.clear()
        _reg.register_protocol("dup", _FakeProto)

        class _FakeProto2:
            pass

        _reg.register_protocol("dup", _FakeProto2)
        assert _reg._PROTOCOLS["dup"] is _FakeProto2

    def test_get_protocol_returns_class(self):
        _reg._PROTOCOLS.clear()
        _reg.register_protocol("grab", _FakeProto)
        assert _reg.get_protocol("grab") is _FakeProto

    def test_get_protocol_missing_raises(self):
        _reg._PROTOCOLS.clear()
        with pytest.raises(KeyError):
            _reg.get_protocol("definitely_not_registered_xyz")

    def test_list_protocols_empty(self):
        _reg._PROTOCOLS.clear()
        assert _reg.list_protocols() == []

    def test_list_protocols_multiple(self):
        _reg._PROTOCOLS.clear()
        _reg.register_protocol("a", _FakeProto)
        _reg.register_protocol("b", _FakeProto)
        names = _reg.list_protocols()
        assert "a" in names
        assert "b" in names
        assert len(names) == 2


class TestAutoLoadBuiltins:
    """auto_load_builtin + protocol accessor — uses fresh_registry fixture."""

    _EXPECTED = {m.rsplit(".", 1)[-1] for m in _BUILTIN_PROTOCOL_MODS}

    def test_reload_registers_all_builtins(self, fresh_registry):
        loaded = set(_reg.list_protocols())
        assert self._EXPECTED.issubset(loaded)

    def test_reload_then_get(self, fresh_registry):
        for name in ("modbus", "s7comm", "opcua"):
            cls = _reg.get_protocol(name)
            assert cls is not None, f"protocol {name} not registered"
            assert hasattr(cls, "run_fuzz"), f"{name} class missing run_fuzz method"

    def test_reload_idempotent(self, fresh_registry):
        names1 = set(_reg.list_protocols())
        reset_and_reload_all()
        names2 = set(_reg.list_protocols())
        assert names1 == names2
        assert len(names1) >= 7
