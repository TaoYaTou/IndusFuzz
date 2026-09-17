import os
import sys
import time
import socket
import subprocess

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SERVER_DIR = os.path.join(PROJECT_ROOT, "server")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5020


def _port_open(host, port, timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, OSError):
        return False


def _get_slave_script(protocol_name):
    path = os.path.join(SERVER_DIR, f"{protocol_name}_server.py")
    if os.path.exists(path):
        return path
    return None


def start_slave(protocol_name, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=10, strict=True):
    if _port_open(host, port):
        print(f"[从站] 端口 {port} 已被占用，检测是否可连通...")
        return None, f"端口 {port} 已被其他进程占用"

    slave_script = _get_slave_script(protocol_name)
    if not slave_script:
        print(f"[从站] server/{protocol_name}_server.py 不存在，跳过启动")
        return None, f"协议 {protocol_name} 没有对应的从站脚本"

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    try:
        cmd = [sys.executable, slave_script, "--port", str(port)]
        if strict:
            cmd.append("--strict")
        proc = subprocess.Popen(
            cmd,
            cwd=PROJECT_ROOT,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )
    except Exception as e:
        return None, f"启动从站失败: {type(e).__name__}: {e}"

    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return None, f"从站进程意外退出，退出码 {proc.returncode}"
        if _port_open(host, port):
            return proc, None
        time.sleep(0.3)

    return proc, f"从站启动超时（{timeout}s）"


def stop_slave(proc):
    if not proc:
        return
    if proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=2)
            except Exception:
                pass
        except Exception:
            pass


def supports_protocol(protocol_name):
    return _get_slave_script(protocol_name) is not None


def list_supported_protocols():
    if not os.path.isdir(SERVER_DIR):
        return []
    result = []
    for fname in os.listdir(SERVER_DIR):
        if fname.endswith("_server.py"):
            result.append(fname[:-len("_server.py")])
    return result
