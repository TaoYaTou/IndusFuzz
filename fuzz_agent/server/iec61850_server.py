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

_REQUEST_TYPES = {
    0x81, 0x83, 0x86, 0xA8, 0xAB, 0xAC, 0xAF,
    0xB0, 0xB2, 0xB5, 0xB7, 0xB9, 0xBC,
    0xBF, 0xC1, 0xC2, 0xC5,
}


def _build_response(pdu_type):
    resp = bytearray()
    mms = bytearray()
    if pdu_type in (0xB0, 0xB5, 0xB7, 0xBC, 0xBF, 0xC5):
        resp_pdu = pdu_type + 1
    elif pdu_type in (0xB2, 0xC1, 0xC2):
        resp_pdu = 0xB3 if pdu_type == 0xB2 else (0xC3 if pdu_type == 0xC1 else 0xC4)
    elif pdu_type == 0x81:
        resp_pdu = 0x82
    else:
        resp_pdu = 0x84

    mms.append(resp_pdu)
    mms.append(0x02)
    mms.append(0x00)
    mms.append(0x01)

    cotp = bytearray()
    cotp.append(0xF0)
    cotp.append(len(mms))
    cotp.append(0x00)
    cotp.append(0x00)
    cotp.append(0x80)
    cotp.append(0x00)

    tpkt_len = len(cotp) + len(mms) + 4
    resp.append(0x30)
    resp.append(0x00)
    resp.append((tpkt_len >> 8) & 0xFF)
    resp.append(tpkt_len & 0xFF)
    resp.extend(cotp)
    resp.extend(mms)
    return bytes(resp)


def _build_error_response(error_class=0x02, error_code=0x01):
    mms = bytearray()
    mms.append(0xA2)
    mms.append(0x03)
    mms.append(error_class & 0xFF)
    mms.append(error_code & 0xFF)
    mms.append(0x00)

    cotp = bytearray()
    cotp.append(0xF0)
    cotp.append(len(mms))
    cotp.append(0x00)
    cotp.append(0x00)
    cotp.append(0x80)
    cotp.append(0x00)

    tpkt_len = len(cotp) + len(mms) + 4
    resp = bytearray()
    resp.append(0x30)
    resp.append(0x00)
    resp.append((tpkt_len >> 8) & 0xFF)
    resp.append(tpkt_len & 0xFF)
    resp.extend(cotp)
    resp.extend(mms)
    return bytes(resp)


def _validate(data):
    if len(data) < 12:
        return False, "close", "报文过短"
    if data[0] != 0x30:
        return False, "close", "TPKT 起始字节错误"
    declared_len = struct.unpack(">H", data[2:4])[0]
    if declared_len != len(data):
        return False, "close", f"TPKT 长度字段不匹配: 声明 {declared_len}, 实际 {len(data)}"
    if data[4] not in (0xF0, 0xE0):
        return False, "close", f"COTP 类型 0x{data[4]:02X} 不支持"
    if data[5] != len(data) - 10:
        return False, "close", f"COTP 长度字段不匹配: 声明 {data[5]}, 实际 {len(data) - 10}"
    pdu_type = data[10]
    if pdu_type not in _REQUEST_TYPES:
        return False, "exception", f"MMS PDU 0x{pdu_type:02X} 不支持"
    return True, None, None


def _handle_client(conn, addr, strict):
    print(f"[IEC61850-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            pdu_type = data[10] if len(data) > 10 else 0

            if strict:
                print(f"[IEC61850-从站] 收到 {len(data)} 字节，功能码=0x{pdu_type:02X}")
                ok, action, reason = _validate(data)
                if not ok:
                    if action == "exception":
                        print(f"[IEC61850-从站] 校验失败：{reason}，返回异常响应")
                        try:
                            conn.sendall(_build_error_response())
                        except Exception:
                            break
                        continue
                    print(f"[IEC61850-从站] 校验失败：{reason}，关闭连接")
                    break
                print(f"[IEC61850-从站] 校验通过，返回正常响应")
            else:
                print(f"[IEC61850-从站] 收到 {len(data)} 字节")

            resp = _build_response(pdu_type)
            try:
                conn.sendall(resp)
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
