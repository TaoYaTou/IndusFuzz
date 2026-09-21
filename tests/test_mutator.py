import pytest
import importlib

_PROTO_NAMES = [
    "modbus",
    "s7comm",
    "dnp3",
    "iec104",
    "iec61850",
    "enip",
    "opcua",
]


def _load_mutator(name):
    mod = importlib.import_module(f"src.protocols.{name}.mutator")
    return getattr(mod, "mutate_payload")


@pytest.mark.parametrize("proto", _PROTO_NAMES)
class TestMutatePayload:
    def test_none_input_returns_none(self, proto):
        fn = _load_mutator(proto)
        assert fn(None) is None

    def test_empty_bytes_returns_input(self, proto):
        fn = _load_mutator(proto)
        result = fn(b"")
        assert result == b""

    def test_short_payload_passthrough(self, proto):
        fn = _load_mutator(proto)
        short = bytes([0x01, 0x02, 0x03])
        result = fn(short)
        assert isinstance(result, (bytes, bytearray))

    def test_normal_payload_produces_bytes(self, proto, sample_modbus_payload):
        fn = _load_mutator(proto)
        result = fn(sample_modbus_payload)
        assert isinstance(result, (bytes, bytearray))
        assert len(result) == len(sample_modbus_payload)

    def test_mutate_is_deterministic_with_seed(self, proto, sample_modbus_payload):
        # modbus exposes seed_mutator; the others use module-level RNG
        import src.protocols.modbus.mutator as mb

        mb.seed_mutator(42)
        r1 = mb.mutate_payload(sample_modbus_payload)
        mb.seed_mutator(42)
        r2 = mb.mutate_payload(sample_modbus_payload)
        assert bytes(r1) == bytes(r2)

    def test_mutator_does_not_crash(self, proto, sample_modbus_payload):
        """所有 7 协议 mutator 至少返回一个 bytes 且长度不变 — 核心契约。"""
        fn = _load_mutator(proto)
        result = fn(sample_modbus_payload)
        assert isinstance(result, (bytes, bytearray)), f"{proto}: mutator 必须返回 bytes/bytearray"
        assert len(result) == len(
            sample_modbus_payload
        ), f"{proto}: 长度应与输入一致 ({len(result)} != {len(sample_modbus_payload)})"

    def test_large_payload_handled(self, proto):
        fn = _load_mutator(proto)
        large = bytes(range(256)) * 4  # 1024 bytes
        result = fn(large)
        assert isinstance(result, (bytes, bytearray))
        assert len(result) == len(large)
