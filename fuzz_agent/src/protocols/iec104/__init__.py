from src.protocols.registry import register_protocol
from src.protocols.iec104.client import IEC104Client, _FUNC_NAME_MAP

register_protocol("iec104", IEC104Client)

FUNC_NAME_MAP = _FUNC_NAME_MAP

__all__ = ["IEC104Client", "FUNC_NAME_MAP"]
