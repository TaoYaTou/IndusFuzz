from src.protocols.registry import register_protocol
from src.protocols.enip.client import ENIPClient, _CIP_SERVICE_NAMES

register_protocol("enip", ENIPClient)

CIP_SERVICE_NAMES = _CIP_SERVICE_NAMES

__all__ = ["ENIPClient", "CIP_SERVICE_NAMES"]
