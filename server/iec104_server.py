import os
import sys
import socket
import struct
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 2404
BUFFER_SIZE = 4096

_REQUEST_TYPES = {
    0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x3A, 0x3B, 0x3C,
    0x3D, 0x3E, 0x3F, 0x40, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6A, 0x6B, 0x6E, 0x6F, 0x70, 0x71, 0x78, 0x79, 0x7A, 0x7B,
    0x7C, 0x7D, 0x7E,
}


def _build_response(type_id, vsq, cot, origin, common_addr, ioa):
    resp = bytearray()
    apdu_len = 1 + 1 + 2 + 1 + 2 + 3
    resp.append(0x68)
    resp.append(apdu_len)
    resp.extend(struct.pack("<H", 0x0200))
    resp.extend(struct.pack("<H", 0x0000))
    resp.append(type_id & 0xFF)
    resp.append(vsq & 0xFF)
    resp.extend(struct.pack("<H", cot))
    resp.append(origin & 0xFF)
    resp.extend(struct.pack("<H", common_addr))
    resp.extend(struct.pack("<I", ioa)[:3])
    return bytes(resp)


def _build_error_response(type_id, vsq, origin, common_addr, ioa):
    resp = bytearray()
    apdu_len = 1 + 1 + 2 + 1 + 2 + 3
    resp.append(0x68)
    resp.append(apdu_len)
    resp.extend(struct.pack("<H", 0x0200))
    resp.extend(struct.pack("<H", 0x0000))
    resp.append((type_id | 0x80) & 0xFF)
    resp.append(vsq & 0xFF)
    resp.extend(struct.pack("<H", 0x0000))
    resp.append(origin & 0xFF)
    resp.extend(struct.pack("<H", common_addr))
    resp.extend(struct.pack("<I", ioa)[:3])
    return bytes(resp)


def _parse_frame(data):
    if len(data) >= 11:
        type_id = data[6]
        vsq = data[7]
        cot = struct.unpack("<H", data[8:10])[0]
        origin = data[10]
        common_addr = struct.unpack("<H", data[11:13])[0] if len(data) >= 13 else 0
        ioa = struct.unpack("<I", b"\x00" + data[13:16])[0] if len(data) >= 16 else 0
    else:
        type_id = data[6] if len(data) >= 7 else 0
        vsq = cot = origin = common_addr = ioa = 0
    return type_id, vsq, cot, origin, common_addr, ioa


def _validate(data):
    if len(data) < 6:
        return False, "close", "报文过短"
    if data[0] != 0x68:
        return False, "close", "协议标识错误"
    declared_len = data[1]
    if declared_len > 253:
        return False, "close", f"长度字段超限: {declared_len} > 253"
    if declared_len + 2 != len(data):
        return False, "close", f"长度字段不匹配: 声明 {declared_len}, 实际 {len(data) - 2}"
    if len(data) > 6:
        type_id = data[6]
        if type_id not in _REQUEST_TYPES:
            return False, "exception", f"类型标识 0x{type_id:02X} 不支持"
    return True, None, None


def _handle_client(conn, addr, strict):
    print(f"[IEC104-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            type_id, vsq, cot, origin, common_addr, ioa = _parse_frame(data)

            if strict:
                print(f"[IEC104-从站] 收到 {len(data)} 字节，功能码=0x{type_id:02X}")
                ok, action, reason = _validate(data)
                if not ok:
                    if action == "exception":
                        print(f"[IEC104-从站] 校验失败：{reason}，返回异常响应")
                        try:
                            conn.sendall(_build_error_response(type_id, vsq, origin, common_addr, ioa))
                        except Exception:
                            break
                        continue
                    print(f"[IEC104-从站] 校验失败：{reason}，关闭连接")
                    break
                print(f"[IEC104-从站] 校验通过，返回正常响应")
            else:
                print(f"[IEC104-从站] 收到 {len(data)} 字节")

            resp = _build_response(type_id, vsq, cot, origin, common_addr, ioa)
            try:
                conn.sendall(resp)
            except Exception as e:
                print(f"[IEC104-从站] 发送失败: {type(e).__name__}: {e}")
                break
    except Exception as e:
        print(f"[IEC104-从站] 处理异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[IEC104-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[IEC104-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[IEC104-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[IEC104-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[IEC104-从站] 按 Ctrl+C 停止服务")

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
                print(f"[IEC104-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[IEC104-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[IEC104-从站] 已停止")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2404)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.strict)
