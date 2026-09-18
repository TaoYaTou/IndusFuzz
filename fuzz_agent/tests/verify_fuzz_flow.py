import os
import sys
import io
import re
import time
import glob
import socket
import subprocess
import argparse
import random

ROOT = r"d:\Application\AllToolsSet\AgnetPrograms\IndusFuzz"
FUZZ_AGENT = os.path.join(ROOT, "fuzz_agent")
VENV_PY = os.path.join(ROOT, "agentscope_env", "Scripts", "python.exe")
HOST = "127.0.0.1"

# 协议 -> (server脚本, 端口, 功能码列表)
PROTOCOL_CONFIG = {
    "modbus":   ("modbus_server.py",   15020, ["0x03", "0x06"]),
    "s7comm":   ("s7comm_server.py",   15103, ["0x04", "0x11"]),
    "dnp3":     ("dnp3_server.py",     12000, ["0x01", "0x02"]),
    "iec104":   ("iec104_server.py",   12404, ["0x64", "0x65"]),
    "iec61850": ("iec61850_server.py", 1102,  ["0xB0"]),
    "enip":     ("enip_server.py",     14481, ["0x01"]),
    "opcua":    ("opcua_server.py",    14840, ["446"]),
}


def wait_port(host, port, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


def run_one(protocol):
    server_script, port, func_codes = PROTOCOL_CONFIG[protocol]

    slave = subprocess.Popen(
        [VENV_PY, os.path.join(FUZZ_AGENT, "server", server_script),
         "--port", str(port), "--strict"],
        cwd=FUZZ_AGENT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

    try:
        if not wait_port(HOST, port):
            print(f"FAIL {protocol} strict 从站启动失败")
            return False
        print(f"{protocol} strict 从站已启动 127.0.0.1:{port}")

        sys.path.insert(0, FUZZ_AGENT)
        os.chdir(FUZZ_AGENT)

        before = set(glob.glob(os.path.join(FUZZ_AGENT, "reports", "*")))

        from src.core.fuzz_loop_llm import run

        # 强制禁用 LLM，走本地随机变异，确保验证可复现
        import src.core.fuzz_loop_llm as _fuzz_mod
        _fuzz_mod._load_model_config = lambda: None
        try:
            import importlib
            _llm_mod = importlib.import_module(f"src.protocols.{protocol}.llm_mutator")
            _llm_mod._load_model_config = lambda: None
        except Exception:
            pass
        # generate_mutations 内部调用的是 llm_mutator_base 模块级 _load_model_config，
        # 必须同步打补丁才能真正禁用 LLM 路径
        try:
            import importlib
            _base_mod = importlib.import_module("src.protocols.llm_mutator_base")
            _base_mod._load_model_config = lambda *a, **k: {}
        except Exception:
            pass

        # 固定 mutator seed 消除变异随机性，确保验证可复现
        try:
            import importlib
            _mut_mod = importlib.import_module(f"src.protocols.{protocol}.mutator")
            if hasattr(_mut_mod, "seed_mutator"):
                _mut_mod.seed_mutator(42)
        except Exception:
            pass

        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            run({
                "protocols": [protocol],
                "func_codes": {protocol: func_codes},
                "timeout": 3,
                "scenario": "local",
                "lang": "zh",
                "targets": {protocol: "%s:%d" % (HOST, port)},
            })
        finally:
            sys.stdout = old_stdout

        output = buf.getvalue()
        print(output)
        print("=" * 60)

        checks = []
        checks.append(("流程无崩溃(无Traceback)", "Traceback" not in output))
        checks.append(("端口连通检查输出", "连通" in output))
        checks.append(("NORMAL分类出现", "NORMAL" in output))
        checks.append(("EXCEPTION分类出现", "EXCEPTION" in output))
        checks.append(("总数统计输出", "全部协议总计" in output))

        report_path = None
        m = re.search(r"报告:\s*(\S+)", output)
        if m:
            report_path = m.group(1).strip()
        report_ok = bool(report_path) and os.path.exists(report_path) and os.path.getsize(report_path) > 0
        checks.append(("HTML报告文件生成", report_ok))

        report_has_exception = False
        report_has_mode_line = False
        if report_ok:
            try:
                with open(report_path, "r", encoding="utf-8", errors="ignore") as f:
                    html = f.read()
                report_has_exception = "EXCEPTION" in html
                report_has_mode_line = "模拟从站模式" in html and "严格" in html
            except Exception:
                report_has_exception = False
        checks.append(("报告中含EXCEPTION统计", report_has_exception))
        checks.append(("报告含从站模式行(严格)", report_has_mode_line))

        new_files = [p for p in glob.glob(os.path.join(FUZZ_AGENT, "reports", "*")) if p not in before]
        checks.append(("reports目录新增文件(报告+日志)", len(new_files) >= 2))

        all_pass = True
        for name, ok in checks:
            print(("PASS " if ok else "FAIL ") + name)
            if not ok:
                all_pass = False
        print("=" * 60)
        print(f"7.6 {protocol} fuzz流程验证: " + ("PASS" if all_pass else "FAIL"))
        return all_pass
    finally:
        slave.terminate()
        try:
            slave.wait(timeout=3)
        except Exception:
            slave.kill()
        print(f"{protocol} 从站进程已停止")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="IndusFuzz fuzz flow verification")
    parser.add_argument("--protocol", choices=list(PROTOCOL_CONFIG.keys()) + ["all"],
                        default="s7comm", help="要验证的协议（默认 s7comm，all 则全部轮换）")
    args = parser.parse_args()

    protocols = list(PROTOCOL_CONFIG.keys()) if args.protocol == "all" else [args.protocol]

    results = {}
    for p in protocols:
        print(f"\n{'#'*60}")
        print(f"# 验证协议: {p}")
        print(f"{'#'*60}")
        results[p] = run_one(p)

    print(f"\n{'='*60}")
    print("汇总:")
    for p, ok in results.items():
        print(f"  {p}: {'PASS' if ok else 'FAIL'}")
    all_ok = all(results.values())
    print(f"7.6 完整fuzz流程验证（{len(results)} 协议）: " + ("PASS" if all_ok else "FAIL"))
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
