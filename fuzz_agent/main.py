import sys
import os

# 修复 Windows 控制台 GBK 编码无法输出 Unicode 字符（✓ 等）的问题
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

_SLAVE_MODULES = {
    "modbus": "server.modbus_server",
    "s7comm": "server.s7comm_server",
    "dnp3": "server.dnp3_server",
    "iec104": "server.iec104_server",
    "iec61850": "server.iec61850_server",
    "enip": "server.enip_server",
    "opcua": "server.opcua_server",
}


def _run_slave_from_argv(argv):
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)
    mod_name = _SLAVE_MODULES.get(args.protocol)
    if not mod_name:
        print(f"[slave] 未知协议: {args.protocol}")
        sys.exit(1)
    import importlib
    mod = importlib.import_module(mod_name)
    mod.run_server(host=args.host, port=args.port, strict=args.strict)


if len(sys.argv) > 1 and sys.argv[1] == "--run-slave":
    _run_slave_from_argv(sys.argv[2:])
    sys.exit(0)

from src.protocols.registry import auto_load_builtin, auto_load_plugins
from src.core.version import __version__
from src.core.menu import (
    check_environment,
    interactive_flow,
    save_config,
    _safe_input,
    _parse_target,
    SCENARIO_NAME,
    GoBack,
)
from src.core.slave_launcher import (
    start_slave,
    stop_slave,
    supports_protocol,
)
from src.core.fuzz_loop_llm import run


def _check_first_run():
    marker = os.path.join(os.path.expanduser("~"), ".indusfuzz", "first_run")
    os.makedirs(os.path.dirname(marker), exist_ok=True)
    if not os.path.exists(marker):
        print("  💡 提示：建议为本程序创建桌面快捷方式")
        print("     方法：右键 IndusFuzz.exe → 发送到 → 桌面快捷方式")
        print()
        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write("1")
        except Exception:
            pass


def main():
    auto_load_builtin()
    auto_load_plugins()

    print()
    print("========================================")
    print(f"  IndusFuzz v{__version__}")
    print("  工业协议模糊测试智能体")
    print("========================================")
    _check_first_run()
    print("  提示：任意输入框输入 q 可返回上一步，在模型选择步骤输入 q 直接退出程序")
    print("     ")
    print()

    env = check_environment()
    print(f"[环境] Python: {'OK' if env['python'] else 'FAIL'}")
    if env["ollama"]:
        print(f"[环境] Ollama: OK ({len(env['ollama_models'])} 个模型)")
    else:
        print(f"[环境] Ollama: 不可用")
        while True:
            try:
                ans = _safe_input("是否继续？(y=继续 / n/q=退出): ").lower()
            except GoBack:
                print("\n已退出")
                return
            if ans in ("y", "yes"):
                break
            if ans in ("n", "no"):
                print("\n已退出")
                return
            print("请输入 y / n / q")

    config = interactive_flow()
    if config is None:
        print("\n已退出")
        return

    save_config({
        "model": config.get("model", {}),
        "last_selection": {
            "protocols": config["protocols"],
            "func_codes": config["func_codes"],
            "targets": config["targets"],
            "scenario": config["scenario"],
        }
    })

    is_local = config["scenario"] == "local"
    timeout = config["timeout"]
    strict = config.get("slave_mode", "strict") == "strict"

    slave_procs = []

    if is_local:
        for protocol_name in config["protocols"]:
            if not supports_protocol(protocol_name):
                print(f"[启动] 协议 {protocol_name} 不支持自动启动从站，请手动启动")
                continue

            target = config["targets"].get(protocol_name)
            if not target:
                print(f"[启动] 协议 {protocol_name} 未指定目标，跳过")
                continue

            host, port = _parse_target(target)

            print()
            print(f"[启动] 正在后台启动 {protocol_name} 从站（端口 {port}）...")
            proc, err = start_slave(protocol_name, host=host, port=port, timeout=10, strict=strict)
            if err:
                print(f"[启动] {protocol_name} 从站启动失败：{err}")
                print()
                print("请检查：")
                print(f"  [1] 端口 {port} 是否被占用：netstat -ano | findstr {port}")
                print(f"  [2] server/ 下是否有对应从站脚本")
                print(f"  [3] 依赖是否已安装")
                print()
                print("如果以上均排查失败，请联系开发者")
                for p in slave_procs:
                    stop_slave(p)
                return
            print(f"[启动] {protocol_name} 从站已启动，监听 {host}:{port}（{'严格' if strict else '宽松'}模式）")
            slave_procs.append(proc)
    else:
        first_target = list(config["targets"].values())[0] if config["targets"] else "N/A"
        print()
        print(f"[启动] 场景: {SCENARIO_NAME.get(config['scenario'], config['scenario'])}")
        print(f"[启动] 远程目标: {first_target}")
        print(f"[启动] 跳过本地从站启动")
        print(f"[提示] 请确保设备已授权，超时 {timeout} 秒")

    print()
    try:
        print("开始模糊测试...")
        print()
        run(config)
    finally:
        if slave_procs:
            print()
            print("[清理] 正在停止从站...")
            for p in slave_procs:
                stop_slave(p)
            print("[清理] 从站已停止")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n已中断")
    except Exception as e:
        print(f"\n运行失败: {type(e).__name__}: {e}")
        import traceback, os, datetime
        try:
            from src.core.fuzz_loop_llm import _error_log_lock
            from src.core._resource import app_dir
            reports_dir = os.path.join(app_dir(), "reports")
            os.makedirs(reports_dir, exist_ok=True)
            with _error_log_lock:
                with open(os.path.join(reports_dir, "error.log"), "a", encoding="utf-8") as f:
                    f.write(f"\n===== {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | main =====\n")
                    f.write(traceback.format_exc())
                    f.write("\n")
        except Exception:
            pass