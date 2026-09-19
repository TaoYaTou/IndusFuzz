import socket
from scapy.all import *
from scapy.contrib.modbus import *

def build_read_holding_registers(transaction_id=1, unit_id=1, start_addr=0, quantity=10):
    pkt = (
        IP(dst="127.0.0.1") / TCP(dport=5020) /
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

def extract_modbus_payload(pkt):
    modbus_bytes = bytes(pkt[ModbusADURequest])
    return modbus_bytes

def send_via_socket(payload, host="127.0.0.1", port=5020, timeout=3):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        s.connect((host, port))
        print(f">>> 已连接 {host}:{port}")
        s.sendall(payload)
        print(f">>> 已发送 {len(payload)} 字节")
        response = s.recv(1024)
        print(f">>> 收到 {len(response)} 字节响应")
        return response

if __name__ == "__main__":
    print(">>> 构造 Modbus 报文...")
    pkt = build_read_holding_registers()
    pkt.show()

    payload = extract_modbus_payload(pkt)
    print(f"\n>>> Modbus 报文（{len(payload)} 字节）：{payload.hex()}")

    response = send_via_socket(payload)

    if response:
        print(f"\n>>> 响应原始字节：{response.hex()}")
        try:
            resp_pkt = ModbusADUResponse(response)
            resp_pkt.show()
        except Exception as e:
            print(f">>> 解析响应失败：{e}")
