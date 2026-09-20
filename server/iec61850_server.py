"""IEC61850 MMS 仿真从站 — 两阶段协议状态机

协议层次: TPKT → COTP → ISO 8650 Session → MMS PDU (ASN.1 BER)
阶段:   COTP Setup → DATA (MMS Initiate / Read / Write 等)

client connect() 流程（IndusFuzz IEC61850Client）:
  帧1: COTP Setup Connection Request (type=0xE0)  → server 需响应 0xD0 Ack
  帧2: COTP Data Transfer + MMS Initiate PDU      → server 需响应 0x82 Initiate Ack
  帧3+: COTP Data Transfer + MMS Request          → server 响应

历史（v1.8.3 半成品问题）:
  1. 跳过 COTP Setup Connection (type=0xE0)，直接假设收到的是 COTP Data Transfer
  2. MMS PDU offset 算错：原代码用 data[10] 找 PDU type，实际应该是 data[9]
     - TPKT(4) + COTP Data Transfer fixed(5) = 9，MMS 从 data[9] 开始
  3. _validate L94 错误长度检查：对 fixed-format COTP Data Transfer
     data[5]=0x00（不是 header_len），但代码把它当 header_len 与 len(data)-10 比较
"""

import os
import sys
import socket
import struct
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 102
BUFFER_SIZE = 4096

# MMS Request PDU 类型
_REQUEST_TYPES = {
    0x81, 0x83, 0x86, 0xA8, 0xAB, 0xAC, 0xAF,
    0xB0, 0xB2, 0xB5, 0xB7, 0xB9, 0xBC,
    0xBF, 0xC1, 0xC2, 0xC5,
}
# Initiate 用 type 0x81 → Response 0x82
_INITIATE_PAIR = {0x81: 0x82}
# General response mapping (request → response)
_PDU_RESPONSE_MAP = {
    0x83: 0x84,   # confirmed-error → error
    0x86: 0x87,   # unconfirmed-response → 0x87 or 0x88
    0xAC: 0xAD,   # cancel → cancel response
    0xAB: 0xAA,   # confirmed → cancel? no, 0xAB is cancel-request
    0xB0: 0xB1,   # Read → Read Response
    0xB2: 0xB3,   # Write → Write Response
    0xB5: 0xB6,   # Get Name List → Response
    0xB7: 0xB8,   # Identify → Identify Response
    0xB9: 0xBA,   # Rename → Rename Response
    0xBC: 0xBD,   # Status → Status Response
    0xBF: 0xC0,   # Get File → Response
    0xC1: 0xC3,   # Set File → Response
    0xC2: 0xC4,   # Delete File → Response
    0xC5: 0xC6,   # Get File Attr → Response
}
# 未在映射中的，回退到 request+1
_FALLBACK_RESP_OFFSET = 1


# ============================================================
# 帧解析
# ============================================================

def _parse_tpkt(data):
    """返回 (tpkt_length, cotp_start=4, cotp_type) 或 None."""
    if len(data) < 5:
        return None
    if data[0] not in (0x30, 0x03):  # Connectionless=0x30, Connection Oriented=0x03
        return None
    tpkt_len = struct.unpack(">H", data[2:4])[0]
    if tpkt_len < 4 or tpkt_len > 4096:
        return None
    # COTP 类型判断
    # 对于 fixed-format (type 在 offset 4):
    #   0xF0 = Data Transfer (class 0, no seq, last), 固定 5 字节头
    #   0xE0 = Data Transfer with seq (class 1), 可变长头
    # 对于 variable-format (data[4] = header_len, data[5] = type):
    #   0x11 = Setup Connection Request, 0xD0 = Setup Connection Ack
    #   0x21 = Disconnect Request, 0x80 = Disconnect Ack (MMS uses 0x80 sometimes)
    cotp_fixed = data[4]
    if cotp_fixed in (0xF0, 0xE0):
        return tpkt_len, cotp_fixed
    # 假设是 variable-format
    if len(data) >= 6:
        return tpkt_len, data[5]  # 0x11, 0xD0, etc.
    return None


def _cotp_data_hdr_len(cotp_type, data):
    """COTP header 长度（含 type + params）。

    fixed-format Data Transfer (0xF0, 0xE0): 固定 5 字节
    variable-format: data[4] 就是 header_len
    """
    if cotp_type in (0xF0, 0xE0):
        return 5
    if len(data) >= 5:
        return data[4]  # variable-format 第一个字节是 header_len
    return 5  # default


def _mms_pdu_offset(cotp_type, data):
    """返回 MMS PDU 在 data 里的起始 offset。

    TPKT(4) + COTP_header_len + ISO_Session(1 if MMS over COTP, else 0)
    对于 fixed-format Data Transfer: 4 + 5 + 1 = 10
    对于 variable-format Setup (不会有 MMS): None
    """
    if cotp_type in (0xF0, 0xE0):
        return 4 + 5 + 1  # TPKT4 + COTP5 + Session1(0x80)
    # ISO 8650 Session header 0x80 可能不在 COTP Setup 后面
    header_len = _cotp_data_hdr_len(cotp_type, data)
    # COTP Data Transfer with explicit header_len (e.g. 0xE0)
    if cotp_type == 0xE0:
        return 4 + header_len + 1
    return None  # Setup/Disconnect 没有 MMS


# ============================================================
# COTP Setup Connection Ack (0xD0)
# ============================================================

def _build_cotp_setup_ack(data):
    """响应 COTP Setup Connection Request (0xE0/0x11 → 统一按 type byte)。

    请求结构:
      TPKT(4) + header_len(1) + 0xE0 + src_ref(2) + dst_ref(2) + class(1) + params...
    Ack 结构 (对称交换 src ↔ dst):
      TPKT(4) + header_len(1) + 0xD0 + dst_ref(2) + src_ref(2) + class(1) + params...
    """
    header_len = data[4]
    src_ref = struct.unpack(">H", data[5:7])[0] if len(data) >= 7 else 0
    dst_ref = struct.unpack(">H", data[7:9])[0] if len(data) >= 9 else 0

    ack = bytearray()
    ack.append(header_len)
    ack.append(0xD0)
    ack.extend(dst_ref.to_bytes(2, "big"))
    ack.extend(src_ref.to_bytes(2, "big"))
    ack.append(0x00)  # class=0, options=0
    # 复制 params
    params_start = 11  # TPKT(4) + header_len(1) + type(1) + src_ref(2) + dst_ref(2) + class(1)
    params_end = 4 + header_len  # header_len 从 data[4] 开始，到 data[4+header_len-1]
    if params_end <= len(data) and params_start < params_end:
        ack.extend(data[params_start:params_end])

    tpkt_len = 4 + len(ack)
    resp = bytearray([data[0], data[1]])  # 跟随请求的 TPKT 起始字节 (0x30 or 0x03)
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(ack)
    return bytes(resp)


# ============================================================
# MMS 响应构造
# ============================================================

def _build_mms_response(pdu_type):
    """构造 MMS PDU 响应帧（TPKT + COTP Data Transfer + ISO Session + MMS Response）。"""
    # MMS PDU 响应 tag
    resp_pdu = _PDU_RESPONSE_MAP.get(pdu_type, pdu_type + _FALLBACK_RESP_OFFSET)

    mms = bytearray()
    if pdu_type == 0x81:  # Initiate
        # Initiate Ack: 0x82 0x02 0x00 0x01 (简化 BER: tag+len+content)
        mms.append(0x82)
        mms.append(0x02)
        mms.append(0x00)
        mms.append(0x01)
    else:
        # Generic simple response: tag + BER-length(02) + content(0x00 0x01)
        mms.append(resp_pdu)
        mms.append(0x02)
        mms.append(0x00)
        mms.append(0x01)

    cotp = bytearray([0xF0, 0x00, 0x00, 0x80, 0x00])  # fixed-format Data Transfer
    iso_session = bytes([0x80])                        # ISO 8650 Session header

    # 如果 MMS 在 ISO Session 内部就用，或者作为独立 COTP Data 后面
    inner = cotp + iso_session + bytes(mms)

    tpkt_len = 4 + len(inner)
    resp = bytearray([data[0], data[1]])  # 跟随请求的 TPKT 起始字节 (0x30 or 0x03)
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(inner)
    return bytes(resp)


def _build_mms_error():
    """返回 MMS Error Service PDU (0xA2)."""
    mms = bytes([0xA2, 0x03, 0x02, 0x01, 0x00])  # tag=0xA2, len=3, err_class=0x02, err_code=0x01
    cotp = bytearray([0xF0, 0x00, 0x00, 0x80, 0x00])
    iso_session = bytes([0x80])
    inner = cotp + iso_session + mms

    tpkt_len = 4 + len(inner)
    resp = bytearray([data[0], data[1]])  # 跟随请求的 TPKT 起始字节 (0x30 or 0x03)
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(inner)
    return bytes(resp)


# ============================================================
# 状态机主循环
# ============================================================

def _handle_client(conn, addr, strict):
    print(f"[IEC61850-从站] 客户端已连接: {addr} (strict={strict})")
    state = "COTP"  # COTP Setup → DATA
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            parsed = _parse_tpkt(data)
            if parsed is None:
                print(f"[IEC61850-从站] [{state}] 无效 TPKT 头 (len={len(data)})")
                break

            tpkt_len, cotp_type = parsed

            # ——— COTP Setup Connection Request (0xE0 / 0x11) ———
            if cotp_type in (0xE0, 0x11):
                print(f"[IEC61850-从站] [{state}] 收到 COTP Setup Connection (type=0x{cotp_type:02X})")
                try:
                    conn.sendall(_build_cotp_setup_ack(data))
                except Exception:
                    break
                state = "DATA"
                continue

            if state == "COTP":
                # 在 COTP 阶段收到非 Setup 的帧 — 自动跳过 Setup 阶段
                if cotp_type in (0xF0, 0xE0):
                    print(f"[IEC61850-从站] [{state}] 跳过 COTP Setup，直接进入 DATA")
                    state = "DATA"
                else:
                    print(f"[IEC61850-从站] [{state}] 未知 COTP 类型 0x{cotp_type:02X}")
                    break

            if state == "DATA":
                # ——— COTP Data Transfer ———
                mms_off = _mms_pdu_offset(cotp_type, data)
                if mms_off is None or mms_off >= len(data):
                    print(f"[IEC61850-从站] [{state}] MMS offset={mms_off} 无效 (data={len(data)} bytes)")
                    continue
                pdu_type = data[mms_off]

                print(f"[IEC61850-从站] [{state}] cotp=0x{cotp_type:02X}, MMS PDU=0x{pdu_type:02X}")

                if strict and pdu_type not in _REQUEST_TYPES:
                    try:
                        conn.sendall(_build_mms_error())
                    except Exception:
                        break
                    continue

                try:
                    conn.sendall(_build_mms_response(pdu_type))
                except Exception as e:
                    print(f"[IEC61850-从站] 发送失败: {type(e).__name__}: {e}")
                    break
    except Exception as e:
        print(f"[IEC61850-从站] 处理异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[IEC61850-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[IEC61850-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[IEC61850-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[IEC61850-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[IEC61850-从站] 按 Ctrl+C 停止服务")

    try:
        while True:
            try:
                conn, addr = server_sock.accept()
                conn.settimeout(30)
                t = threading.Thread(target=_handle_client, args=(conn, addr, strict), daemon=True)
                t.start()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[IEC61850-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[IEC61850-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[IEC61850-从站] 已停止")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=102)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.strict)
