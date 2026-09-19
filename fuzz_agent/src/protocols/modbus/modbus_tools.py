import logging
import socket
import struct

# 仅用 scapy 构造报文（不抓包），抑制 libpcap 缺失等加载警告
logging.getLogger("scapy.loading").setLevel(logging.ERROR)
logging.getLogger("scapy.runtime").setLevel(logging.ERROR)
from scapy.layers.inet import IP, TCP
from scapy.contrib.modbus import (
    ModbusADURequest,
    ModbusPDU01ReadCoilsRequest,
    ModbusPDU02ReadDiscreteInputsRequest,
    ModbusPDU03ReadHoldingRegistersRequest,
    ModbusPDU04ReadInputRegistersRequest,
    ModbusPDU06WriteSingleRegisterRequest,
    ModbusPDU07ReadExceptionStatusRequest,
    ModbusPDU08DiagnosticsRequest,
    ModbusPDU0BGetCommEventCounterRequest,
    ModbusPDU0CGetCommEventLogRequest,
    ModbusPDU11ReportSlaveIdRequest,
    ModbusPDU14ReadFileRecordRequest,
    ModbusPDU15WriteFileRecordRequest,
    ModbusPDU2B0EReadDeviceIdentificationRequest,
)


def _build_pdu_bytes(func_code, **kw):
    start_addr = kw.get("start_addr", 0)
    quantity = kw.get("quantity", 10)
    coil_address = kw.get("coil_address", 0)
    coil_value = kw.get("coil_value", 0)
    register_address = kw.get("register_address", 0)
    register_value = kw.get("register_value", 0)
    mask_register_value = kw.get("mask_register_value", 0)

    if func_code == 0x05:
        return struct.pack(">BHH", 0x05, coil_address, coil_value)
    if func_code == 0x0F:
        qty = max(quantity, 1)
        byte_count = (qty + 7) // 8
        outputs = bytes([0] * byte_count)
        return struct.pack(">BHHB", 0x0F, start_addr, qty, byte_count) + outputs
    if func_code == 0x10:
        qty = max(quantity, 1)
        byte_count = qty * 2
        regs = b"\x00" * byte_count
        return struct.pack(">BHHB", 0x10, start_addr, qty, byte_count) + regs
    if func_code == 0x16:
        return struct.pack(">BHHH", 0x16, register_address, mask_register_value, register_value)
    if func_code == 0x17:
        read_qty = max(kw.get("read_quantity", 10), 1)
        write_qty = max(kw.get("write_quantity", 10), 1)
        byte_count = write_qty * 2
        regs = b"\x00" * byte_count
        return struct.pack(
            ">BHHHHB",
            0x17,
            kw.get("read_start_addr", 0), read_qty,
            kw.get("write_start_addr", 0), write_qty,
            byte_count
        ) + regs
    if func_code == 0x18:
        return struct.pack(">BH", 0x18, register_address)
    return None


def build_modbus_request(
    trans_id=1, unit_id=1, func_code=3,
    start_addr=0, quantity=10,
    coil_address=0, coil_value=0,
    register_address=0, register_value=0,
    mask_register_value=0,
    read_start_addr=0, read_quantity=0,
    write_start_addr=0, write_quantity=0,
    write_registers_values=None
):
    pdu = None
    try:
        if func_code == 0x01:
            pdu = ModbusPDU01ReadCoilsRequest(startAddr=start_addr, quantity=quantity)
        elif func_code == 0x02:
            pdu = ModbusPDU02ReadDiscreteInputsRequest(startAddr=start_addr, quantity=quantity)
        elif func_code == 0x03:
            pdu = ModbusPDU03ReadHoldingRegistersRequest(startAddr=start_addr, quantity=quantity)
        elif func_code == 0x04:
            pdu = ModbusPDU04ReadInputRegistersRequest(startAddr=start_addr, quantity=quantity)
        elif func_code == 0x06:
            pdu = ModbusPDU06WriteSingleRegisterRequest(registerAddr=register_address, registerValue=register_value)
        elif func_code == 0x07:
            pdu = ModbusPDU07ReadExceptionStatusRequest()
        elif func_code == 0x08:
            pdu = ModbusPDU08DiagnosticsRequest()
        elif func_code == 0x0B:
            pdu = ModbusPDU0BGetCommEventCounterRequest()
        elif func_code == 0x0C:
            pdu = ModbusPDU0CGetCommEventLogRequest()
        elif func_code == 0x11:
            pdu = ModbusPDU11ReportSlaveIdRequest()
        elif func_code == 0x14:
            pdu = ModbusPDU14ReadFileRecordRequest()
        elif func_code == 0x15:
            pdu = ModbusPDU15WriteFileRecordRequest()
        elif func_code == 0x2B:
            pdu = ModbusPDU2B0EReadDeviceIdentificationRequest()
    except Exception as e:
        print(f"[build_modbus_request] 功能码 0x{func_code:02X} 构造 PDU 失败: {type(e).__name__}: {e}")
        return None

    if pdu is not None:
        try:
            pkt = (
                IP(dst="127.0.0.1") / TCP(dport=5020) /
                ModbusADURequest(transId=trans_id, unitId=unit_id, protoId=0) /
                pdu
            )
            return bytes(pkt[ModbusADURequest])
        except Exception as e:
            print(f"[build_modbus_request] 功能码 0x{func_code:02X} 打包 ADU 失败: {type(e).__name__}: {e}")
            return None

    pdu_bytes = _build_pdu_bytes(
        func_code,
        start_addr=start_addr, quantity=quantity,
        coil_address=coil_address, coil_value=coil_value,
        register_address=register_address, register_value=register_value,
        mask_register_value=mask_register_value,
        read_start_addr=read_start_addr, read_quantity=read_quantity,
        write_start_addr=write_start_addr, write_quantity=write_quantity,
    )
    if pdu_bytes is None:
        print(f"[build_modbus_request] 不支持的功能码: 0x{func_code:02X}")
        return None

    adu = struct.pack(">HHHB", trans_id, 0, len(pdu_bytes) + 1, unit_id) + pdu_bytes
    return adu


def send_modbus_payload(payload, host="127.0.0.1", port=5020, timeout=3):
    if payload is None:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            s.sendall(payload)
            response = s.recv(1024)
            return response
    except (socket.timeout, ConnectionRefusedError, OSError):
        return None
    except Exception as e:
        print(f"[Modbus-tools] 发送异常: {type(e).__name__}: {e}")
        return None


def parse_modbus_response(raw):
    if not raw:
        return None
    try:
        from scapy.contrib.modbus import ModbusADUResponse
        pkt = ModbusADUResponse(raw)
        return {
            "transId": pkt.transId,
            "unitId": pkt.unitId,
            "raw_hex": raw.hex(),
            "raw_len": len(raw)
        }
    except Exception as e:
        return {"raw_hex": raw.hex(), "raw_len": len(raw), "parse_error": str(e)}
