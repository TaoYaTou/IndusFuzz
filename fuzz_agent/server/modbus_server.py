import sys
import socket
import threading

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5020
BUFFER_SIZE = 4096

# 标准 Modbus 功能码（请求方向），与 modbus_func_codes.json 对齐（19 码）
_VALID_FUNC_CODES = {
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x0B, 0x0C,
    0x0F, 0x10, 0x11, 0x14, 0x15, 0x16, 0x17, 0x18, 0x2B,
}

# 读功能码（数据区含 start_addr + quantity）
_READ_FUNC_CODES = {0x01, 0x02, 0x03, 0x04}


def _parse_args():
    port = DEFAULT_PORT
    strict = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                print(f"[Modbus-从站] 无效端口参数: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif args[i] == "--strict":
            strict = True
            i += 1
        else:
            i += 1
    return port, strict


def _build_exception_response(data, exception_code=0x01):
    """构造 Modbus 异常响应。MBAP length = unit_id(1) + fc|0x80(1) + exc_code(1) = 3"""
    trans_id = data[0:2]
    proto_id = data[2:4]
    unit_id = data[6:7]
    fc = data[7] if len(data) > 7 else 0x00
    length = (3).to_bytes(2, "big")
    return trans_id + proto_id + length + unit_id + bytes([fc | 0x80, exception_code])


def _build_normal_response(data):
    """构造一个简单的正常响应（读功能码返回少量数据）。"""
    trans_id = data[0:2]
    proto_id = data[2:4]
    unit_id = data[6:7]
    fc = data[7] if len(data) > 7 else 0x03
    # 简单返回 2 字节数据
    pdu = bytes([fc, 0x02, 0x00, 0x00])
    length = (1 + len(pdu)).to_bytes(2, "big")
    return trans_id + proto_id + length + unit_id + pdu


def _validate_request(data, strict):
    """返回 (ok, action, reason, exception_code)。action: 'exception' | 'close' | None"""
    if len(data) < 8:
        return False, "close", "报文过短（不足 8 字节）", 0x01
    if data[2:4] != b"\x00\x00":
        return False, "close", "协议标识非 0x0000", 0x01
    fc = data[7]
    if strict and fc not in _VALID_FUNC_CODES:
        return False, "exception", f"功能码 0x{fc:02X} 不支持", 0x01
    # 数据区校验：读功能码 quantity 上限 0x7D（125 寄存器/线圈）
    if strict and fc in _READ_FUNC_CODES and len(data) >= 12:
        quantity = (data[10] << 8) | data[11]
        if quantity > 0x7D:
            return False, "exception", f"quantity={quantity} 超过上限 0x7D", 0x03
    return True, None, None, 0x00


def _handle_client(conn, addr, strict):
    print(f"[Modbus-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            try:
                data = conn.recv(BUFFER_SIZE)
            except socket.timeout:
                break
            if not data:
                break

            ok, action, reason, exc_code = _validate_request(data, strict)
            if not ok:
                if action == "exception":
                    print(f"[Modbus-从站] 校验失败：{reason}，返回异常响应 0x{exc_code:02X}")
                    try:
                        conn.sendall(_build_exception_response(data, exc_code))
                    except Exception:
                        break
                    continue
                print(f"[Modbus-从站] 校验失败：{reason}，关闭连接")
                break

            fc = data[7]
            if strict:
                print(f"[Modbus-从站] 收到 {len(data)} 字节，功能码=0x{fc:02X}，返回正常响应")
            else:
                print(f"[Modbus-从站] 收到 {len(data)} 字节，功能码=0x{fc:02X}")

            try:
                conn.sendall(_build_normal_response(data))
            except Exception as e:
                print(f"[Modbus-从站] 发送响应失败: {type(e).__name__}: {e}")
                break
    except Exception as e:
        print(f"[Modbus-从站] 处理客户端 {addr} 异常: {type(e).__name__}: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass
        print(f"[Modbus-从站] 客户端断开: {addr}")


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[Modbus-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[Modbus-从站] 端口 {port} 被占用或不可用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[Modbus-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")
    print(f"[Modbus-从站] 按 Ctrl+C 停止服务")

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
                print(f"[Modbus-从站] accept 失败: {type(e).__name__}: {e}")
    except KeyboardInterrupt:
        print("\n[Modbus-从站] 正在停止...")
    finally:
        try:
            server_sock.close()
        except Exception:
            pass


if __name__ == "__main__":
    port, strict = _parse_args()
    run_server(DEFAULT_HOST, port, strict)
