import os, sys, socket, struct, threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 4840
BUFFER_SIZE = 4096

_REQUEST_SERVICES = {
    446, 447, 461, 462, 463, 464,
    486, 487, 488, 489,
    525, 526, 527, 528, 529,
    629, 630, 673, 674,
    712,
    749, 750, 751, 752,
    787, 788, 789, 791,
}


def _build_ack_response():
    ack = bytearray()
    ack.extend(b"ACK")
    ack.extend(struct.pack("<I", 4))
    ack.extend(struct.pack("<I", 0))
    return bytes(ack)


def _build_msg_response(request_id):
    resp = bytearray()
    body = bytearray()
    body.extend(struct.pack("<I", request_id))
    body.extend(struct.pack("<I", 0))
    body.extend(b"\x00" * 16)
    body.append(0x00)
    body.append(0x00)
    body.append(0x00)
    body.append(0x00)
    body.extend(struct.pack("<Q", 0))
    body.extend(struct.pack("<I", 0))
    body.append(0x00)
    body.append(0x00)
    body.append(0x00)
    body.extend(struct.pack("<I", 0x00000000))
    body.extend(struct.pack("<I", 0))
    resp.extend(b"MSG")
    resp.extend(struct.pack("<I", 8 + 8 + len(body)))
    resp.append(0x46)
    resp.append(0x00)
    resp.extend(struct.pack("<I", request_id))
    resp.extend(struct.pack("<I", request_id))
    resp.extend(body)
    return bytes(resp)


def _build_err_response(error_code=0x80B40000):
    resp = bytearray()
    resp.extend(b"ERR")
    resp.extend(struct.pack("<I", 12))
    resp.extend(struct.pack("<I", error_code))
    return bytes(resp)


def _parse_frame(data):
    prefix = data[:3] if len(data) >= 3 else b""
    request_id = struct.unpack("<I", data[9:13])[0] if len(data) >= 13 else 1
    service_id = struct.unpack("<I", data[-4:])[0] if len(data) >= 17 else 0
    return prefix, request_id, service_id


def _validate(data):
    if len(data) < 8:
        return False, "close", "报文过短"
    prefix = data[:3]
    if prefix == b"HEL":
        if len(data) < 13:
            return False, "close", "Hello 报文过短"
        declared_len = struct.unpack("<I", data[5:9])[0]
        if declared_len + 9 != len(data):
            return False, "close", f"消息大小字段不匹配: 声明 {declared_len}, 实际 {len(data) - 9}"
        return True, None, None
    if prefix == b"ACK":
        return True, None, None
    if prefix == b"ERR":
        return True, None, None
    if prefix == b"MSG":
        if len(data) < 17:
            return False, "close", "MSG 报文过短"
        declared_len = struct.unpack("<I", data[3:7])[0]
        if declared_len + 1 != len(data):
            return False, "close", f"消息大小字段不匹配: 声明 {declared_len}, 实际 {len(data) - 1}"
        request_id = struct.unpack("<I", data[9:13])[0]
        if request_id == 0:
            return False, "exception", "请求 ID 为 0"
        service_id = struct.unpack("<I", data[-4:])[0]
        if service_id not in _REQUEST_SERVICES:
            return False, "exception", f"ServiceNodeId {service_id} 不支持"
        return True, None, None
    return False, "close", f"未知消息类型 {prefix}"


def _handle_client(conn, addr, strict):
    print(f"[OPCUA-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            prefix, request_id, service_id = _parse_frame(data)

            if strict:
                if prefix == b"HEL":
                    print(f"[OPCUA-从站] 收到 {len(data)} 字节，消息类型=HEL")
                else:
                    print(f"[OPCUA-从站] 收到 {len(data)} 字节，功能码={service_id}")
                ok, action, reason = _validate(data)
                if not ok:
                    if action == "exception":
                        print(f"[OPCUA-从站] 校验失败：{reason}，返回异常响应")
                        try:
                            conn.sendall(_build_err_response())
                        except Exception:
                            break
                        continue
                    print(f"[OPCUA-从站] 校验失败：{reason}，关闭连接")
                    break
                print(f"[OPCUA-从站] 校验通过，返回正常响应")
            else:
                print(f"[OPCUA-从站] 收到 {len(data)} 字节")

            if prefix == b"HEL":
                resp = _build_ack_response()
            elif prefix == b"MSG":
                resp = _build_msg_response(request_id)
            else:
                resp = _build_msg_response(request_id)

            try:
                conn.sendall(resp)
            except Exception as e:
                print(f"[OPCUA-从站] 发送失败: {type(e).__name__}: {e}")
                break
    except Exception as e:
        print(f"[OPCUA-从站] 处理异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[OPCUA-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[OPCUA-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[OPCUA-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[OPCUA-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[OPCUA-从站] 按 Ctrl+C 停止服务")

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
                print(f"[OPCUA-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[OPCUA-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass
        print("[OPCUA-从站] 已停止")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4840)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    run_server(args.host, args.port, args.strict)
