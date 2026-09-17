import sys
import struct
import socket
from src.protocols.base import ProtocolBase

_DNP3_START = 0x0564


def build_dnp3_request(
    function_code=0x01,
    control=0x00,
    dest=0x0101,
    src=0x0000,
    payload=b"",
):
    try:
        length = 5 + len(payload)
        header = bytearray()
        header.append(0x05)
        header.append(0x64)
        header.append(length & 0xFF)
        header.append(control & 0xFF)
        header.extend(struct.pack(">H", function_code))
        header.extend(struct.pack("<H", dest))
        header.extend(struct.pack("<H", src))
        result = bytes(header) + payload

        crc = _crc16(result)
        return bytes(result) + struct.pack("<H", crc)
    except Exception as e:
        print(f"[DNP3] build_dnp3_request 失败: {type(e).__name__}: {e}")
        return None


def _crc16(data):
    crc = 0x0000
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def send_dnp3_payload(payload, host="127.0.0.1", port=20000, timeout=3):
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
        print(f"[DNP3] 发送失败: {type(e).__name__}: {e}")
        return None


_PROTO_NAME = "DNP3"
_FUNC_NAME_MAP = {
    0x00: "CONFIRM",
    0x01: "READ",
    0x02: "WRITE",
    0x03: "SELECT",
    0x04: "OPERATE",
    0x05: "DIRECT_OPERATE",
    0x06: "DIRECT_OPERATE_NR",
    0x07: "IMMED_FREEZE",
    0x08: "IMMED_FREEZE_NR",
    0x09: "FREEZE_CLEAR",
    0x0A: "FREEZE_CLEAR_NR",
    0x0B: "FREEZE_AT_TIME",
    0x0C: "FREEZE_AT_TIME_NR",
    0x0D: "COLD_RESTART",
    0x0E: "WARM_RESTART",
    0x0F: "INITIALIZE_DATA",
    0x10: "INITIALIZE_APPLICATION",
    0x11: "START_APPLICATION",
    0x12: "STOP_APPLICATION",
    0x13: "SAVE_CONFIGURATION",
    0x14: "ENABLE_UNSOLICITED",
    0x15: "DISABLE_UNSOLICITED",
    0x16: "ASSIGN_CLASS",
    0x17: "DELAY_MEASURE",
    0x18: "RECORD_CURRENT_TIME",
    0x19: "OPEN_FILE",
    0x1A: "CLOSE_FILE",
    0x1B: "DELETE_FILE",
    0x1C: "GET_FILE_INFO",
    0x1D: "AUTHENTICATE_FILE",
    0x1E: "ABORT_FILE",
    0x81: "RESPONSE",
    0x82: "UNSOLICITED_RESPONSE",
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


class DNP3Client(ProtocolBase):
    name = "dnp3"
    default_port = 20000

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        # 仅返回请求方向功能码（过滤 0x81 RESPONSE / 0x82 UNSOLICITED_RESPONSE）
        return [fc for fc in _FUNC_NAME_MAP.keys() if fc < 0x80]

    def build_request(self, **kwargs):
        func_code = kwargs.get("func_code", 0x01)
        return build_dnp3_request(function_code=func_code)

    def send_payload(self, payload, host="127.0.0.1", port=20000, timeout=3):
        return send_dnp3_payload(payload, host=host, port=port, timeout=timeout)

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0}
        return {"raw_hex": raw.hex(), "raw_len": len(raw)}

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if len(response) >= 6 and (response[0] != 0x05 or response[1] != 0x64):
            return "MALFORMED"
        if len(response) >= 6 and response[5] & 0x80:
            return "EXCEPTION"
        return "NORMAL"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
        from src.protocols.dnp3.mutator import mutate_payload as local_mutate
        from src.protocols.dnp3.llm_mutator import llm_generate_mutations

        total_funcs = len(func_codes)

        for idx, fc_str in enumerate(func_codes, start=1):
            if stop_event and stop_event.is_set():
                return
            try:
                func_code = int(fc_str, 16) if isinstance(fc_str, str) else int(fc_str)
            except (ValueError, TypeError):
                skipped.append({"round": idx, "func_code": fc_str, "reason": "格式无效"})
                continue

            base_payload = build_dnp3_request(function_code=func_code)
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
                    func_code_str=f'0x{func_code:02X}')
            except Exception as e:
                print(f"警告：DNP3 LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
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

                response = send_dnp3_payload(mutation_bytes, host=host, port=port, timeout=timeout)
                response_hex = response.hex() if response else ""
                classification = self._classify(mutation_bytes, response)

                print(f"[0x{func_code:02X}] Round {idx}/{total_funcs}, Mutation {i}/5: {mutation} -> {classification}")

                if sys.stdout.isatty():
                    _pct = (idx - 1) / total_funcs * 100 if total_funcs else 0
                    sys.stdout.write(f"\r当前进度：[{idx}/{total_funcs}] {_pct:.1f}% | 协议：{_PROTO_NAME} | 功能码：0x{func_code:02X} | 状态：{classification}")
                    sys.stdout.flush()


                results.append({
                    "protocol": "dnp3",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
