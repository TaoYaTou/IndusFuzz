from src.protocols.registry import register_protocol
from src.protocols.dnp3.client import DNP3Client, _FUNC_NAME_MAP

register_protocol("dnp3", DNP3Client)

FUNC_NAME_MAP = _FUNC_NAME_MAP

__all__ = ["DNP3Client", "FUNC_NAME_MAP"]
