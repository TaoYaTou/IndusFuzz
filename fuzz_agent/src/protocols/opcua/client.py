import sys
import socket
import struct
from src.protocols.base import ProtocolBase


def build_opcua_hello(endpoint="opc.tcp://localhost:4840"):
    try:
        body = bytearray()
        url_bytes = endpoint.encode("utf-8")
        body.extend(struct.pack("<I", len(url_bytes)))
        body.extend(url_bytes)
        body.extend(struct.pack("<I", 65536))
        body.extend(struct.pack("<I", 65536))
        body.extend(struct.pack("<I", 16777216))
        body.extend(struct.pack("<I", 256))
        msg = bytearray()
        msg.extend(b"HELLO")
        msg.extend(struct.pack("<I", len(body)))
        msg.extend(body)
        return bytes(msg)
    except Exception as e:
        print(f"[OPCUA] build_hello 失败: {type(e).__name__}: {e}")
        return None


def build_opcua_msg(service_node_id, request_id=1, request_body=None):
    try:
        msg = bytearray()
        body_len = len(request_body) if request_body else 0
        chunk_header = 8
        msg.extend(b"MSG")
        msg.extend(struct.pack("<I", 8 + chunk_header + body_len))
        msg.append(0x46)
        msg.append(0x00)
        msg.extend(struct.pack("<I", request_id))
        msg.extend(struct.pack("<I", request_id))
        if request_body:
            msg.extend(request_body)
        return bytes(msg)
    except Exception as e:
        print(f"[OPCUA] build_msg 失败: {type(e).__name__}: {e}")
        return None


def build_opcua_request(service_node_id, request_id=1):
    try:
        body = bytearray()
        body.extend(struct.pack("<I", request_id))
        body.extend(struct.pack("<I", 3000))
        body.append(0x00)
        body.append(0x00)
        body.extend(b"\x00" * 2)
        body.append(0x00)
        body.append(0x00)
        body.append(0x00)
        body.append(0x00)
        body.extend(struct.pack("<Q", 0))
        body.extend(struct.pack("<I", 0))
        body.append(0x00)
        body.append(0x00)
        body.append(0x00)
        body.extend(struct.pack("<I", service_node_id))
        return build_opcua_msg(service_node_id, request_id, bytes(body))
    except Exception as e:
        print(f"[OPCUA] build_opcua_request 失败: {type(e).__name__}: {e}")
        return None


def send_opcua_payload(payload, host="127.0.0.1", port=4840, timeout=3):
    if payload is None:
        return None
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            hello = build_opcua_hello()
            if hello:
                try:
                    s.sendall(hello)
                    s.recv(4096)
                except Exception:
                    pass
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
        print(f"[OPCUA] 发送失败: {type(e).__name__}: {e}")
        return None


_PROTO_NAME = "OPCUA"
_SERVICE_NAMES = {
    446: "OpenSecureChannel", 447: "CloseSecureChannel",
    461: "CreateSession", 462: "ActivateSession", 463: "CloseSession", 464: "Cancel",
    486: "AddNodes", 487: "AddReferences", 488: "DeleteNodes", 489: "DeleteReferences",
    525: "Browse", 526: "BrowseNext", 527: "TranslateBrowsePathsToNodeIds",
    528: "RegisterNodes", 529: "UnregisterNodes",
    629: "Read", 630: "HistoryRead", 673: "Write", 674: "HistoryUpdate",
    712: "Call",
    749: "CreateMonitoredItems", 750: "ModifyMonitoredItems",
    751: "SetMonitoringMode", 752: "DeleteMonitoredItems",
    787: "CreateSubscription", 788: "ModifySubscription",
    789: "SetPublishingMode", 791: "DeleteSubscriptions",
}

_REQUEST_SERVICES = set(_SERVICE_NAMES.keys())


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


class OPCUAClient(ProtocolBase):
    name = "opcua"
    default_port = 4840

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        return sorted(_REQUEST_SERVICES)

    def build_request(self, **kwargs):
        sid = kwargs.get("service_node_id", 446)
        return build_opcua_request(service_node_id=sid)

    def send_payload(self, payload, host="127.0.0.1", port=4840, timeout=3):
        return send_opcua_payload(payload, host=host, port=port, timeout=timeout)

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0}
        return {"raw_hex": raw.hex(), "raw_len": len(raw)}

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if len(response) < 4:
            return "MALFORMED"
        prefix = response[:3]
        if prefix == b"ERR":
            return "EXCEPTION"
        if prefix == b"MSG":
            return "NORMAL"
        if prefix == b"ACK":
            return "ACK"
        if prefix == b"HEL":
            return "HELLO_ECHO"
        return f"OTHER_{prefix.hex()}"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
        from src.protocols.opcua.mutator import mutate_payload as local_mutate
        from src.protocols.opcua.llm_mutator import llm_generate_mutations

        total_funcs = len(func_codes)

        for idx, fc_str in enumerate(func_codes, start=1):
            if stop_event and stop_event.is_set():
                return
            try:
                func_code = int(fc_str) if not isinstance(fc_str, str) else int(fc_str, 16) if "x" in fc_str.lower() else int(fc_str)
            except (ValueError, TypeError):
                skipped.append({"round": idx, "func_code": fc_str, "reason": "格式无效"})
                continue

            base_payload = build_opcua_request(service_node_id=func_code)
            if base_payload is None:
                reason = f"Service {func_code} 基准报文构造失败"
                print(f"警告：{reason}，跳过")
                skipped.append({"round": idx, "func_code": func_code, "reason": reason})
                build_failures.append({"func_code": func_code, "stage": "基准报文构造", "reason": reason})
                continue

            base_hex = base_payload.hex()
            svc_name = _SERVICE_NAMES.get(func_code, "Unknown")
            print(f"\n>>> Service {func_code} ({svc_name}) 基准报文: {base_hex}")

            mutations = []
            try:
                mutations = llm_generate_mutations(
                    base_hex, count=5,
                    status_collector=llm_status,
                    func_code_str=f'0x{func_code:02X}')
            except Exception as e:
                print(f"警告：OPCUA LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
                mutations = []

            if len(mutations) < 5:
                if mutations:
                    print(f"[OPCUA] LLM 只生成了 {len(mutations)} 个变异，补齐到 5 个")
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
                    print("[OPCUA] LLM 未生成变异，使用本地变异回退")
                    if llm_status:
                        llm_status.on_fallback_only(f"0x{func_code:02X}")
                    mutations = _generate_local_fallback(base_payload, base_hex, local_mutate, count=5)

            if not mutations:
                reason = "无有效变异"
                print(f"警告：Service {func_code} {reason}，跳过")
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
                    print(f"警告：Service {func_code} {reason}")
                    build_failures.append({"func_code": func_code, "stage": "变异报文解析", "reason": reason})
                    continue

                response = send_opcua_payload(mutation_bytes, host=host, port=port, timeout=timeout)
                response_hex = response.hex() if response else ""
                classification = self._classify(mutation_bytes, response)

                print(f"[{func_code}] Round {idx}/{total_funcs}, Mutation {i}/5: {mutation} -> {classification}")

                if sys.stdout.isatty():
                    _pct = (idx - 1) / total_funcs * 100 if total_funcs else 0
                    sys.stdout.write(f"\r当前进度：[{idx}/{total_funcs}] {_pct:.1f}% | 协议：{_PROTO_NAME} | 功能码：0x{func_code:02X} | 状态：{classification}")
                    sys.stdout.flush()


                results.append({
                    "protocol": "opcua",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
