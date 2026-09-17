from src.protocols.registry import register_protocol
from src.protocols.s7comm.client import S7CommClient

register_protocol("s7comm", S7CommClient)

__all__ = ["S7CommClient"]