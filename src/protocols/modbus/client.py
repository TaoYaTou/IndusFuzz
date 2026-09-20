import sys
import socket
from src.protocols.base import ProtocolBase
from src.protocols.modbus.modbus_tools import build_modbus_request, send_modbus_payload
from src.protocols.modbus.mutator import mutate_payload as local_mutate
from src.protocols.modbus.llm_mutator import llm_generate_mutations

_PROTO_NAME = "Modbus"
_FUNC_NAME_MAP = {
    0x01: "Read Coils",
    0x02: "Read Discrete Inputs",
    0x03: "Read Holding Registers",
    0x04: "Read Input Registers",
    0x05: "Write Single Coil",
    0x06: "Write Single Register",
    0x07: "Read Exception Status",
    0x08: "Diagnostics",
    0x0B: "Get Comm Event Counter",
    0x0C: "Get Comm Event Log",
    0x0F: "Write Multiple Coils",
    0x10: "Write Multiple Registers",
    0x11: "Report Slave ID",
    0x14: "Read File Record",
    0x15: "Write File Record",
    0x16: "Mask Write Register",
    0x17: "Read/Write Multiple Registers",
    0x18: "Read FIFO Queue",
    0x2B: "Read Device Identification",
}


# 非法功能码集合（Modbus 标准未定义，设备必回异常响应）
_ILLEGAL_FC_BYTES = {"5a", "a5", "ff"}


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

    # 保证至少有一条变异使用非法功能码（5A/A5/FF），确保能触发 EXCEPTION 分类
    has_illegal = any(len(h) >= 16 and h[14:16] in _ILLEGAL_FC_BYTES for h in mutations)
    if not has_illegal and len(base_payload) >= 8:
        forced = bytearray(base_payload)
        forced[7] = 0xFF  # 强制写入非法功能码
        forced_hex = forced.hex()
        if forced_hex not in seen:
            if mutations:
                mutations[-1] = forced_hex
            else:
                mutations.append(forced_hex)
    return mutations


class ModbusClient(ProtocolBase):
    name = "modbus"
    default_port = 5020

    def __init__(self):
        self._sock = None
        self._connected = False
        self._persistent = False
        self._real_host = None
        self._real_port = None
        self._unit_id = 1
        self._timeout = 5
        self._conn_failures = 0

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        return list(_FUNC_NAME_MAP.keys())

    def build_request(self, **kwargs):
        kwargs.setdefault("unit_id", self._unit_id)
        return build_modbus_request(**kwargs)

    def connect(self, host, port, **kwargs) -> bool:
        self._unit_id = kwargs.get("unit_id", 1)
        self._timeout = kwargs.get("timeout", 5)
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.connect((host, port))
            # 协议层握手：发 Read Holding Registers (fc=0x03, 合法最小请求)
            # 真实 Modbus PLC 必须返回合法 MBAP 帧；假 TCP server 不会
            handshake = bytes([
                0x00, 0x01,                   # transaction_id
                0x00, 0x00,                   # protocol_id (Modbus TCP 固定 0x0000)
                0x00, 0x06,                   # length = unit_id + pdu(5)
                self._unit_id & 0xFF,          # unit_id
                0x03,                          # fc=Read Holding Registers
                0x00, 0x00,                    # start_addr = 0
                0x00, 0x01,                    # quantity = 1
            ])
            s.sendall(handshake)
            try:
                resp = s.recv(1024)
            except socket.timeout:
                s.close()
                print(f"[Modbus] 握手失败: 真实设备 {host}:{port} 未响应协议层请求 (超时)")
                return False
            except OSError:
                s.close()
                print(f"[Modbus] 握手失败: 真实设备 {host}:{port} 连接中断")
                return False
            # 校验：MBAP 头至少 7 字节；protocol_id 必须是 0x0000
            if not resp or len(resp) < 7:
                s.close()
                print(f"[Modbus] 握手失败: 响应过短 (len={len(resp) if resp else 0})")
                return False
            if resp[2:4] != b"\x00\x00":
                s.close()
                print(f"[Modbus] 握手失败: protocol_id 非 0x0000 (got 0x{resp[2]:02X}{resp[3]:02X})")
                return False

            self._sock = s
            self._connected = True
            self._persistent = True
            self._real_host = host
            self._real_port = port
            self._conn_failures = 0
            print(f"[Modbus] 已连接真实设备 {host}:{port} (unit_id={self._unit_id})")
            return True
        except Exception as e:
            print(f"[Modbus] 连接失败: {type(e).__name__}: {e}")
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
            return self.connect(self._real_host, self._real_port, unit_id=self._unit_id, timeout=self._timeout)
        return False

    def _recv_frame(self, sock):
        try:
            header = sock.recv(6)
            if not header:
                return b""
            if len(header) < 6:
                return header
            length = (header[4] << 8) | header[5]
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

    def send_payload(self, payload, host="127.0.0.1", port=5020, timeout=3):
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
        return send_modbus_payload(payload, host=host, port=port, timeout=timeout)

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0}
        return {"raw_hex": raw.hex(), "raw_len": len(raw)}

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if len(response) >= 8 and len(mutated) >= 8:
            req_fc = mutated[7]
            resp_fc = response[7]
            if resp_fc == (req_fc | 0x80):
                return "EXCEPTION"
        return "NORMAL"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
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

            base_payload = build_modbus_request(func_code=func_code, unit_id=self._unit_id)
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
                print(f"警告：Modbus LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
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
                    "protocol": "modbus",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
