import os
import sys
import time
import socket
import subprocess

from src.core._resource import resource_path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5020

_SUPPORTED_PROTOCOLS = {
    "modbus", "s7comm", "dnp3", "iec104", "iec61850", "enip", "opcua",
}


def _port_open(host, port, timeout=0.5):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.error, OSError):
        return False


def supports_protocol(protocol_name):
    return protocol_name in _SUPPORTED_PROTOCOLS


def list_supported_protocols():
    return sorted(_SUPPORTED_PROTOCOLS)


def start_slave(protocol_name, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=10, strict=True):
    if _port_open(host, port):
        print(f"[从站] 端口 {port} 已被占用，检测是否可连通...")
        return None, f"端口 {port} 已被其他进程占用"

    if not supports_protocol(protocol_name):
        print(f"[从站] 协议 {protocol_name} 没有对应的从站脚本")
        return None, f"协议 {protocol_name} 没有对应的从站脚本"

    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = subprocess.CREATE_NO_WINDOW

    try:
        cmd = [
            sys.executable, "--run-slave",
            "--protocol", protocol_name,
            "--host", host,
            "--port", str(port),
        ]
        if strict:
            cmd.append("--strict")
        proc = subprocess.Popen(
            cmd,
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
