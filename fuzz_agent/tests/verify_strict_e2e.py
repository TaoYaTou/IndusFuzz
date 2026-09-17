import os
import sys
import socket
import subprocess
import time
import struct

ROOT = os.path.dirname(os.path.abspath(__file__))
FUZZ_AGENT = os.path.abspath(os.path.join(ROOT, ".."))
sys.path.insert(0, FUZZ_AGENT)

from src.protocols.s7comm.client import S7CommClient
from src.protocols.dnp3.client import DNP3Client, build_dnp3_request
from src.protocols.iec104.client import IEC104Client, build_iec104_request
from src.protocols.iec61850.client import IEC61850Client, build_iec61850_request
from src.protocols.enip.client import ENIPClient, build_enip_request
from src.protocols.opcua.client import OPCUAClient, build_opcua_request, build_opcua_hello


def wait_port(port, timeout=8):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def start_server(script, port, strict):
    cmd = [sys.executable, os.path.join(FUZZ_AGENT, "server", script), "--port", str(port)]
    if strict:
        cmd.append("--strict")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ok = wait_port(port)
    return proc, ok


def send_one(port, payload, handshake=None):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
            s.settimeout(2)
            if handshake:
                s.sendall(handshake)
                try:
                    s.recv(4096)
                except Exception:
                    pass
            s.sendall(payload)
            try:
                return s.recv(4096)
            except socket.timeout:
                return None
    except Exception:
        return None


def mutate_byte(payload, offset, value):
    b = bytearray(payload)
    b[offset] = value
    return bytes(b)


results = []


def check(name, expect, got, alt=None):
    ok = (got == expect) or (alt is not None and got == alt)
    status = "PASS" if ok else "FAIL"
    results.append((status, name, expect, got))
    print(f"[{status}] {name}: 期望 {expect}，实际 {got}")


s7 = S7CommClient()
dnp3 = DNP3Client()
i104 = IEC104Client()
i61850 = IEC61850Client()
enip = ENIPClient()
opcua = OPCUAClient()

CASES = [
    {
        "name": "s7comm", "script": "s7comm_server.py", "port": 15102, "client": s7,
        "valid": lambda: s7.build_request(func_code=0x04),
        "bad_func": lambda: s7.build_request(func_code=0x11),
        "malformed": lambda: mutate_byte(s7.build_request(func_code=0x04), 0, 0x04),
        "classify": lambda payload, resp: s7._classify(payload, resp),
    },
    {
        "name": "dnp3", "script": "dnp3_server.py", "port": 25000, "client": dnp3,
        "valid": lambda: build_dnp3_request(function_code=0x01),
        "bad_func": lambda: build_dnp3_request(function_code=0x2F),
        "malformed": lambda: mutate_byte(build_dnp3_request(function_code=0x01), 0, 0x06),
        "classify": lambda payload, resp: dnp3._classify(resp),
    },
    {
        "name": "iec104", "script": "iec104_server.py", "port": 12404, "client": i104,
        "valid": lambda: build_iec104_request(type_id=0x64),
        "bad_func": lambda: build_iec104_request(type_id=0x01),
        "malformed": lambda: mutate_byte(build_iec104_request(type_id=0x64), 0, 0x00),
        "classify": lambda payload, resp: i104._classify(resp),
    },
    {
        "name": "iec61850", "script": "iec61850_server.py", "port": 1102, "client": i61850,
        "valid": lambda: build_iec61850_request(pdu_type=0xB0),
        "bad_func": lambda: build_iec61850_request(pdu_type=0x99),
        "malformed": lambda: mutate_byte(build_iec61850_request(pdu_type=0xB0), 0, 0x31),
        "classify": lambda payload, resp: i61850._classify(resp),
    },
    {
        "name": "enip", "script": "enip_server.py", "port": 44819, "client": enip,
        "valid": lambda: build_enip_request(service_code=0x01),
        "bad_func": lambda: build_enip_request(service_code=0x99),
        "malformed": lambda: mutate_byte(mutate_byte(build_enip_request(service_code=0x01), 0, 0x00), 1, 0x99),
        "classify": lambda payload, resp: enip._classify(resp),
    },
    {
        "name": "opcua", "script": "opcua_server.py", "port": 14840, "client": opcua,
        "valid": lambda: build_opcua_request(446),
        "bad_func": lambda: build_opcua_request(999),
        "malformed": lambda: b"XXX" + build_opcua_request(446)[3:],
        "handshake": lambda: build_opcua_hello(),
        "classify": lambda payload, resp: opcua._classify(resp),
    },
]


def run_case(case, strict):
    mode = "strict" if strict else "default"
    proc, ok = start_server(case["script"], case["port"], strict)
    try:
        if not ok:
            check(f"{case['name']}/{mode}/server-start", "STARTED", "FAILED")
            return
        check(f"{case['name']}/{mode}/server-start", "STARTED", "STARTED")

        handshake = case.get("handshake")
        hs = handshake() if handshake else None

        valid_payload = case["valid"]()
        resp = send_one(case["port"], valid_payload, hs)
        cls = case["classify"](valid_payload, resp)
        check(f"{case['name']}/{mode}/valid->NORMAL", "NORMAL", cls)

        bad_payload = case["bad_func"]()
        resp = send_one(case["port"], bad_payload, hs)
        cls = case["classify"](bad_payload, resp)
        expect = "EXCEPTION" if strict else "NORMAL"
        check(f"{case['name']}/{mode}/bad-func->{expect}", expect, cls)

        if strict:
            bad_payload2 = case["malformed"]()
            resp = send_one(case["port"], bad_payload2, hs)
            cls = case["classify"](bad_payload2, resp)
            check(f"{case['name']}/{mode}/malformed->CLOSED-or-EMPTY", "CONN_CLOSED", cls, alt="EMPTY")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()


for case in CASES:
    run_case(case, strict=True)
    run_case(case, strict=False)

fails = [r for r in results if r[0] == "FAIL"]
print(f"\n总计 {len(results)} 项，通过 {len(results) - len(fails)} 项，失败 {len(fails)} 项")
sys.exit(1 if fails else 0)
