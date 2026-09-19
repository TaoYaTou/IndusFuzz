import os
import sys
import socket
import platform
import subprocess
import datetime
import shlex

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _safe_input(prompt=""):
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return ""


def _run_cmd(cmd, timeout=5):
    """cmd 必须是列表参数，避免 shell 注入。"""
    try:
        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(
            cmd,
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            errors="replace",
            creationflags=creation_flags,
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"命令超时（{timeout}s）"
    except Exception as e:
        return False, f"执行失败: {type(e).__name__}: {e}"


def _get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        addrs = socket.getaddrinfo(hostname, None)
        seen = set()
        for addr in addrs:
            ip = addr[4][0]
            if ip not in seen and ":" not in ip:
                seen.add(ip)
                ips.append(ip)
    except Exception:
        pass

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(2)
        s.connect(("8.8.8.8", 80))
        out_ip = s.getsockname()[0]
        s.close()
        if out_ip not in ips and not out_ip.startswith("127."):
            ips.insert(0, out_ip)
    except Exception:
        pass

    return ips


def _resolve_host(host):
    try:
        return socket.gethostbyname(host)
    except Exception as e:
        return f"解析失败: {e}"


def _ping_target(host, count=2, timeout_sec=2):
    safe_host = shlex.quote(host)
    if sys.platform == "win32":
        cmd = ["ping", "-n", str(count), "-w", str(timeout_sec * 1000), safe_host]
    else:
        cmd = ["ping", "-c", str(count), "-W", str(timeout_sec), safe_host]
    return _run_cmd(cmd, timeout=timeout_sec * count + 3)


def _test_port(host, port, timeout=3):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "端口可达"
    except socket.timeout:
        return False, "连接超时"
    except ConnectionRefusedError:
        return False, "连接被拒绝（目标未监听该端口）"
    except socket.gaierror:
        return False, "主机名无法解析"
    except OSError as e:
        return False, f"网络错误: {e}"


def _get_route_table():
    if sys.platform == "win32":
        cmd = ["route", "print", "-4"]
    else:
        cmd = ["ip", "route"]
    ok, output = _run_cmd(cmd, timeout=5)
    if not ok:
        return f"获取失败: {output}"
    lines = output.split("\n")
    return "\n".join(lines[:25])


def _get_local_listening_ports():
    if sys.platform == "win32":
        cmd = ["netstat", "-ano", "-p", "TCP"]
    else:
        cmd = ["netstat", "-tlnp"]
    ok, output = _run_cmd(cmd, timeout=5)
    if not ok:
        return f"获取失败: {output}"
    lines = output.split("\n")
    filtered = [ln for ln in lines if "LISTEN" in ln.upper() or "LISTENING" in ln.upper()]
    return "\n".join(filtered[:15]) if filtered else "无监听端口"


def _get_os_info():
    try:
        system = platform.system()
        release = platform.release()
        version = platform.version()
        machine = platform.machine()
        return f"{system} {release} ({version}) [{machine}]"
    except Exception:
        return "未知"


def collect_diagnostics(target, scenario="lan"):
    if ":" in target:
        host, port_str = target.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 5020
    else:
        host = target
        port = 5020

    report = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": f"{host}:{port}",
        "host": host,
        "port": port,
        "scenario": scenario,
        "os": _get_os_info(),
        "python_version": sys.version.split()[0],
        "hostname": socket.gethostname() if hasattr(socket, "gethostname") else "unknown",
        "local_ips": _get_local_ips(),
        "dns_resolved": _resolve_host(host),
    }

    ping_ok, ping_out = _ping_target(host, count=2, timeout_sec=2)
    report["ping_ok"] = ping_ok
    report["ping_output"] = ping_out

    port_ok, port_msg = _test_port(host, port, timeout=3)
    report["port_ok"] = port_ok
    report["port_message"] = port_msg

    report["route_table"] = _get_route_table()
    report["local_listening"] = _get_local_listening_ports()

    return report


def _section(title):
    print()
    print(f"── {title} " + "─" * max(0, 52 - len(title)))


def print_diagnostics(report):
    print()
    print("=" * 56)
    print("  🔍 自动诊断报告")
    print("=" * 56)
    print(f"时间: {report['timestamp']}")
    print(f"操作系统: {report['os']}")
    print(f"Python: {report['python_version']}")
    print(f"主机名: {report['hostname']}")

    _section("本机 IP 地址")
    if report["local_ips"]:
        for ip in report["local_ips"]:
            print(f"  - {ip}")
    else:
        print("  (未获取到)")

    _section("目标信息")
    print(f"  目标: {report['target']}")
    print(f"  场景: {report['scenario']}")
    print(f"  DNS 解析: {report['dns_resolved']}")

    _section("Ping 测试")
    print(f"  结果: {'✓ 通' if report['ping_ok'] else '✗ 不通'}")
    if report["ping_output"]:
        for line in report["ping_output"].split("\n")[:10]:
            print(f"  {line}")

    _section("端口测试")
    print(f"  TCP {report['target']}: {'✓ 可达' if report['port_ok'] else '✗ ' + report['port_message']}")

    _section("路由表（前 25 行）")
    for line in report["route_table"].split("\n"):
        print(f"  {line}")

    _section("本机监听端口（前 15 条）")
    for line in report["local_listening"].split("\n"):
        print(f"  {line}")

    _section("诊断结论")
    if report["port_ok"]:
        print("  ✓ 目标端口可达，网络正常")
    elif report["ping_ok"]:
        print("  ⚠️ 能 ping 通但端口不可达")
        print("  最可能的原因：")
        print("    1. 目标设备没有监听该端口（从站未启动）")
        print("    2. 目标防火墙拦截了该端口")
        print("    3. 端口号输入错误")
    else:
        print("  ❌ 目标不可达")
        print("  最可能的原因：")
        print("    1. 目标设备未开机或不在网络")
        print("    2. 目标 IP 输入错误")
        print("    3. 网络隔离（不同 VLAN 或防火墙策略）")
        print("    4. 路由不可达")

    print()
    print("=" * 56)
    print("  请将以上信息完整截图，发送给开发者")
    print("=" * 56)
    print()


def save_diagnostics(report, directory=None):
    if directory is None:
        directory = os.path.join(PROJECT_ROOT, "reports")
    try:
        os.makedirs(directory, exist_ok=True)
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(directory, f"diagnose_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"时间: {report['timestamp']}\n")
            f.write(f"操作系统: {report['os']}\n")
            f.write(f"Python: {report['python_version']}\n")
            f.write(f"主机名: {report['hostname']}\n")
            f.write(f"\n本机 IP:\n")
            for ip in report["local_ips"]:
                f.write(f"  - {ip}\n")
            f.write(f"\n目标: {report['target']}\n")
            f.write(f"场景: {report['scenario']}\n")
            f.write(f"DNS: {report['dns_resolved']}\n")
            f.write(f"\nPing: {'OK' if report['ping_ok'] else 'FAIL'}\n")
            f.write(report["ping_output"] + "\n")
            f.write(f"\nPort: {'OK' if report['port_ok'] else 'FAIL'} - {report['port_message']}\n")
            f.write(f"\n=== 路由表 ===\n{report['route_table']}\n")
            f.write(f"\n=== 本机监听端口 ===\n{report['local_listening']}\n")
        return path
    except Exception as e:
        print(f"保存诊断文件失败: {e}")
        return None


def run_diagnostics(target, scenario="lan"):
    print()
    print("[诊断] 正在收集环境信息，请稍候...")
    report = collect_diagnostics(target, scenario)
    print_diagnostics(report)

    try:
        save = _safe_input("是否保存诊断报告到 reports/ 目录？(y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if save in ("y", "yes"):
        path = save_diagnostics(report)
        if path:
            print(f"[诊断] 已保存: {path}")
