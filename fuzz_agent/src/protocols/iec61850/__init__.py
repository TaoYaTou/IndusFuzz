from src.protocols.registry import register_protocol
from src.protocols.iec61850.client import IEC61850Client, _PDU_TYPE_NAME_MAP

register_protocol("iec61850", IEC61850Client)

PDU_TYPE_NAME_MAP = _PDU_TYPE_NAME_MAP

__all__ = ["IEC61850Client", "PDU_TYPE_NAME_MAP"]
