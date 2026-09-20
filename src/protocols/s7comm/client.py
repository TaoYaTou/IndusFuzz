import sys
import os
import json
import socket
from src.protocols.base import ProtocolBase
from src.core._resource import resource_path

_FUNC_CODES_PATH = resource_path(
    os.path.join("src", "protocols", "func_codes", "s7comm_func_codes.json")
)


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


_PROTO_NAME = "S7comm"
class S7CommClient(ProtocolBase):
    name = "s7comm"
    default_port = 10102

    def __init__(self):
        self._sock = None
        self._connected = False
        self._persistent = False
        self._real_host = None
        self._real_port = None
        self._rack = 0
        self._slot = 2
        self._timeout = 5
        self._conn_failures = 0

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        try:
            with open(_FUNC_CODES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("func_codes", [])
        except FileNotFoundError:
            print(f"[S7comm] 功能码定义文件不存在: {_FUNC_CODES_PATH}")
            return []
        except json.JSONDecodeError as e:
            print(f"[S7comm] 功能码定义文件解析失败: {e}")
            return []
        except Exception as e:
            print(f"[S7comm] 读取功能码失败: {type(e).__name__}: {e}")
            return []

    def build_request(
        self,
        trans_id=1,
        func_code=0x04,
        db_number=1,
        start_addr=0,
        length=10,
        **kwargs
    ) -> bytes:
        try:
            pdu = bytes([
                func_code & 0xFF,
                0x12,
                0x0A,
                0x10,
                0x02,
                0x00,
            ]) + db_number.to_bytes(2, "big") + start_addr.to_bytes(2, "big") + length.to_bytes(2, "big")

            header = bytes([
                0x03,
                0x00,
            ]) + trans_id.to_bytes(2, "big") + len(pdu).to_bytes(2, "big") + bytes([0x00, 0x00])

            return header + pdu
        except Exception as e:
            print(f"[S7comm] 构造请求失败: {type(e).__name__}: {e}")
            return None

    def connect(self, host, port, **kwargs) -> bool:
        self._rack = kwargs.get("rack", 0)
        self._slot = kwargs.get("slot", 2)
        self._timeout = kwargs.get("timeout", 5)
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.connect((host, port))
            dst_tsap = (1 << 8) | (self._rack << 4) | self._slot
            cotp_cr = bytes([
                0x03, 0x00, 0x00, 0x16,
                0x11, 0xE0, 0x00, 0x00, 0x00, 0x01, 0x00,
                0xC0, 0x01, 0x0A,
                0xC1, 0x02, 0x01, 0x00,
                0xC2, 0x02, (dst_tsap >> 8) & 0xFF, dst_tsap & 0xFF,
            ])
            s.sendall(cotp_cr)
            try:
                cc = s.recv(1024)
            except Exception:
                cc = b""
            if not cc or len(cc) < 8:
                s.close()
                print("[S7comm] COTP 连接确认失败")
                return False
            s7_setup = bytes([
                0x03, 0x00, 0x00, 0x19,
                0x02, 0xF0, 0x80,
                0x32, 0x01, 0x00, 0x00, 0x00, 0x00,
                0x00, 0x08, 0x00, 0x00,
                0xF0, 0x00, 0x00, 0x01, 0x00, 0x01, 0x03, 0xC0,
            ])
            s.sendall(s7_setup)
            try:
                s.recv(1024)
            except Exception:
                pass
            self._sock = s
            self._connected = True
            self._persistent = True
            self._real_host = host
            self._real_port = port
            self._conn_failures = 0
            print(f"[S7comm] 已连接真实设备 {host}:{port} (rack={self._rack}, slot={self._slot})")
            return True
        except Exception as e:
            print(f"[S7comm] 连接失败: {type(e).__name__}: {e}")
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

    def is_connected(self) -> bool:
        return self._connected

    def _reconnect(self) -> bool:
        self.disconnect()
        if self._real_host and self._real_port:
            return self.connect(self._real_host, self._real_port, rack=self._rack, slot=self._slot, timeout=self._timeout)
        return False

    def _recv_frame(self, sock):
        try:
            header = sock.recv(4)
            if not header:
                return b""
            if len(header) < 4 or header[0] != 0x03:
                return header
            length = (header[2] << 8) | header[3]
            remaining = length - 4
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

    def send_payload(self, payload, host="127.0.0.1", port=10102, timeout=3) -> bytes:
        if payload is None:
            return None
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
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(timeout)
                s.connect((host, port))
                s.sendall(payload)
                response = s.recv(1024)
                return response
        except socket.timeout:
            return None
        except ConnectionRefusedError:
            return None
        except OSError:
            return None
        except Exception as e:
            print(f"[S7comm] 发送失败: {type(e).__name__}: {e}")
            return None

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0, "parse_error": "空响应"}
        try:
            raw_hex = raw.hex()
            raw_len = len(raw)
            func_code = None
            if raw_len >= 8:
                func_code = raw[7]
            return {
                "raw_hex": raw_hex,
                "raw_len": raw_len,
                "func_code": func_code,
            }
        except Exception as e:
            return {
                "raw_hex": raw.hex() if raw else "",
                "parse_error": f"{type(e).__name__}: {e}"
            }

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if response[0] != 0x03:
            return "MALFORMED"
        if len(response) >= 10 and response[8] == 0x03 and response[9] == 0x85:
            return "EXCEPTION"
        return "NORMAL"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
        from src.protocols.s7comm.mutator import mutate_payload as local_mutate
        from src.protocols.s7comm.llm_mutator import llm_generate_mutations

        total_funcs = len(func_codes)

        for idx, fc_str in enumerate(func_codes, start=1):
            if stop_event and stop_event.is_set():
                return
            try:
                func_code = int(fc_str, 16) if isinstance(fc_str, str) else int(fc_str)
            except (ValueError, TypeError):
                reason = f"功能码 {fc_str} 格式无效"
                print(f"警告：{reason}，跳过")
                skipped.append({"round": idx, "func_code": fc_str, "reason": reason})
                continue

            base_payload = self.build_request(func_code=func_code)
            if base_payload is None:
                reason = f"功能码 0x{func_code:02X} 基准报文构造失败"
                print(f"警告：{reason}，跳过")
                skipped.append({"round": idx, "func_code": func_code, "reason": reason})
                build_failures.append({"func_code": func_code, "stage": "基准报文构造", "reason": reason})
                continue

            base_hex = base_payload.hex()
            print(f"\n>>> 功能码 0x{func_code:02X} 基准报文: {base_hex}")

            mutations = []
            try:
                mutations = llm_generate_mutations(
                    base_hex, count=5,
                    status_collector=llm_status,
                    func_code_str=f'0x{func_code:02X}', stop_event=stop_event)
            except Exception as e:
                print(f"警告：S7comm LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
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
                print(f"警告：功能码 0x{func_code:02X} {reason}，跳过")
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
                    print(f"警告：功能码 0x{func_code:02X} {reason}")
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
                    "protocol": "s7comm",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
