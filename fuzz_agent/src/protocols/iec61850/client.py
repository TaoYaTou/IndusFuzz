import sys
import socket
from src.protocols.base import ProtocolBase


def build_iec61850_request(
    pdu_type=0xB0,
    invoke_id=1,
    variable_spec=b"\x02\x01\x01",
    data=b"",
):
    try:
        mms_pdu = bytearray()
        mms_pdu.append(pdu_type & 0xFF)
        body_len = 2 + len(variable_spec) + len(data)
        if body_len < 128:
            mms_pdu.append(body_len)
        else:
            mms_pdu.append(0x81)
            mms_pdu.append(body_len & 0xFF)
        mms_pdu.append(0x00)
        mms_pdu.append(invoke_id & 0xFF)
        mms_pdu.extend(variable_spec)
        mms_pdu.extend(data)

        cotp = bytearray()
        cotp.append(0xF0)
        cotp.append(len(mms_pdu))
        cotp.append(0x00)
        cotp.append(0x00)
        cotp.append(0x80)
        cotp.append(0x00)

        tpkt_len = len(cotp) + len(mms_pdu) + 4
        tpkt = bytearray()
        tpkt.append(0x30)
        tpkt.append(0x00)
        tpkt.append((tpkt_len >> 8) & 0xFF)
        tpkt.append(tpkt_len & 0xFF)

        return bytes(tpkt) + bytes(cotp) + bytes(mms_pdu)
    except Exception as e:
        print(f"[IEC61850] build_iec61850_request 失败: {type(e).__name__}: {e}")
        return None


def send_iec61850_payload(payload, host="127.0.0.1", port=102, timeout=3):
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
        print(f"[IEC61850] 发送失败: {type(e).__name__}: {e}")
        return None


_PROTO_NAME = "IEC61850"
_PDU_TYPE_NAME_MAP = {
    0x81: "INITIATE", 0x82: "INITIATE_ACK",
    0x83: "CONFIRMED_REQUEST", 0x84: "CONFIRMED_RESPONSE", 0x85: "CONFIRMED_ERROR",
    0x86: "UNCONFIRMED_REQUEST",
    0xA8: "CANCEL_REQUEST", 0xA9: "CANCEL_RESPONSE", 0xAA: "CANCEL_ERROR",
    0xAB: "CONCLUDE_REQUEST",
    0xAC: "SERVICE_REQUEST", 0xAD: "SERVICE_RESPONSE", 0xAE: "SERVICE_ERROR",
    0xAF: "UNCONFIRMED_SERVICE",
    0xB0: "READ_REQUEST", 0xB1: "READ_RESPONSE",
    0xB2: "WRITE_REQUEST", 0xB3: "WRITE_RESPONSE", 0xB4: "WRITE_ERROR",
    0xB5: "GET_NAME_LIST_REQUEST", 0xB6: "GET_NAME_LIST_RESPONSE",
    0xB7: "IDENTIFY_REQUEST", 0xB8: "IDENTIFY_RESPONSE",
    0xB9: "RENAME_REQUEST", 0xBA: "RENAME_RESPONSE", 0xBB: "RENAME_ERROR",
    0xBC: "STATUS_REQUEST", 0xBD: "STATUS_RESPONSE", 0xBE: "STATUS_ERROR",
    0xBF: "GET_FILE_REQUEST", 0xC0: "GET_FILE_RESPONSE",
    0xC1: "SET_FILE_REQUEST", 0xC2: "DELETE_FILE_REQUEST",
    0xC3: "SET_FILE_RESPONSE", 0xC4: "DELETE_FILE_RESPONSE",
    0xC5: "GET_FILE_ATTR_REQUEST", 0xC6: "GET_FILE_ATTR_RESPONSE",
}


_REQUEST_PDU_TYPES = {
    0x81, 0x83, 0x86, 0xA8, 0xAB, 0xAC, 0xAF,
    0xB0, 0xB2, 0xB5, 0xB7, 0xB9, 0xBC,
    0xBF, 0xC1, 0xC2, 0xC5,
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


class IEC61850Client(ProtocolBase):
    name = "iec61850"
    default_port = 102

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        return sorted(_REQUEST_PDU_TYPES)

    def build_request(self, **kwargs):
        pdu_type = kwargs.get("pdu_type", 0xB0)
        return build_iec61850_request(pdu_type=pdu_type)

    def send_payload(self, payload, host="127.0.0.1", port=102, timeout=3):
        return send_iec61850_payload(payload, host=host, port=port, timeout=timeout)

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0}
        return {"raw_hex": raw.hex(), "raw_len": len(raw)}

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if response[0] != 0x30:
            return "MALFORMED"
        if len(response) >= 11 and response[10] == 0xA2:
            return "EXCEPTION"
        return "NORMAL"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
        from src.protocols.iec61850.mutator import mutate_payload as local_mutate
        from src.protocols.iec61850.llm_mutator import llm_generate_mutations

        total_funcs = len(func_codes)

        for idx, fc_str in enumerate(func_codes, start=1):
            if stop_event and stop_event.is_set():
                return
            try:
                func_code = int(fc_str, 16) if isinstance(fc_str, str) else int(fc_str)
            except (ValueError, TypeError):
                skipped.append({"round": idx, "func_code": fc_str, "reason": "格式无效"})
                continue

            base_payload = build_iec61850_request(pdu_type=func_code)
            if base_payload is None:
                reason = f"PDU Type 0x{func_code:02X} 基准报文构造失败"
                print(f"警告：{reason}，跳过")
                skipped.append({"round": idx, "func_code": func_code, "reason": reason})
                build_failures.append({"func_code": func_code, "stage": "基准报文构造", "reason": reason})
                continue

            base_hex = base_payload.hex()
            print(f"\n>>> PDU 0x{func_code:02X} ({_PDU_TYPE_NAME_MAP.get(func_code, 'Unknown')}) 基准报文: {base_hex}")

            mutations = []
            try:
                mutations = llm_generate_mutations(
                    base_hex, count=5,
                    status_collector=llm_status,
                    func_code_str=f'0x{func_code:02X}')
            except Exception as e:
                print(f"警告：IEC61850 LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
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
                print(f"警告：PDU 0x{func_code:02X} {reason}，跳过")
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
                    print(f"警告：PDU 0x{func_code:02X} {reason}")
                    build_failures.append({"func_code": func_code, "stage": "变异报文解析", "reason": reason})
                    continue

                response = send_iec61850_payload(mutation_bytes, host=host, port=port, timeout=timeout)
                response_hex = response.hex() if response else ""
                classification = self._classify(mutation_bytes, response)

                print(f"[0x{func_code:02X}] Round {idx}/{total_funcs}, Mutation {i}/5: {mutation} -> {classification}")

                if sys.stdout.isatty():
                    _pct = (idx - 1) / total_funcs * 100 if total_funcs else 0
                    sys.stdout.write(f"\r当前进度：[{idx}/{total_funcs}] {_pct:.1f}% | 协议：{_PROTO_NAME} | 功能码：0x{func_code:02X} | 状态：{classification}")
                    sys.stdout.flush()


                results.append({
                    "protocol": "iec61850",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
