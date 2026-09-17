from scapy.all import *
from scapy.contrib.modbus import *

def build_read_holding_registers(transaction_id=1, unit_id=1, start_addr=0, quantity=10):
    """构造 Modbus/TCP 读保持寄存器请求（功能码 0x03）"""
    pkt = (
        IP(dst="127.0.0.1") / TCP(dport=502) /
        ModbusADURequest(
            transId=transaction_id,
            unitId=unit_id,
            protoId=0
        ) /
        ModbusPDU03ReadHoldingRegistersRequest(
            startAddr=start_addr,
            quantity=quantity
        )
    )
    return pkt

if __name__ == "__main__":
    print(">>> 开始构造 Modbus 报文...")
    pkt = build_read_holding_registers()
    print(">>> 报文构造成功，下面是结构：")
    pkt.show()
    print("\n>>> 报文十六进制：")
    hexdump(pkt)