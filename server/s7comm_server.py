"""S7comm 仿真从站 — 三阶段协议状态机

协议层次: TPKT → COTP → ISO 8650 → S7
阶段:   COTP Setup → S7 Setup → DATA (S7 Read/Write/Block Download 等)

client connect() 流程（IndusFuzz S7CommClient）:
  帧1: COTP Setup Connection Request  (type=0x11)  → server 需响应 0xD0 Ack
  帧2: COTP Data + S7 Setup PDU  (type=0x32)     → server 需响应 Setup Ack
  帧3+: COTP Data + ISO-TP + S7 Request          → server 响应

历史（v1.8.3 半成品问题）:
  _handle_client 假设收到的都是 ISO-TP 帧，跳过了 COTP Setup + S7 Setup 阶段，
  导致 client.connect() 里 s.recv(1024) 在 COTP Setup 处就失败（收到的不是 Setup Ack）。
"""

import os
import sys
import socket
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10102
BUFFER_SIZE = 4096

_S7COMM_KNOWN_FUNCS = {0x00, 0x04, 0x05, 0x07, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x28, 0x29, 0xF0}


# ============================================================
# 帧解析辅助
# ============================================================

def _parse_tpkt(data):
    """解析 ISO 8650 TPKT 头，返回 (length, cotp_start_offset) 或 None。"""
    if len(data) < 4:
        return None
    if data[0] != 0x03:
        return None
    tpkt_len = int.from_bytes(data[2:4], "big")
    if tpkt_len < 4:
        return None
    return tpkt_len, 4  # TPKT 固定 4 字节，COTP 从 offset 4 开始


def _cotp_type(data):
    """返回 COTP TPDU 类型字节（在 data[4+header_len_index] 位置）。

    COTP Setup Connection: data[4] = header_len, data[5] = type (0x11/0xD0)
    COTP Data Transfer (fixed): data[4] = 0xF0 (type 在第一个字节)
    """
    if len(data) < 5:
        return None
    if data[4] == 0xF0:
        return 0xF0  # fixed-format Data Transfer
    # variable-format: data[4] = header_len, data[5] = type
    if data[4] == 0xE0 or data[4] == 0xD0 or data[4] == 0xE1 or data[4] == 0xD1:
        # Actually 0xE0 is Data Transfer with explicit header_len
        pass
    # Generic: assume variable-format if first byte not a fixed type
    return data[5] if len(data) > 5 else None


# ============================================================
# COTP 层响应构造
# ============================================================

def _build_cotp_setup_ack(data):
    """响应 COTP Setup Connection Request (0x11) → Acknowledge (0xD0).

    从请求帧里提取 src_ref / dst_ref / tsap，构造对称的 Ack。
    请求帧结构:
      TPKT(4) + COTP_header_len + 0x11 + src_ref(2) + dst_ref(2) + class(1) + params...
    """
    cotp_header_len = data[4]
    src_ref = int.from_bytes(data[5:7], "big")   # e.g. 0x00E0
    dst_ref = int.from_bytes(data[7:9], "big")   # e.g. 0x0001

    # 对称交换 src ↔ dst
    ack = bytearray()
    ack.append(cotp_header_len)   # 与请求相同 header_len
    ack.append(0xD0)               # Acknowledge (0xE0→0xD0, 0x11→0xD0 均对称)
    ack.extend(dst_ref.to_bytes(2, "big"))   # ack's src = req's dst
    ack.extend(src_ref.to_bytes(2, "big"))   # ack's dst = req's src
    ack.append(0x00)
    # 复制请求里的 params（C0/C1/C2），保持对称
    # 这些 params 在 data[11:11+...] 开始，原样复制
    params_start = 11  # TPKT(4) + header_len(1) + type(1) + src_ref(2) + dst_ref(2) + class(1) = 11
    params_end = 4 + cotp_header_len  # data[4] 是 header_len（type byte + params 总长）
    if params_end <= len(data) and params_start < params_end:
        ack.extend(data[params_start:params_end])

    # TPKT 外层
    tpkt_len = 4 + len(ack)
    resp = bytearray([0x03, 0x00])
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(ack)
    return bytes(resp)


def _build_s7_setup_ack(data):
    """响应 S7 Setup (opcode=0x32 param PDU) → S7 Setup Ack.

    提取 COTP Data Transfer 头 + ISO-TP Setup opcode=0x32,
    构造对应的 response。
    """
    # 从请求中抽取 COTP Data header (5 bytes: F0 00 00 80 00)
    cotp_hdr = data[4:9] if len(data) >= 9 else b"\xF0\x00\x00\x80\x00"
    # ISO-TP session header 0x80 之后是 S7 param PDU
    # S7 Setup request 结构 (简化版):
    #   opcode=0x32, reserved=0x01 0x00 0x00 0x00 0x00,
    #   reserved2=0x00 0x08 0x00 0x00, ...
    # S7 Setup response (简化版):
    #   opcode=0x32, 0x03, reserved=0x00 0x00 0x00 0x00,
    #   reserved2=0x00 0x08 0x00 0x00, 0x00 0x00 0x00 0x00
    s7_setup_body = bytes([
        0x32, 0x03, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x08, 0x00, 0x00, 0xF0, 0x00,
        0x00, 0x01, 0x00, 0x01, 0x03, 0xC0,
    ])

    inner = cotp_hdr + s7_setup_body
    tpkt_len = 4 + len(inner)
    resp = bytearray([0x03, 0x00])
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(inner)
    return bytes(resp)


# ============================================================
# S7 ISO-TP 正常请求响应
# ============================================================

def _build_iso_tp_response(data, trans_id, func_code):
    """响应 ISO-TP S7 请求（非 Setup）。"""
    # COTP Data Transfer header — 从请求复制
    cotp_hdr = data[4:9] if len(data) >= 9 else b"\xF0\x00\x00\x80\x00"
    # ISO-TP response body: opcode 与 request 同，func_code 保留，加响应值
    body = bytes([
        func_code & 0xFF,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
    ])
    inner = cotp_hdr + body
    tpkt_len = 4 + len(inner)
    resp = bytearray([0x03, 0x00])
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(inner)
    return bytes(resp)


def _build_error_response(data, trans_id, error_code=0x01):
    """返回 ISO-TP S7 异常响应。"""
    cotp_hdr = data[4:9] if len(data) >= 9 else b"\xF0\x00\x00\x80\x00"
    body = bytes([
        0x03,  # ISO-TP error opcode
        0x85,
        error_code & 0xFF,
        0x00, 0x00, 0x00, 0x00, 0x00,
    ])
    inner = cotp_hdr + body
    tpkt_len = 4 + len(inner)
    resp = bytearray([0x03, 0x00])
    resp.extend(tpkt_len.to_bytes(2, "big"))
    resp.extend(inner)
    return bytes(resp)


def _parse_s7_request(data):
    """从 ISO-TP 帧里提取 trans_id 和 func_code。

    S7 ISO-TP 数据区偏移:
      TPKT 4 + COTP Data 5 + ISO-TP session 1 = 10
      S7 header 从 data[10] 开始:
        data[10] = opcode (0x32 setup, 0x04 param, 0x05 data, ...)
        data[11] = part_id (0x01=request, 0x02=response)
        data[12:14] = trans_id (big)
        data[15] = func_code
    """
    if len(data) < 16:
        return 0, 0
    trans_id = int.from_bytes(data[12:14], "big")
    func_code = data[15]
    return trans_id, func_code


# ============================================================
# 状态机主循环
# ============================================================

def _handle_client(conn, addr, strict):
    print(f"[S7comm-从站] 客户端已连接: {addr} (strict={strict})")
    state = "COTP"  # COTP → S7_SETUP → DATA
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            # 快速探测：是否有有效 TPKT 头
            tpkt = _parse_tpkt(data)
            cotp_tpdu_type = _cotp_type(data) if tpkt else None

            if cotp_tpdu_type in (0x11, 0xE0):  # S7comm 用 0xE0, 经典 ISO 8650 用 0x11
                # ——— COTP Setup Connection Request ———
                print(f"[S7comm-从站] [{state}] 收到 COTP Setup Connection (type=0x11)")
                try:
                    conn.sendall(_build_cotp_setup_ack(data))
                except Exception:
                    break
                state = "S7_SETUP"
                continue

            # 在 COTP 阶段收到非 Setup 的帧 — client 可能跳过了 COTP Setup
            # （某些实现里 client 直接发包，没有显式 COTP Setup）
            if state == "COTP":
                # 先看看是不是已经是 S7 Setup 或 ISO-TP
                if cotp_tpdu_type in (0xF0, 0xE0):
                    # 跳过 COTP Setup，直接进入 S7_SETUP 处理
                    print(f"[S7comm-从站] [{state}] 收到非 Setup 帧，自动进入 S7_SETUP 阶段")
                    state = "S7_SETUP"
                else:
                    # 无法识别，关闭
                    print(f"[S7comm-从站] [{state}] 未知 COTP 类型 0x{cotp_tpdu_type:02X}，关闭")
                    break
                    # fall through to state-specific handling

            if state == "S7_SETUP":
                # ——— S7 Setup Request ———
                # S7 Setup 的特征: COTP Data Transfer (0xF0) + ISO-TP opcode=0x32 + part_id=0x01
                if (cotp_tpdu_type == 0xF0
                        and len(data) >= 13
                        and data[10] == 0x32
                        and data[11] == 0x01):
                    print(f"[S7comm-从站] [{state}] 收到 S7 Setup (opcode=0x32)")
                    try:
                        conn.sendall(_build_s7_setup_ack(data))
                    except Exception:
                        break
                    state = "DATA"
                    continue
                # 兼容：某些 client 发完 COTP Setup 后直接发 ISO-TP 正常请求
                if cotp_tpdu_type == 0xF0 and len(data) >= 16:
                    print(f"[S7comm-从站] [{state}] 收到非 Setup ISO-TP 帧，自动进入 DATA 阶段")
                    state = "DATA"
                    # fall through

            if state == "DATA":
                # ——— ISO-TP S7 正常请求 ———
                if cotp_tpdu_type == 0xF0 and len(data) >= 16:
                    trans_id, func_code = _parse_s7_request(data)
                    print(f"[S7comm-从站] [{state}] transId={trans_id}, func=0x{func_code:02X}")
                    if strict and func_code not in _S7COMM_KNOWN_FUNCS:
                        try:
                            conn.sendall(_build_error_response(data, trans_id, 0x01))
                        except Exception:
                            break
                        continue
                    try:
                        conn.sendall(_build_iso_tp_response(data, trans_id, func_code))
                    except Exception as e:
                        print(f"[S7comm-从站] 发送失败: {type(e).__name__}: {e}")
                        break
                else:
                    print(f"[S7comm-从站] [{state}] 帧格式不完整 ({len(data)} bytes)，跳过")
                    continue
    except Exception as e:
        print(f"[S7comm-从站] 处理客户端 {addr} 异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[S7comm-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[S7comm-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[S7comm-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[S7comm-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[S7comm-从站] 按 Ctrl+C 停止服务")

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
                print(f"[S7comm-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[S7comm-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[S7comm-从站] 已停止")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10102)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.strict)
