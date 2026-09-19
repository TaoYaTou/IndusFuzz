from src.protocols.registry import register_protocol
from src.protocols.modbus.client import ModbusClient, _FUNC_NAME_MAP

register_protocol("modbus", ModbusClient)

FUNC_NAME_MAP = _FUNC_NAME_MAP
FUNC_CODES = list(_FUNC_NAME_MAP.keys())
ModbusProtocol = ModbusClient

__all__ = ["ModbusClient", "ModbusProtocol", "FUNC_NAME_MAP", "FUNC_CODES"]
