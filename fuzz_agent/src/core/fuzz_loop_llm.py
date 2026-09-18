import traceback
import time
import threading
import sys
import os
import datetime
import platform
import subprocess
import getpass

sys.dont_write_bytecode = True

from src.core.color_output import print_ok, print_warn, print_error, print_info
from src.core._resource import app_dir

from src.protocols.registry import get_protocol, list_protocols, auto_load_builtin
from src.core.report_generator import generate_combined_report
from src.core.llm_status import LLMStatus
from src.core.llm_precheck import (
    precheck_llm,
    PROTOCOL_FUZZ_TIMEOUT,
    make_timeout_excepthook_for_protocol,
)


auto_load_builtin()

_error_log_lock = threading.Lock()


def _log_exception(context=""):
    """将完整堆栈写入 reports/error.log，终端只打印摘要行。线程安全。"""
    exc_text = traceback.format_exc()
    try:
        reports_dir = os.path.join(app_dir(), "reports")
        os.makedirs(reports_dir, exist_ok=True)
        log_path = os.path.join(reports_dir, "error.log")
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with _error_log_lock:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"\n===== {ts} | {context} =====\n")
                f.write(exc_text)
                f.write("\n")
    except Exception:
        pass
    last_line = exc_text.strip().splitlines()[-1] if exc_text.strip() else "unknown error"
    print(f"[ERROR] {context}: {last_line}")


def _parse_target(target):
    if ":" in target:
        host, port_str = target.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = 5020
    else:
        host = target
        port = 5020
    return host, port


def _load_model_config():
    """读取 ~/.indusfuzz/config.json 里的 model 配置，解密 api_key 后返回。"""
    from src.core import security
    cfg_path = os.path.join(os.path.expanduser("~"), ".indusfuzz", "config.json")
    if not os.path.exists(cfg_path):
        return {}
    try:
        import json
        with open(cfg_path, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        model = cfg.get("model", {})
        if model and isinstance(model, dict) and model.get("api_key"):
            model = dict(model)
            model["api_key"] = security.get_api_key(model)
        return model
    except Exception:
        return {}


def run(config):
    protocols = config.get("protocols", [])
    func_codes_map = config.get("func_codes", {})
    timeout = config.get("timeout", 6)
    scenario = config.get("scenario", "lan")
    lang = config.get("lang", "zh")
    slave_mode = config.get("slave_mode", "strict")

    targets = config.get("targets")
    if not targets:
        legacy_target = config.get("target", "127.0.0.1:5020")
        targets = {p: legacy_target for p in protocols}

    connect_params = config.get("connect_params", {}) or {}

    gpu_cfg = config.get("gpu", {})
    gpu_enabled = bool(gpu_cfg.get("enabled", False))
    gpu_summary = gpu_cfg.get("summary", "")
    from src.core.runtime_config import set_gpu_config
    set_gpu_config(gpu_enabled, gpu_summary)
    if gpu_enabled:
        print(f"[GPU] 加速已启用: {gpu_summary}")
    else:
        print(f"[GPU] 未启用加速（{gpu_cfg.get('reason', '未配置')}）")

    # ============ 步骤 0：LLM 预连通性检查 ============
    model_cfg = _load_model_config()
    if model_cfg:
        provider = model_cfg.get("provider", "none")
        print(f"\n{'='*50}")
        print(f"[预检查] LLM 连通性测试（provider={provider}）...")
        ok, msg, elapsed, diagnostics = precheck_llm(model_cfg, lang=lang)
        if ok:
            print(f"[预检查] ✅ {msg}")
        else:
            level = diagnostics.get("error_type", "unknown")
            suggestion = diagnostics.get("suggestion", "")
            if lang == "zh":
                print(f"[预检查] ❌ {msg}")
                print(f"[预检查]   错误类型: {level}")
                print(f"[预检查]   建议: {suggestion}")
                print(f"[预检查]   → 将使用本地随机变异继续跑（不阻塞 fuzz）")
            else:
                print(f"[precheck] ❌ {msg}")
                print(f"[precheck]   type: {level}")
                print(f"[precheck]   suggestion: {suggestion}")
                print(f"[precheck]   → falling back to local random mutations")
    else:
        print(f"\n[预检查] 无 LLM 配置，所有变异使用本地随机")

    # ============ 步骤 0.5：协议端口连通性检查 ============
    print(f"\n{'='*50}")
    print("[预检查] 目标设备端口连通性...")
    for protocol_name in protocols:
        target = targets.get(protocol_name)
        if not target:
            continue
        host, port = _parse_target(target)
        import socket
        s = socket.socket()
        s.settimeout(2)
        try:
            s.connect((host, port))
            print(f"  ✅ {protocol_name:12} -> {host}:{port} 连通")
        except Exception as e:
            print(f"  ⚠️  {protocol_name:12} -> {host}:{port} 不通 ({type(e).__name__}) — fuzz 可能全部返回 CONN_CLOSED")
        finally:
            try:
                s.close()
            except Exception:
                pass

    # ============ 步骤 1：逐协议 fuzz ============
    all_results = []
    all_skipped = []
    all_build_failures = []
    all_protocol_data = []
    protocol_errors = []  # 记录超时/异常协议，最后汇总

    if scenario == "production":
        first_target = next(iter(targets.values()), "未知")
        print()
        print("=" * 60)
        print("⚠️⚠️⚠️  生产环境警告  ⚠️⚠️⚠️")
        print("=" * 60)
        print()
        print("即将对真实工业设备执行模糊测试：")
        print(f"  目标：{first_target}")
        print(f"  协议：{', '.join(protocols)}")
        print(f"  场景：生产环境")
        print()
        print("模糊测试会发送畸形报文，可能导致：")
        print("  - 设备崩溃或重启")
        print("  - 产线停摆")
        print("  - 安全事故")
        print()
        print("请确认以下事项：")
        print("  [ ] 已获得设备所有者的书面授权")
        print("  [ ] 测试网络与生产网络物理隔离")
        print("  [ ] 已准备好紧急停止方案")
        print("  [ ] 测试时间窗口已获批准")
        print()
        print("=" * 60)
        try:
            confirm = getpass.getpass("如全部确认，请输入 YES（必须大写，输入不回显）继续：").strip()
        except Exception:
            confirm = ""
        if confirm != "YES":
            print("已取消测试。")
            return
    elif scenario == "lan":
        first_target = next(iter(targets.values()), "未知")
        print()
        print("=" * 50)
        print("⚠️  局域网设备测试")
        print(f"  目标：{first_target}")
        print(f"  协议：{', '.join(protocols)}")
        print("  请确认已获得测试授权，且不会影响生产业务")
        print("=" * 50)

    for protocol_name in protocols:
        func_codes = func_codes_map.get(protocol_name, [])
        if not func_codes:
            continue

        target = targets.get(protocol_name)
        if not target:
            print(f"警告：协议 {protocol_name} 未指定目标，跳过")
            continue

        host, port = _parse_target(target)

        protocol_results = []
        protocol_skipped = []
        protocol_build_failures = []
        protocol_llm_status = LLMStatus()

        print(f"\n{'='*50}")
        print(f">>> 开始协议: {protocol_name}")
        print(f">>> 目标: {host}:{port}")
        print(f">>> 场景: {scenario}")
        print(f">>> 超时: {timeout} 秒/包")
        print(f">>> 整体协议超时上限: {PROTOCOL_FUZZ_TIMEOUT} 秒")

        # ===== 用线程跑 run_fuzz + 整体超时熔断 =====
        fuzz_error = [None]  # mutable holder for thread exception
        fuzz_done = [False]
        fuzz_start = time.time()
        stop_event = threading.Event()

        client_instance = [None]

        def _run_in_thread():
            try:
                protocol_class = get_protocol(protocol_name)
                client = protocol_class()
                client_instance[0] = client
                if scenario != "local":
                    proto_params = connect_params.get(protocol_name, {})
                    extra = dict(proto_params.get("extra", {}))
                    extra["timeout"] = timeout
                    ok = client.connect(host, port, **extra)
                    if not ok:
                        print(f"⚠️  [{protocol_name}] 连接真实设备失败，跳过该协议")
                        protocol_errors.append({
                            "protocol": protocol_name,
                            "error_type": "connect_failed",
                            "reason": f"无法连接 {host}:{port}",
                        })
                        return
                client.run_fuzz(
                    func_codes, host, port, timeout,
                    protocol_results, protocol_skipped, protocol_build_failures,
                    llm_status=protocol_llm_status, stop_event=stop_event,
                )
                if getattr(client, "_conn_failures", 0) > 3:
                    print(f"⚠️  [{protocol_name}] 连接中断超过 3 次，剩余用例已跳过")
            except KeyError as e:
                fuzz_error[0] = ("KeyError", str(e))
                for idx, fc in enumerate(func_codes, start=1):
                    protocol_skipped.append({
                        "round": idx, "func_code": fc,
                        "reason": f"协议 {protocol_name} 未注册",
                    })
            except Exception as e:
                fuzz_error[0] = (type(e).__name__, str(e))
                _log_exception(f"fuzz_loop:{protocol_name}")
            finally:
                try:
                    if scenario != "local" and client_instance[0] is not None:
                        client_instance[0].disconnect()
                except Exception:
                    pass
                fuzz_done[0] = True

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()
        t.join(timeout=PROTOCOL_FUZZ_TIMEOUT)

        protocol_timed_out = False
        if t.is_alive():
            elapsed = time.time() - fuzz_start
            protocol_timed_out = True
            print(f"\n⚠️  [超时] 协议 {protocol_name} fuzz 超过 {PROTOCOL_FUZZ_TIMEOUT} 秒（已跑 {elapsed:.0f}s），强制终止")
            print(f"⚠️  [超时] 已收集 {len(protocol_results)} 条结果，这些结果仍然会生成报告")
            protocol_errors.append({
                "protocol": protocol_name,
                "error_type": "timeout",
                "elapsed": round(elapsed, 1),
                "completed_func_codes": len(set(r.get("func_code") for r in protocol_results)),
                "total_func_codes": len(func_codes),
                "reason": f"fuzz 超过 {PROTOCOL_FUZZ_TIMEOUT} 秒未完成，可能是 LLM 推理过慢或目标无响应",
            })
            protocol_llm_status.on_call("TIMEOUT")
            # 触发协作停止事件，让线程在下一个检查点自行退出
            stop_event.set()
            # 给线程一个宽限期让其因 socket timeout 自行退出，避免 daemon 线程累积
            t.join(timeout=5)
            if t.is_alive():
                print(f"⚠️  [超时] 协议 {protocol_name} 线程仍在运行，将在主进程退出时被强制清理")
            protocol_llm_status.on_fallback_only("TIMEOUT")
        elif fuzz_error[0]:
            err_type, err_msg = fuzz_error[0]
            elapsed = time.time() - fuzz_start
            print(f"\n⚠️  [异常] 协议 {protocol_name} 执行异常 {err_type}: {err_msg}")
            protocol_errors.append({
                "protocol": protocol_name,
                "error_type": err_type,
                "error_msg": err_msg,
                "elapsed": round(elapsed, 1),
            })

        all_protocol_data.append({
            "protocol_name": protocol_name,
            "target": target,
            "results": protocol_results,
            "skipped": protocol_skipped,
            "build_failures": protocol_build_failures,
            "llm_status": protocol_llm_status,
            "slave_mode": slave_mode,
            "protocol_timed_out": protocol_timed_out,
        })

        all_results.extend(protocol_results)
        all_skipped.extend(protocol_skipped)
        all_build_failures.extend(protocol_build_failures)

    # ============ 步骤 2：汇总 + 错误报告 ============
    conn_closed_count = sum(1 for r in all_results if r.get("classification") == "CONN_CLOSED")
    print(f"\n{'='*50}")
    print(f"=== 全部协议总计 ===")
    print(f"总数: {len(all_results)}, CONN_CLOSED: {conn_closed_count}")
    print(f"跳过: {len(all_skipped)}, 变异失败: {len(all_build_failures)}")

    if protocol_errors:
        print(f"\n⚠️  有 {len(protocol_errors)} 个协议出现问题：")
        for e in protocol_errors:
            print(f"  [{e.get('error_type','?')}] {e['protocol']}: {e.get('reason', e.get('error_msg',''))}")

    if all_protocol_data:
        try:
            report_path, pdf_path, log_path = generate_combined_report(
                all_protocol_data, scenario=scenario, protocol_errors=protocol_errors
            )
            print(f"\n=== 报告文件 ===")
            print_ok(f"  HTML 报告: {report_path}")
            print_ok(f"  PDF 报告:  {pdf_path}")
            print(f"  运行日志:  {log_path}")
            print_info(f"[INFO] 报告已生成：{report_path}")
            try:
                import webbrowser
                webbrowser.open("file://" + os.path.abspath(report_path))
                print_info("[INFO] 已自动打开浏览器")
                print_info("[INFO] 如果浏览器未打开，请手动访问上述路径")
            except Exception:
                print_info("[INFO] 自动打开浏览器失败，请手动打开上述 HTML 报告")
            reports_dir = os.path.dirname(os.path.abspath(report_path))
            print_info(f"[INFO] 报告目录：reports/")
            print_info("[INFO] 按 R 打开报告目录，按 Q 退出")
            try:
                if sys.stdin.isatty():
                    key = input().strip().upper()
                    if key == "R":
                        if platform.system() == "Windows":
                            os.startfile(reports_dir)
                        elif platform.system() == "Darwin":
                            subprocess.Popen(["open", reports_dir])
                        else:
                            subprocess.Popen(["xdg-open", reports_dir])
            except Exception:
                pass
        except Exception as e:
            print_error(f"整合报告生成失败: {type(e).__name__}: {e}")
            _log_exception("combined_report")


# Used by tests/verify_error_report.py; not called in main flow yet.
def _summarize_suggestions(protocol_errors, model_cfg):
    """根据错误类型和当前 LLM 配置，给出针对性建议。返回 {"zh": ..., "en": ...}。"""
    tips_zh = []
    tips_en = []

    timeout_count = sum(1 for e in protocol_errors if e.get("error_type") == "timeout")
    provider = (model_cfg or {}).get("provider", "none")
    model_name = (model_cfg or {}).get("name", "")

    if timeout_count > 0:
        completed = sum(e.get("completed_func_codes", 0) for e in protocol_errors if e.get("error_type") == "timeout")
        total = sum(e.get("total_func_codes", 0) for e in protocol_errors if e.get("error_type") == "timeout")
        if provider == "ollama":
            tips_zh.append(
                f"- {timeout_count} 个协议 fuzz 超时（已完成 {completed}/{total} 个功能码）。\n"
                f"  当前使用本地 Ollama 模型 {model_name}，最可能原因是本地推理过慢。\n"
                f"  建议：\n"
                f"    1) 在菜单中选择更少的功能码（如 5-10 个）\n"
                f"    2) 使用更小的模型（如 qwen2.5-coder:3b）\n"
                f"    3) 使用 CPU 推理，考虑 GPU 加速\n"
                f"    4) 使用云端API"
            )
            tips_en.append(
                f"- {timeout_count} protocol(s) timed out ({completed}/{total} function codes completed).\n"
                f"  Currently using local Ollama model {model_name}; most likely cause is slow local inference.\n"
                f"  Suggestions:\n"
                f"    1) Select fewer function codes in the menu (e.g. 5-10)\n"
                f"    2) Use a smaller model (e.g. qwen2.5-coder:3b)\n"
                f"    3) If using CPU inference, consider GPU acceleration\n"
                f"    4) Use cloud API (data will be sent to third parties, do not use in sensitive scenarios)"
            )
        elif provider in ("none", "", None):
            tips_zh.append(
                f"- {timeout_count} 个协议 fuzz 超时。\n"
                f"  当前未配置 LLM，使用本地随机变异。超时可能是目标设备无响应或网络问题。"
            )
            tips_en.append(
                f"- {timeout_count} protocol(s) timed out.\n"
                f"  No LLM configured; using local random mutation. Timeout may be due to unresponsive target or network issues."
            )
        else:
            tips_zh.append(
                f"- {timeout_count} 个协议 fuzz 超时（已完成 {completed}/{total} 个功能码）。\n"
                f"  当前使用云端 LLM: {provider} @ {model_cfg.get('base_url','')}\n"
                f"  可能原因：云端 API 响应过慢或网络不稳定。\n"
                f"  建议：\n"
                f"    1) 在菜单中选择更少的功能码\n"
                f"    2) 确认 API Key 有效且账户额度充足\n"
                f"    3) 网络不稳定，改用本地 Ollama"
            )
            tips_en.append(
                f"- {timeout_count} protocol(s) timed out ({completed}/{total} function codes completed).\n"
                f"  Currently using cloud LLM: {provider} @ {model_cfg.get('base_url','')}\n"
                f"  Possible cause: slow cloud API response or unstable network.\n"
                f"  Suggestions:\n"
                f"    1) Select fewer function codes in the menu\n"
                f"    2) Verify API Key is valid and account has sufficient quota\n"
                f"    3) If network is unstable, switch to local Ollama"
            )

    tips_zh.append("- 安全提示：使用云端 API 时数据会发送到第三方，敏感场景请勿使用")
    tips_en.append("- Security Notice: When using cloud APIs, data is sent to third parties. Do not use in sensitive scenarios.")

    if not tips_zh:
        tips_zh.append("- 未知错误，请查看上方错误信息")
        tips_en.append("- Unknown error, please check the error details above")

    return {"zh": "\n".join(tips_zh), "en": "\n".join(tips_en)}
