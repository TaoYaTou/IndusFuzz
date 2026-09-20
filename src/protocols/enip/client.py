import sys
import socket
import struct
from src.protocols.base import ProtocolBase


def build_enip_request(
    service_code=0x01,
    path=b"\x20\x01\x24\x01",
    path_size=None,
    data=b"",
    session_handle=0x00000000,
    sender_context=b"\x00" * 8,
):
    try:
        cip = bytearray()
        cip.append(service_code & 0xFF)
        if path_size is None:
            psize = len(path) // 2
        else:
            psize = path_size
        cip.append(psize & 0xFF)
        cip.extend(path)
        cip.extend(data)

        encaps = bytearray()
        encaps.extend(struct.pack("<H", 0x6F))
        encaps.extend(struct.pack("<H", len(cip)))
        encaps.extend(struct.pack("<I", session_handle))
        encaps.extend(struct.pack("<I", 0x00000000))
        encaps.extend(sender_context[:8].ljust(8, b"\x00"))
        encaps.extend(struct.pack("<I", 0x00000000))
        encaps.extend(cip)

        return bytes(encaps)
    except Exception as e:
        print(f"[ENIP] build_enip_request 失败: {type(e).__name__}: {e}")
        return None


def send_enip_payload(payload, host="127.0.0.1", port=44818, timeout=3):
    if payload is None:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            s.sendall(payload)
            response = s.recv(4096)
            return response
    except socket.timeout:
        return None
    except ConnectionRefusedError:
        return None
    except OSError:
        return None
    except Exception as e:
        print(f"[ENIP] 发送失败: {type(e).__name__}: {e}")
        return None


_PROTO_NAME = "ENIP"
_CIP_SERVICE_NAMES = {
    0x01: "Get_Attributes_All", 0x02: "Set_Attributes_All",
    0x03: "Get_Attribute_List", 0x04: "Set_Attribute_List",
    0x05: "Reset", 0x06: "Start", 0x07: "Stop",
    0x08: "Create", 0x09: "Delete",
    0x0A: "Multiple_Service_Packet",
    0x0D: "Apply_Attributes",
    0x0E: "Get_Attribute_Single",
    0x10: "Set_Attribute_Single",
    0x11: "Find_Next_Object_Instance",
    0x14: "Error_Response",
    0x15: "Restore", 0x16: "Save",
    0x17: "No_Operation",
    0x18: "Get_Member", 0x19: "Set_Member",
    0x1A: "Insert_Member", 0x1B: "Remove_Member",
    0x1C: "GroupSync",
    0x4C: "Read_Tag", 0x4D: "Write_Tag",
    0x4E: "Forward_Close",
    0x52: "Unconnected_Send",
    0x54: "Forward_Open",
}

_REQUEST_SERVICES = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0D, 0x0E, 0x10, 0x11, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A,
    0x1B, 0x1C, 0x4C, 0x4D, 0x4E, 0x52, 0x54,
}


def _generate_local_fallback(base_payload, base_hex, mutate_fn, count=5, max_attempts=30):
    seen = set()
    mutations = []
    for _ in range(max_attempts):
        if len(mutations) >= count:
            break
        m = mutate_fn(base_payload)
        if not m:
            continue
        hex_m = m.hex()
        if hex_m == base_hex or hex_m in seen:
            continue
        seen.add(hex_m)
        mutations.append(hex_m)
    return mutations


class ENIPClient(ProtocolBase):
    name = "enip"
    default_port = 44818

    def __init__(self):
        self._sock = None
        self._connected = False
        self._persistent = False
        self._real_host = None
        self._real_port = None
        self._slot = 0
        self._session_handle = 0
        self._timeout = 5
        self._conn_failures = 0

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        return sorted(_REQUEST_SERVICES)

    def build_request(self, **kwargs):
        service_code = kwargs.get("service_code", 0x01)
        return build_enip_request(service_code=service_code, session_handle=self._session_handle)

    def connect(self, host, port, **kwargs) -> bool:
        self._slot = kwargs.get("slot", 0)
        self._timeout = kwargs.get("timeout", 5)
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.connect((host, port))
            reg_session = bytes([
                0x65, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
                0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            ])
            s.sendall(reg_session)
            try:
                resp = s.recv(1024)
                if resp and len(resp) >= 8:
                    self._session_handle = struct.unpack("<I", resp[4:8])[0]
            except Exception:
                pass
            self._sock = s
            self._connected = True
            self._persistent = True
            self._real_host = host
            self._real_port = port
            self._conn_failures = 0
            print(f"[ENIP] 已连接真实设备 {host}:{port} (slot={self._slot}, session=0x{self._session_handle:08X})")
            return True
        except Exception as e:
            print(f"[ENIP] 连接失败: {type(e).__name__}: {e}")
            if s:
                try:
                    s.close()
                except Exception:
                    pass
            self._connected = False
            self._sock = None
            return False

    def disconnect(self) -> None:
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
        self._connected = False
        self._persistent = False
        self._real_host = None
        self._real_port = None
        self._session_handle = 0

    def is_connected(self) -> bool:
        return self._connected

    def _reconnect(self) -> bool:
        self.disconnect()
        if self._real_host and self._real_port:
            return self.connect(self._real_host, self._real_port, slot=self._slot, timeout=self._timeout)
        return False

    def _recv_frame(self, sock):
        try:
            header = sock.recv(24)
            if not header:
                return b""
            if len(header) < 24:
                return header
            length = struct.unpack("<H", header[2:4])[0]
            remaining = length
            data = bytearray()
            while remaining > 0:
                chunk = sock.recv(min(4096, remaining))
                if not chunk:
                    break
                data.extend(chunk)
                remaining -= len(chunk)
            return bytes(header) + bytes(data)
        except Exception:
            return None

    def send_payload(self, payload, host="127.0.0.1", port=44818, timeout=3):
        if self._persistent:
            if not self._connected:
                if self._conn_failures > 3:
                    return None
                if not self._reconnect():
                    self._conn_failures += 1
                    return None
            try:
                self._sock.settimeout(timeout)
                self._sock.sendall(payload)
                resp = self._recv_frame(self._sock)
                if resp is None:
                    self._connected = False
                    self._conn_failures += 1
                    try:
                        self._sock.close()
                    except Exception:
                        pass
                    self._sock = None
                    return None
                if resp == b"":
                    self._connected = False
                return resp if resp else None
            except Exception:
                self._connected = False
                self._conn_failures += 1
                try:
                    self._sock.close()
                except Exception:
                    pass
                self._sock = None
                return None
        return send_enip_payload(payload, host=host, port=port, timeout=timeout)

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0}
        return {"raw_hex": raw.hex(), "raw_len": len(raw)}

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if len(response) < 24:
            return "MALFORMED"
        status = struct.unpack("<I", response[8:12])[0]
        if status != 0:
            return "EXCEPTION"
        if len(response) >= 27 and response[26] != 0:
            return "EXCEPTION"
        return "NORMAL"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
        from src.protocols.enip.mutator import mutate_payload as local_mutate
        from src.protocols.enip.llm_mutator import llm_generate_mutations

        total_funcs = len(func_codes)

        for idx, fc_str in enumerate(func_codes, start=1):
            if stop_event and stop_event.is_set():
                return
            try:
                func_code = int(fc_str, 16) if isinstance(fc_str, str) else int(fc_str)
            except (ValueError, TypeError):
                skipped.append({"round": idx, "func_code": fc_str, "reason": "格式无效"})
                continue

            base_payload = build_enip_request(service_code=func_code, session_handle=self._session_handle)
            if base_payload is None:
                reason = f"Service 0x{func_code:02X} 基准报文构造失败"
                print(f"警告：{reason}，跳过")
                skipped.append({"round": idx, "func_code": func_code, "reason": reason})
                build_failures.append({"func_code": func_code, "stage": "基准报文构造", "reason": reason})
                continue

            base_hex = base_payload.hex()
            print(f"\n>>> Service 0x{func_code:02X} ({_CIP_SERVICE_NAMES.get(func_code, 'Unknown')}) 基准报文: {base_hex}")

            mutations = []
            try:
                mutations = llm_generate_mutations(
                    base_hex, count=5,
                    status_collector=llm_status,
                    func_code_str=f'0x{func_code:02X}', stop_event=stop_event)
            except Exception as e:
                print(f"警告：ENIP LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
                mutations = []

            if len(mutations) < 5:
                if mutations:
                    print("[LLM] 变异不足 5 个，补齐到 5 个")
                    if llm_status:
                        llm_status.on_fallback_used(f"0x{func_code:02X}", reason="partial LLM, filled locally")
                    seen = set(mutations)
                    for fb in _generate_local_fallback(base_payload, base_hex, local_mutate, count=5):
                        if fb not in seen:
                            mutations.append(fb)
                            seen.add(fb)
                        if len(mutations) >= 5:
                            break
                else:
                    print("[LLM] 未生成变异，使用本地变异回退")
                    if llm_status:
                        llm_status.on_fallback_only(f"0x{func_code:02X}")
                    mutations = _generate_local_fallback(base_payload, base_hex, local_mutate, count=5)

            if not mutations:
                reason = "无有效变异"
                print(f"警告：Service 0x{func_code:02X} {reason}，跳过")
                skipped.append({"round": idx, "func_code": func_code, "reason": reason})
                build_failures.append({"func_code": func_code, "stage": "变异生成", "reason": reason})
                continue
            for i, mutation in enumerate(mutations[:5], start=1):
                if stop_event and stop_event.is_set():
                    return
                try:
                    mutation_bytes = bytes.fromhex(mutation)
                except ValueError:
                    reason = f"变异报文不是合法十六进制：{mutation}"
                    print(f"警告：Service 0x{func_code:02X} {reason}")
                    build_failures.append({"func_code": func_code, "stage": "变异报文解析", "reason": reason})
                    continue

                response = self.send_payload(mutation_bytes, host=host, port=port, timeout=timeout)
                if self._conn_failures > 3:
                    if stop_event:
                        stop_event.set()
                    break
                response_hex = response.hex() if response else ""
                classification = self._classify(mutation_bytes, response)

                print(f"[0x{func_code:02X}] Round {idx}/{total_funcs}, Mutation {i}/5: {mutation} -> {classification}")

                if sys.stdout.isatty():
                    _pct = (idx - 1) / total_funcs * 100 if total_funcs else 0
                    sys.stdout.write(f"\r当前进度：[{idx}/{total_funcs}] {_pct:.1f}% | 协议：{_PROTO_NAME} | 功能码：0x{func_code:02X} | 状态：{classification}")
                    sys.stdout.flush()


                results.append({
                    "protocol": "enip",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
