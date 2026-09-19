from src.protocols.registry import register_protocol
from src.protocols.opcua.client import OPCUAClient, _SERVICE_NAMES

register_protocol("opcua", OPCUAClient)

SERVICE_NAMES = _SERVICE_NAMES

__all__ = ["OPCUAClient", "SERVICE_NAMES"]
