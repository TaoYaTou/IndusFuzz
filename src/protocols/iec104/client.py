import sys
import struct
import socket
from src.protocols.base import ProtocolBase


def build_iec104_request(
    type_id=0x64,
    vsq=0x01,
    cot=0x0600,
    origin=0x00,
    common_addr=0x0001,
    ioa=0x000001,
    data=b"",
    tx_seq=1,
    rx_seq=0,
):
    try:
        asdu = bytearray()
        asdu.append(type_id & 0xFF)
        asdu.append(vsq & 0xFF)
        asdu.extend(struct.pack("<H", cot))
        asdu.append(origin & 0xFF)
        asdu.extend(struct.pack("<H", common_addr))
        asdu.extend(struct.pack("<I", ioa)[:3])
        asdu.extend(data)

        ctrl = bytearray()
        ctrl.append(tx_seq & 0xFF)
        ctrl.append((tx_seq >> 8) & 0xFF)
        ctrl.append(rx_seq & 0xFF)
        ctrl.append((rx_seq >> 8) & 0xFF)

        apdu = bytearray()
        apdu.append(0x68)
        apdu.append(len(asdu) + 4)
        apdu.extend(ctrl)
        apdu.extend(asdu)

        return bytes(apdu)
    except Exception as e:
        print(f"[IEC104] build_iec104_request 失败: {type(e).__name__}: {e}")
        return None


def send_iec104_payload(payload, host="127.0.0.1", port=2404, timeout=3):
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
        print(f"[IEC104] 发送失败: {type(e).__name__}: {e}")
        return None


_REQUEST_TYPES = {
    0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x3A, 0x3B, 0x3C,
    0x3D, 0x3E, 0x3F, 0x40, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6A, 0x6B, 0x6E, 0x6F, 0x70, 0x71, 0x78, 0x79, 0x7A, 0x7B,
    0x7C, 0x7D, 0x7E,
}

_PROTO_NAME = "IEC104"
_FUNC_NAME_MAP = {
    0x01: "M_SP_NA_1", 0x02: "M_SP_TA_1", 0x03: "M_DP_NA_1", 0x04: "M_DP_TA_1",
    0x05: "M_ST_NA_1", 0x06: "M_ST_TA_1", 0x07: "M_BO_NA_1", 0x08: "M_BO_TA_1",
    0x09: "M_ME_NA_1", 0x0A: "M_ME_TA_1", 0x0B: "M_ME_NB_1", 0x0C: "M_ME_TB_1",
    0x0D: "M_ME_NC_1", 0x0E: "M_ME_TC_1", 0x0F: "M_IT_NA_1", 0x10: "M_IT_TA_1",
    0x11: "M_EP_TA_1", 0x12: "M_EP_TB_1", 0x13: "M_EP_TC_1", 0x14: "M_PS_NA_1",
    0x15: "M_ME_ND_1",
    0x1E: "M_SP_TB_1", 0x1F: "M_DP_TB_1", 0x20: "M_ST_TB_1", 0x21: "M_BO_TB_1",
    0x22: "M_ME_TD_1", 0x23: "M_ME_TE_1", 0x24: "M_ME_TF_1", 0x25: "M_IT_TB_1",
    0x26: "M_EP_TD_1", 0x27: "M_EP_TE_1", 0x28: "M_EP_TF_1",
    0x2D: "C_SC_NA_1", 0x2E: "C_DC_NA_1", 0x2F: "C_RC_NA_1", 0x30: "C_SE_NA_1",
    0x31: "C_SE_NB_1", 0x32: "C_SE_NC_1", 0x33: "C_BO_NA_1",
    0x3A: "C_SC_TA_1", 0x3B: "C_DC_TA_1", 0x3C: "C_RC_TA_1", 0x3D: "C_SE_TA_1",
    0x3E: "C_SE_TB_1", 0x3F: "C_SE_TC_1", 0x40: "C_BO_TA_1",
    0x46: "M_EI_NA_1",
    0x64: "C_IC_NA_1", 0x65: "C_CI_NA_1", 0x66: "C_RD_NA_1", 0x67: "C_CS_NA_1",
    0x68: "C_TS_NA_1", 0x69: "C_RP_NA_1", 0x6A: "C_CD_NA_1", 0x6B: "C_TS_TA_1",
    0x6E: "P_ME_NA_1", 0x6F: "P_ME_NB_1", 0x70: "P_ME_NC_1", 0x71: "P_AC_NA_1",
    0x78: "F_FR_NA_1", 0x79: "F_SR_NA_1", 0x7A: "F_SC_NA_1", 0x7B: "F_LS_NA_1",
    0x7C: "F_FA_NA_1", 0x7D: "F_SG_NA_1", 0x7E: "F_DR_TA_1",
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


class IEC104Client(ProtocolBase):
    name = "iec104"
    default_port = 2404

    def __init__(self):
        self._sock = None
        self._connected = False
        self._persistent = False
        self._real_host = None
        self._real_port = None
        self._common_addr = 1
        self._timeout = 5
        self._conn_failures = 0

    def get_default_port(self) -> int:
        return self.default_port

    def get_func_codes(self) -> list:
        return list(_REQUEST_TYPES)

    def build_request(self, **kwargs):
        type_id = kwargs.get("type_id", 0x64)
        kwargs.setdefault("common_addr", self._common_addr)
        return build_iec104_request(type_id=type_id, common_addr=kwargs["common_addr"])

    def connect(self, host, port, **kwargs) -> bool:
        self._common_addr = kwargs.get("common_addr", 1)
        self._timeout = kwargs.get("timeout", 5)
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.connect((host, port))
            startdt = bytes([0x68, 0x04, 0x07, 0x00, 0x00, 0x00])
            s.sendall(startdt)
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
            print(f"[IEC104] 已连接真实设备 {host}:{port} (common_addr={self._common_addr})")
            return True
        except Exception as e:
            print(f"[IEC104] 连接失败: {type(e).__name__}: {e}")
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
            return self.connect(self._real_host, self._real_port, common_addr=self._common_addr, timeout=self._timeout)
        return False

    def _recv_frame(self, sock):
        try:
            header = sock.recv(2)
            if not header:
                return b""
            if len(header) < 2 or header[0] != 0x68:
                return header
            length = header[1]
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

    def send_payload(self, payload, host="127.0.0.1", port=2404, timeout=3):
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
        return send_iec104_payload(payload, host=host, port=port, timeout=timeout)

    def parse_response(self, raw) -> dict:
        if not raw:
            return {"raw_hex": "", "raw_len": 0}
        return {"raw_hex": raw.hex(), "raw_len": len(raw)}

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if response[0] != 0x68:
            return "MALFORMED"
        if len(response) >= 7 and response[6] & 0x80:
            return "EXCEPTION"
        return "NORMAL"

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None):
        from src.protocols.iec104.mutator import mutate_payload as local_mutate
        from src.protocols.iec104.llm_mutator import llm_generate_mutations

        total_funcs = len(func_codes)

        for idx, fc_str in enumerate(func_codes, start=1):
            if stop_event and stop_event.is_set():
                return
            try:
                func_code = int(fc_str, 16) if isinstance(fc_str, str) else int(fc_str)
            except (ValueError, TypeError):
                skipped.append({"round": idx, "func_code": fc_str, "reason": "格式无效"})
                continue

            base_payload = build_iec104_request(type_id=func_code, common_addr=self._common_addr)
            if base_payload is None:
                reason = f"TypeID 0x{func_code:02X} 基准报文构造失败"
                print(f"警告：{reason}，跳过")
                skipped.append({"round": idx, "func_code": func_code, "reason": reason})
                build_failures.append({"func_code": func_code, "stage": "基准报文构造", "reason": reason})
                continue

            base_hex = base_payload.hex()
            print(f"\n>>> TypeID 0x{func_code:02X} ({_FUNC_NAME_MAP.get(func_code, 'Unknown')}) 基准报文: {base_hex}")

            mutations = []
            try:
                mutations = llm_generate_mutations(
                    base_hex, count=5,
                    status_collector=llm_status,
                    func_code_str=f'0x{func_code:02X}', stop_event=stop_event)
            except Exception as e:
                print(f"警告：IEC104 LLM 变异异常 {type(e).__name__}: {e}，回退到本地变异")
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
                print(f"警告：TypeID 0x{func_code:02X} {reason}，跳过")
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
                    print(f"警告：TypeID 0x{func_code:02X} {reason}")
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
                    "protocol": "iec104",
                    "round": idx,
                    "func_code": func_code,
                    "mutation": mutation,
                    "response": response_hex,
                    "classification": classification,
                })
