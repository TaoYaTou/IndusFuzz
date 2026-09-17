import os
import sys
import socket
import struct
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 20000
BUFFER_SIZE = 4096

_KNOWN_FUNCS = {0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
                0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13,
                0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D,
                0x1E}


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


def _build_response(length_byte, control, func_code, dest, src):
    resp = bytearray()
    resp.append(0x05)
    resp.append(0x64)
    resp.append(length_byte)
    resp.append(control)
    resp.extend(struct.pack(">H", func_code & 0x7F))
    resp.extend(struct.pack("<H", src))
    resp.extend(struct.pack("<H", dest))
    crc = _crc16(resp)
    resp.extend(struct.pack("<H", crc))
    return bytes(resp)


def _build_error_response(control, func_code, dest, src, iin=0x0040):
    resp = bytearray()
    resp.append(0x05)
    resp.append(0x64)
    resp.append(0x07)
    resp.append(control)
    resp.extend(struct.pack(">H", (func_code & 0xFF) | 0x80))
    resp.extend(struct.pack("<H", src))
    resp.extend(struct.pack("<H", dest))
    resp.extend(struct.pack("<H", iin))
    crc = _crc16(resp)
    resp.extend(struct.pack("<H", crc))
    return bytes(resp)


def _parse_frame(data):
    length = data[2] if len(data) > 2 else 0
    control = data[3] if len(data) > 3 else 0
    func = ((data[4] << 8) | data[5]) if len(data) > 5 else 0
    dest = struct.unpack("<H", data[6:8])[0] if len(data) >= 8 else 0
    src = struct.unpack("<H", data[8:10])[0] if len(data) >= 10 else 0
    return length, control, func, dest, src


def _validate(data):
    if len(data) < 12:
        return False, "close", "报文过短"
    if data[0] != 0x05 or data[1] != 0x64:
        return False, "close", "协议标识错误"
    declared_len = data[2]
    if declared_len + 7 != len(data):
        return False, "close", f"长度字段不匹配: 声明 {declared_len}, 实际 {len(data) - 7}"
    func_code = (data[4] << 8) | data[5]
    if func_code > 0xFF or data[5] not in _KNOWN_FUNCS:
        return False, "exception", f"功能码 0x{func_code:04X} 不支持"
    return True, None, None


def _handle_client(conn, addr, strict):
    print(f"[DNP3-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            length, control, func, dest, src = _parse_frame(data)

            if strict:
                print(f"[DNP3-从站] 收到 {len(data)} 字节，功能码=0x{func:04X}")
                ok, action, reason = _validate(data)
                if not ok:
                    if action == "exception":
                        print(f"[DNP3-从站] 校验失败：{reason}，返回异常响应")
                        try:
                            conn.sendall(_build_error_response(control, func, dest, src))
                        except Exception:
                            break
                        continue
                    print(f"[DNP3-从站] 校验失败：{reason}，关闭连接")
                    break
                print(f"[DNP3-从站] 校验通过，返回正常响应")
            else:
                print(f"[DNP3-从站] 收到 {len(data)} 字节")

            resp = _build_response(length, control, func, dest, src)
            try:
                conn.sendall(resp)
            except Exception as e:
                print(f"[DNP3-从站] 发送失败: {type(e).__name__}: {e}")
                break
    except Exception as e:
        print(f"[DNP3-从站] 处理异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[DNP3-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[DNP3-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[DNP3-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[DNP3-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[DNP3-从站] 按 Ctrl+C 停止服务")

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
                print(f"[DNP3-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[DNP3-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[DNP3-从站] 已停止")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=20000)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.strict)
