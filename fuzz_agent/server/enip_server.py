import os
import sys
import socket
import struct
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 44818
BUFFER_SIZE = 4096

_REQUEST_SERVICES = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0D, 0x0E, 0x10, 0x11, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A,
    0x1B, 0x1C, 0x4C, 0x4D, 0x4E, 0x52, 0x54,
}

_KNOWN_COMMANDS = {0x63, 0x64, 0x65, 0x66, 0x6F}


def _build_response(service_code, session_handle, sender_context):
    resp = bytearray()
    command = 0x65
    if service_code == 0x01 or service_code == 0x02 or service_code == 0x04 or service_code == 0x05:
        command = 0x6F

    cip_resp = bytearray()
    cip_resp.append(service_code | 0x80)
    cip_resp.append(0x02)
    cip_resp.append(0x00)
    cip_resp.append(0x00)

    resp.extend(struct.pack("<H", command))
    resp.extend(struct.pack("<H", len(cip_resp)))
    resp.extend(struct.pack("<I", session_handle))
    resp.extend(struct.pack("<I", 0x00000000))
    resp.extend(sender_context[:8].ljust(8, b"\x00"))
    resp.extend(struct.pack("<I", 0x00000000))
    resp.extend(cip_resp)
    return bytes(resp)


def _build_error_response(command, service_code, session_handle, sender_context, status=0x08):
    cip_resp = bytearray()
    cip_resp.append((service_code | 0x80) & 0xFF)
    cip_resp.append(0x02)
    cip_resp.append(status & 0xFF)
    cip_resp.append(0x00)

    resp = bytearray()
    resp.extend(struct.pack("<H", command))
    resp.extend(struct.pack("<H", len(cip_resp)))
    resp.extend(struct.pack("<I", session_handle))
    resp.extend(struct.pack("<I", 0x00000000))
    resp.extend(sender_context[:8].ljust(8, b"\x00"))
    resp.extend(struct.pack("<I", 0x00000000))
    resp.extend(cip_resp)
    return bytes(resp)


def _parse_frame(data):
    session_handle = struct.unpack("<I", data[4:8])[0] if len(data) >= 8 else 0
    sender_context = data[12:20] if len(data) >= 20 else b"\x00" * 8
    service_code = data[24] if len(data) > 24 else 0
    command = struct.unpack("<H", data[0:2])[0] if len(data) >= 2 else 0
    return command, session_handle, sender_context, service_code


def _validate(data):
    if len(data) < 26:
        return False, "close", "报文过短"
    command = struct.unpack("<H", data[0:2])[0]
    if command not in _KNOWN_COMMANDS:
        return False, "close", f"ENIP 命令 0x{command:04X} 不支持"
    declared_len = struct.unpack("<H", data[2:4])[0]
    if declared_len + 24 != len(data):
        return False, "close", f"长度字段不匹配: 声明 {declared_len}, 实际 {len(data) - 24}"
    if len(data) > 24:
        service_code = data[24]
        if service_code not in _REQUEST_SERVICES:
            return False, "exception", f"CIP 服务码 0x{service_code:02X} 不支持"
    return True, None, None


def _handle_client(conn, addr, strict):
    print(f"[ENIP-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            command, session_handle, sender_context, service_code = _parse_frame(data)

            if strict:
                print(f"[ENIP-从站] 收到 {len(data)} 字节，功能码=0x{service_code:02X}")
                ok, action, reason = _validate(data)
                if not ok:
                    if action == "exception":
                        print(f"[ENIP-从站] 校验失败：{reason}，返回异常响应")
                        try:
                            conn.sendall(_build_error_response(command, service_code, session_handle, sender_context))
                        except Exception:
                            break
                        continue
                    print(f"[ENIP-从站] 校验失败：{reason}，关闭连接")
                    break
                print(f"[ENIP-从站] 校验通过，返回正常响应")
            else:
                print(f"[ENIP-从站] 收到 {len(data)} 字节")

            resp = _build_response(service_code, session_handle, sender_context)
            try:
                conn.sendall(resp)
            except Exception as e:
                print(f"[ENIP-从站] 发送失败: {type(e).__name__}: {e}")
                break
    except Exception as e:
        print(f"[ENIP-从站] 处理异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[ENIP-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[ENIP-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[ENIP-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[ENIP-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[ENIP-从站] 按 Ctrl+C 停止服务")

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
                print(f"[ENIP-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[ENIP-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[ENIP-从站] 已停止")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=44818)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.strict)
