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


def _parse_frame(data):
    trans_id = 0
    func_code = 0
    try:
        if len(data) >= 4:
            trans_id = int.from_bytes(data[2:4], "big")
        if len(data) >= 9:
            func_code = data[8]
    except Exception:
        pass
    return trans_id, func_code


def _build_response(trans_id, func_code):
    body = bytes([
        func_code & 0xFF,
        0x00, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00,
    ])
    header = bytes([0x03, 0x00]) + trans_id.to_bytes(2, "big") + len(body).to_bytes(2, "big") + bytes([0x00, 0x00])
    return header + body


def _build_error_response(trans_id, error_code=0x01):
    body = bytes([
        0x03,
        0x85,
        error_code & 0xFF,
        0x00, 0x00, 0x00, 0x00, 0x00,
    ])
    header = bytes([0x03, 0x00]) + trans_id.to_bytes(2, "big") + len(body).to_bytes(2, "big") + bytes([0x00, 0x00])
    return header + body


def _validate_request(data):
    if len(data) < 9:
        return False, "close", "报文过短"
    if data[0] != 0x03 or data[1] != 0x00:
        return False, "close", "协议标识错误"
    declared_len = int.from_bytes(data[4:6], "big")
    if declared_len + 8 != len(data):
        return False, "close", f"长度字段不匹配: 声明 {declared_len}, 实际 {len(data) - 8}"
    func_code = data[8]
    if func_code not in _S7COMM_KNOWN_FUNCS:
        return False, "exception", f"功能码 0x{func_code:02X} 不支持"
    if func_code in (0x04, 0x05) and len(data) >= 20:
        db_number = int.from_bytes(data[14:16], "big")
        start_addr = int.from_bytes(data[16:18], "big")
        if db_number > 1000:
            return False, "exception", f"DB 号 {db_number} 超出范围 0-1000"
        if start_addr > 10000:
            return False, "exception", f"起始地址 {start_addr} 超出范围 0-10000"
    return True, None, None


def _handle_client(conn, addr, strict):
    print(f"[S7comm-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            trans_id, func_code = _parse_frame(data)

            if strict:
                print(f"[S7comm-从站] 收到 {len(data)} 字节，功能码=0x{func_code:02X}")
                ok, action, reason = _validate_request(data)
                if not ok:
                    if action == "exception":
                        print(f"[S7comm-从站] 校验失败：{reason}，返回异常响应")
                        try:
                            conn.sendall(_build_error_response(trans_id, 0x01))
                        except Exception:
                            break
                        continue
                    print(f"[S7comm-从站] 校验失败：{reason}，关闭连接")
                    break
                print(f"[S7comm-从站] 校验通过，返回正常响应")
            else:
                print(f"[S7comm-从站] 收到 {len(data)} 字节，transId={trans_id}, func=0x{func_code:02X}")

            response = _build_response(trans_id, func_code)
            try:
                conn.sendall(response)
            except Exception as e:
                print(f"[S7comm-从站] 发送响应失败: {type(e).__name__}: {e}")
                break
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
