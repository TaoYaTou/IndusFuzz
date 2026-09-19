import os
import json
import urllib.request
import socket
from src.core.color_output import print_ok, print_warn, print_error

from src.core import security
from src.core._resource import resource_path

FUNC_CODES_DIR = resource_path(os.path.join("src", "protocols", "func_codes"))
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".indusfuzz")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

PROTOCOL_META = None

_SCANNED_PROTOCOLS = None


def _scan_protocols():
    global _SCANNED_PROTOCOLS
    if _SCANNED_PROTOCOLS is not None:
        return _SCANNED_PROTOCOLS
    result = {}
    if not os.path.isdir(FUNC_CODES_DIR):
        _SCANNED_PROTOCOLS = result
        return result
    for fname in os.listdir(FUNC_CODES_DIR):
        if not fname.endswith("_func_codes.json"):
            continue
        fpath = os.path.join(FUNC_CODES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            proto = data.get("protocol")
            port = data.get("default_port")
            codes = data.get("func_codes", [])
            if not proto or not port or not codes:
                print_warn(f"⚠️  [menu] 功能码文件 {fname} 缺少 protocol/port/func_codes 字段，已跳过")
                continue
            result[proto] = {
                "name": proto,
                "display_name": proto,
                "default_port": port,
                "func_codes": codes,
            }
        except Exception as e:
            print_warn(f"⚠️  [menu] 功能码文件 {fname} 解析失败（{type(e).__name__}），已跳过")
            continue
    _SCANNED_PROTOCOLS = result
    return result

SCENARIO_TIMEOUT = {"local": 2, "lan": 6, "production": 10}
SCENARIO_NAME = {"local": "本机自测", "lan": "局域网设备", "production": "真实工业设备"}

DEVELOPER_CONTACT = {
    "name": "IndusFuzz 开发团队",
    "email": "2723494508@qq.com",
    "issue_template": "请访问github仓库提交问题：https://github.com/IndusFuzz/indusfuzz/issues",
}

CLOUD_PRESETS = {
    "deepseek": {"name": "DeepSeek", "base_url": "https://api.deepseek.com/v1", "default_model": "deepseek-chat"},
    "openai": {"name": "OpenAI", "base_url": "https://api.openai.com/v1", "default_model": "gpt-4o-mini"},
    "custom": {"name": "自定义云端 API", "base_url": "", "default_model": ""},
}

TOTAL_STEPS = 6
MIN_USER_PORT = 1024
MAX_PORT_SEARCH = 100


class GoBack(Exception):
    pass


def _step_header(idx, title):
    print()
    print("=" * 60)
    print(f"  步骤 [{idx}/{TOTAL_STEPS}]  {title}")
    print("=" * 60)


def _display_name(protocol_key):
    meta = _scan_protocols().get(protocol_key)
    if meta:
        return meta.get("display_name", protocol_key)
    return protocol_key


def _get_default_port(protocol_key):
    meta = _scan_protocols().get(protocol_key)
    if meta:
        return meta.get("default_port", 5020)
    return 5020


def _safe_input(prompt):
    try:
        val = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise GoBack()
    if val.lower() in ("q", "quit", "exit"):
        raise GoBack()
    return val


def _confirm(prompt="确认？(y=确认 / n=重选 / q=返回): "):
    while True:
        ans = _safe_input(prompt).lower()
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("请输入 y / n / q")


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        # 自动迁移历史明文 API Key 为 DPAPI 加密存储
        model = cfg.get("model", {})
        if model and isinstance(model, dict):
            migrated = security.migrate_plaintext_config(model)
            if migrated is not model:
                cfg["model"] = migrated
                # 回写加密后的配置
                try:
                    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                        json.dump(cfg, f, ensure_ascii=False, indent=2)
                except Exception:
                    pass
        return cfg
    except Exception:
        return {}


def save_config(new_data):
    existing = load_config()
    # 加密 model.api_key 后再落盘
    model = new_data.get("model", {})
    if model and isinstance(model, dict) and model.get("api_key"):
        new_data = dict(new_data)
        new_data["model"] = security.store_api_key(model, model["api_key"])
    existing.update(new_data)
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print_error(f"保存配置失败: {e}")


def _load_registry():
    registry = {}
    for name, meta in _scan_protocols().items():
        path = os.path.join(FUNC_CODES_DIR, f"{name}_func_codes.json")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not data.get("func_codes"):
                print_warn(f"⚠️  [menu] 协议 {name} 的功能码 JSON 无 func_codes 字段，该协议将不显示")
                continue
            registry[name] = data
        except Exception as e:
            print_warn(f"⚠️  [menu] 协议 {name} 的功能码 JSON 解析失败（{type(e).__name__}），该协议将不显示")
            continue
    return registry


def check_environment():
    result = {"python": True, "ollama": False, "ollama_models": []}
    no_proxy = urllib.request.ProxyHandler({})
    opener = urllib.request.build_opener(no_proxy)
    try:
        req = urllib.request.Request("http://127.0.0.1:11434/api/tags", method="GET")
        with opener.open(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            result["ollama"] = True
            result["ollama_models"] = [m.get("name", "") for m in data.get("models", [])]
    except Exception:
        pass
    return result

def _test_llm_connection(base_url, api_key, model_name, timeout=15):
    try:
        import openai
        import httpx
    except ImportError:
        return False, "openai 库未安装，无法测试连通性", 0.0

    import time
    start = time.time()
    is_local = "localhost" in base_url or "127.0.0.1" in base_url
    try:
        if is_local:
            http_client = httpx.Client(trust_env=False, timeout=timeout)
            client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout, http_client=http_client)
        else:
            client = openai.OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        elapsed = time.time() - start
        return True, f"响应正常，耗时 {elapsed:.2f}s", elapsed
    except Exception as e:
        elapsed = time.time() - start
        err_str = str(e)
        s = err_str.lower()

        if "429" in err_str:
            return False, "云端 API 限流（429），免费额度已用完或请求过于频繁", elapsed
        if "401" in err_str or "invalid_api_key" in s:
            return False, "API Key 无效或认证失败（401）", elapsed
        if "403" in err_str:
            return False, "API Key 无访问权限（403）", elapsed
        if "404" in err_str:
            return False, "模型名或 API 地址错误（404）", elapsed
        if "500" in err_str:
            return False, "云端服务内部错误（500）", elapsed
        if "502" in err_str:
            return False, "网关错误（502）", elapsed
        if "503" in err_str:
            return False, "服务暂不可用（503）", elapsed
        if "timeout" in s or "timed out" in s:
            return False, f"连接超时（{timeout}s），网络不通或服务响应过慢", elapsed
        if "connect" in s or "connection" in s:
            return False, "无法连接服务器，请检查网络或 API 地址", elapsed
        return False, f"未知错误：{err_str[:150]}", elapsed

def _is_port_available(host, port, timeout=0.3):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            result = s.connect_ex((host, port))
            return result != 0
    except Exception:
        return True


def _find_free_port(host, start_port, max_tries=MAX_PORT_SEARCH, min_port=MIN_USER_PORT):
    if start_port < min_port:
        start_port = min_port
    for offset in range(max_tries):
        candidate = start_port + offset
        if candidate > 65535:
            break
        if _is_port_available(host, candidate):
            return candidate
    return None


def _confirm_model_config(model_cfg):
    print()
    print("--- 模型配置摘要 ---")
    print(f"  提供商: {model_cfg.get('provider')}")
    print(f"  模型名: {model_cfg.get('name')}")
    print(f"  地址:   {model_cfg.get('base_url')}")
    if model_cfg.get("provider") != "none":
        key = model_cfg.get("api_key", "")
        print(f"  API Key: {security.mask_key(key) if key else '(未设置)'}")
    print()
    print("  ℹ️  此模型是全局设置，将对所有协议生效")
    print()
    return _confirm("确认使用此配置？(y/n/q): ")


def _select_ollama_model():
    try:
        env = check_environment()
        if not env["ollama"]:
            print("[模型] Ollama 服务不可用")
            print("[模型] 请先启动 Ollama: ollama serve")
            return None

        models = env["ollama_models"]
        if not models:
            print("[模型] Ollama 已启动，但没有已下载的模型")
            print("[模型] 请先下载模型，例如: ollama pull qwen2.5-coder:14b")
            return None

        while True:
            print()
            print("--- 选择 Ollama 本地模型 ---")
            for i, m in enumerate(models, start=1):
                print(f"  [{i}] {m}")
            print(f"  [Q] 返回模型选择主菜单")

            choice = _safe_input("请选择 [编号]: ")
            if not choice:
                print("输入不能为空")
                continue
            try:
                idx = int(choice)
            except ValueError:
                print_warn("编号格式错误")
                continue
            if idx < 1 or idx > len(models):
                print(f"编号 {idx} 超出范围")
                continue

            model_name = models[idx - 1]
            cfg = {
                "provider": "ollama",
                "name": model_name,
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",
            }
            if _confirm_model_config(cfg):
                return cfg
    except GoBack:
        print()
        print("[返回] 已取消，返回模型选择主菜单")
        return None


def _select_cloud_model():
    try:
        print()
        print("--- 选择云端 API ---")
        presets = list(CLOUD_PRESETS.items())
        for i, (key, meta) in enumerate(presets, start=1):
            print(f"  [{i}] {meta['name']}")
        print(f"  [Q] 返回模型选择主菜单")

        while True:
            choice = _safe_input("请选择 [编号]: ")
            if not choice:
                print("输入不能为空")
                continue
            try:
                idx = int(choice)
            except ValueError:
                print_warn("编号格式错误")
                continue
            if idx < 1 or idx > len(presets):
                print(f"编号 {idx} 超出范围")
                continue
            preset_key, preset_meta = presets[idx - 1]
            break

        print()
        default_url = preset_meta["base_url"] or "https://api.example.com/v1"
        url_input = _safe_input(f"API 地址 [默认 {default_url}]: ")
        base_url = url_input or preset_meta["base_url"]
        if not base_url:
            while True:
                base_url = _safe_input("API 地址（必填）: ")
                if base_url:
                    break
                print("API 地址不能为空")
        ok, err = security.validate_cloud_url(base_url, "cloud")
        if not ok:
            print_warn(f"⚠️  {err}")
            print("请使用 HTTPS 地址，或返回选择本地 Ollama。")
            return None

        default_model = preset_meta["default_model"] or "gpt-4o-mini"
        model_input = _safe_input(f"模型名 [默认 {default_model}]: ")
        model_name = model_input or default_model
        if not model_name:
            while True:
                model_name = _safe_input("模型名（必填）: ")
                if model_name:
                    break
                print("模型名不能为空")

        api_key = _safe_input("API Key: ")
        if not api_key:
            while True:
                api_key = _safe_input("API Key（必填）: ")
                if api_key:
                    break
                print("API Key 不能为空")

        print()
        print("--- 模型配置摘要 ---")
        print(f"  提供商: cloud")
        print(f"  模型名: {model_name}")
        print(f"  地址:   {base_url}")
        print(f"  API Key: {security.mask_key(api_key)}")
        print()

        print("[连通测试] 正在测试与云端 API 的连接，请稍候...")
        ok, msg, elapsed = _test_llm_connection(base_url, api_key, model_name)

        if ok:
            print_ok(f"[连通测试] ✓ 成功：{msg}")
        else:
            print_error(f"[连通测试] ✗ 失败：{msg}")
            print()
            print("  可能的原因：")
            print("    - API Key 无效或已过期")
            print("    - 免费额度已用完（429）")
            print("    - 模型名不正确")
            print("    - API 地址不正确")
            print("    - 网络无法访问该地址")
            print()
            while True:
                ans = _safe_input("是否仍然使用此配置？(y=继续使用 / n=重新配置 / q=返回): ").lower()
                if ans in ("y", "yes"):
                    break
                if ans in ("n", "no"):
                    return None
                if ans in ("q", "quit", "exit"):
                    raise GoBack()
                print("请输入 y / n / q")

        cfg = {
            "provider": "cloud",
            "name": model_name,
            "base_url": base_url,
            "api_key": api_key,
        }
        if _confirm("确认使用此配置？(y/n/q): "):
            return cfg
    except GoBack:
        print()
        print("[返回] 已取消，返回模型选择主菜单")
        return None


def _select_custom_local_model():
    try:
        print()
        print("--- 自定义本地模型 ---")
        print("适用于 vLLM、LM Studio、LocalAI、Xinference 等本地推理服务")

        default_url = "http://localhost:8000/v1"
        url_input = _safe_input(f"API 地址 [默认 {default_url}]: ")
        base_url = url_input or default_url
        ok, err = security.validate_cloud_url(base_url, "ollama")
        if not ok:
            print_warn(f"⚠️  {err}")
            return None

        default_model = "local-model"
        model_input = _safe_input(f"模型名 [默认 {default_model}]: ")
        model_name = model_input or default_model

        api_key = _safe_input("API Key [默认 local]: ") or "local"

        print()
        print("--- 模型配置摘要 ---")
        print(f"  提供商: custom")
        print(f"  模型名: {model_name}")
        print(f"  地址:   {base_url}")
        print(f"  API Key: {security.mask_key(api_key)}")
        print()

        print("[连通测试] 正在测试与本地服务的连接，请稍候...")
        ok, msg, elapsed = _test_llm_connection(base_url, api_key, model_name)

        if ok:
            print_ok(f"[连通测试] ✓ 成功：{msg}")
        else:
            print_error(f"[连通测试] ✗ 失败：{msg}")
            print()
            print("  可能的原因：")
            print("    - 本地推理服务未启动")
            print("    - API 地址或端口不正确")
            print("    - 模型名不正确")
            print("    - API Key 无效")
            print()
            while True:
                ans = _safe_input("是否仍然使用此配置？(y=继续使用 / n=重新配置 / q=返回): ").lower()
                if ans in ("y", "yes"):
                    break
                if ans in ("n", "no"):
                    return None
                if ans in ("q", "quit", "exit"):
                    raise GoBack()
                print("请输入 y / n / q")

        cfg = {
            "provider": "custom",
            "name": model_name,
            "base_url": base_url,
            "api_key": api_key,
        }
        if _confirm("确认使用此配置？(y/n/q): "):
            return cfg
    except GoBack:
        print()
        print("[返回] 已取消，返回模型选择主菜单")
        return None

def select_model():
    _step_header(1, "选择模型（全局设置）")
    print()
    print("  此模型将对所有协议统一生效，只需选择一次")
    print("  如需更换模型，请重新运行程序并选择新模型")

    existing = load_config().get("model", {})

    while True:
        print()
        print("============================ 选择模型来源 ============================")
        if existing:
            provider = existing.get("provider", "?")
            name = existing.get("name", "?")
            print(f"     [0] 使用上次的选择（{provider} / {name}）")
        print("     [1] 本地 Ollama（自动列出已下载模型）")
        print("     [2] 云端 API（DeepSeek / OpenAI / 自定义）")
        print(" 安全提示：使用云端 API 时数据会发送到第三方，敏感场景请勿使用")
        print("     [3] 自定义本地模型（vLLM / LM Studio / LocalAI）")
        print("     [4] 不使用 LLM（仅用本地变异回退）")
        print("     [Q] 退出程序")
        print()

        try:
            choice = _safe_input("请选择 [0/1/2/3/4/q]: ")
        except GoBack:
            raise

        if choice == "0" and existing:
            return existing
        if choice == "1":
            cfg = _select_ollama_model()
            if cfg:
                return cfg
            continue
        if choice == "2":
            cfg = _select_cloud_model()
            if cfg:
                return cfg
            continue
        if choice == "3":
            cfg = _select_custom_local_model()
            if cfg:
                return cfg
            continue
        if choice == "4":
            cfg = {"provider": "none", "name": "", "base_url": "", "api_key": ""}
            print()
            print("已选择不使用 LLM，将使用本地变异策略")
            try:
                if _confirm("确认？(y/n/q): "):
                    return cfg
            except GoBack:
                continue
            continue

        print("请输入 0、1、2、3、4 或 q")


def select_gpu_acceleration(model_cfg):
    provider = model_cfg.get("provider", "none")
    if provider not in ("ollama", "custom"):
        return {"enabled": False, "reason": "云端或无模型，不需要 GPU 加速", "gpus": []}

    print()
    print(f"  当前模型提供商: {provider}")
    print("  GPU 加速可显著提升本地大模型推理速度")
    print()

    while True:
        ans = _safe_input("是否启用 GPU 加速？(y=启用 / n=不启用 / q=返回上一步): ").lower()
        if ans in ("y", "yes"):
            print("  正在检测 GPU ...")
            from src.core.gpu_detector import detect_gpu, get_gpu_summary
            has_gpu, gpus, err = detect_gpu()
            if has_gpu:
                summary = get_gpu_summary(gpus)
                print(f"  ✓ 检测到 GPU: {summary}")
                print("  GPU 加速已启用（推理时将使用 GPU）")
                return {"enabled": True, "gpus": gpus, "summary": summary}
            print(f"  ✗ 未检测到可用 GPU: {err}")
            print("  无法启用 GPU 加速，将使用 CPU 推理")
            print("  建议：1) 确认已安装 NVIDIA 驱动；2) 确认显卡支持 CUDA；3) 选择不启用")
            print()
            while True:
                retry = _safe_input("是否重新检测？(y=重新检测 / n=不启用继续): ").lower()
                if retry in ("y", "yes"):
                    break
                if retry in ("n", "no"):
                    return {"enabled": False, "reason": "无可用 GPU", "gpus": []}
                print("请输入 y / n")
            continue
        if ans in ("n", "no"):
            return {"enabled": False, "reason": "用户选择不启用", "gpus": []}
        if ans == "q":
            raise GoBack()
        print("请输入 y / n / q")


def select_protocol():
    _step_header(2, "选择协议类型")
    print()
    print("  可选一个或多个协议，测试会按顺序执行")

    registry = _load_registry()
    if not registry:
        print("未找到任何已注册协议（功能码定义文件缺失）")
        raise GoBack()

    protocol_list = list(registry.keys())
    last_selection = load_config().get("last_selection", {})
    last_protocols = [p for p in last_selection.get("protocols", []) if p in registry]

    while True:
        print()
        print("======== 选择协议 ========")
        if last_protocols:
            names = ", ".join([_display_name(p) for p in last_protocols])
            print(f"  [0] 使用上次的选择（{names}）")
        for i, p in enumerate(protocol_list, start=1):
            print(f"  [{i}] {_display_name(p)}")
        print(f"  [A] 全部协议")
        print(f"  [Q] 返回上一步")
        print()

        choice = _safe_input("请输入编号（多个用逗号分隔，如 1,2）: ")
        if not choice:
            print("输入不能为空，请重新输入")
            continue

        if choice.upper() == "A":
            selected = protocol_list
        elif choice == "0" and last_protocols:
            selected = last_protocols
        else:
            parts = [x.strip() for x in choice.split(",") if x.strip()]
            if not parts:
                print("输入不能为空，请重新输入")
                continue

            selected = []
            valid = True
            for part in parts:
                try:
                    idx = int(part)
                except ValueError:
                    print(f"编号 {part} 格式错误，请重新输入")
                    valid = False
                    break
                if idx < 1 or idx > len(protocol_list):
                    print(f"编号 {idx} 超出范围，请重新输入")
                    valid = False
                    break
                name = protocol_list[idx - 1]
                if name not in selected:
                    selected.append(name)

            if not valid or not selected:
                continue

        names = [_display_name(p) for p in selected]
        print(f"你选择的协议: {', '.join(names)}")
        if _confirm("确认？(y=确认 / n=重选 / q=返回): "):
            return selected


def _manual_input_func_codes(funcs):
    all_codes = {f["code"].lower(): f["name"] for f in funcs}
    while True:
        raw = _safe_input("请输入功能码（十六进制，多个用逗号分隔，如 0x01,0x03，q=返回）: ")
        if not raw:
            print("输入不能为空，请重新输入")
            continue

        raw_codes = [x.strip().lower() for x in raw.split(",") if x.strip()]
        if not raw_codes:
            print("输入不能为空，请重新输入")
            continue

        selected = []
        restart = False
        for c in raw_codes:
            if not c.startswith("0x"):
                c = "0x" + c
            if c in all_codes:
                if c not in selected:
                    selected.append(c)
            else:
                ans = _safe_input(f"功能码 {c} 未定义，是否跳过？(y/n/q): ").lower()
                if ans in ("n", "no"):
                    print("请重新输入完整的功能码列表")
                    restart = True
                    break

        if restart:
            continue

        if selected:
            print(f"你选择的功能码: {', '.join(selected)}")
            if _confirm("确认？(y=确认 / n=重选 / q=返回): "):
                return selected
            continue
        print("未选中任何有效功能码，请重新输入")


def select_func_codes(protocol_name):
    registry = _load_registry()
    if protocol_name not in registry:
        print(f"协议 {protocol_name} 未注册")
        raise GoBack()

    info = registry[protocol_name]
    funcs = info.get("func_codes", [])
    if not funcs:
        print(f"协议 {protocol_name} 未定义功能码")
        raise GoBack()

    while True:
        print()
        print(f"======== 选择功能码（{_display_name(protocol_name)}）========")
        for i, f in enumerate(funcs, start=1):
            print(f"  [{i}] {f['code']} {f['name']}")
        print(f"  [A] 全部功能码")
        print(f"  [M] 手动输入")
        print(f"  [Q] 返回上一步")
        print()

        choice = _safe_input("请输入编号（多个用逗号分隔，如 1,3）: ")
        if not choice:
            print("输入不能为空，请重新输入")
            continue

        if choice.upper() == "A":
            selected = [f["code"] for f in funcs]
        elif choice.upper() == "M":
            selected = _manual_input_func_codes(funcs)
            if selected:
                return selected
            continue
        else:
            parts = [x.strip() for x in choice.split(",") if x.strip()]
            if not parts:
                print("输入不能为空，请重新输入")
                continue

            selected = []
            valid = True
            for part in parts:
                try:
                    idx = int(part)
                except ValueError:
                    print(f"编号 {part} 格式错误，请重新输入")
                    valid = False
                    break
                if idx < 1 or idx > len(funcs):
                    print(f"编号 {idx} 超出范围，请重新输入")
                    valid = False
                    break
                code = funcs[idx - 1]["code"]
                if code not in selected:
                    selected.append(code)

            if not valid or not selected:
                continue

        print(f"你选择的功能码: {', '.join(selected)}")
        if _confirm("确认？(y=确认 / n=重选 / q=返回): "):
            return selected


def _parse_host_port(raw, default_host=None, default_port=5020):
    raw = raw.strip()
    if not raw:
        if default_host is None:
            return None, None, "输入不能为空"
        return default_host, default_port, None

    if ":" in raw:
        host, port_str = raw.rsplit(":", 1)
        if not host:
            return None, None, "主机地址不能为空"
        try:
            port = int(port_str)
        except ValueError:
            return None, None, "端口格式错误"
        if port < 1 or port > 65535:
            return None, None, "端口范围 1-65535"
        return host, port, None
    else:
        if default_host is None:
            return raw, default_port, None
        try:
            port = int(raw)
        except ValueError:
            return raw, default_port, None
        if port < 1 or port > 65535:
            return None, None, "端口范围 1-65535"
        return default_host, port, None


def _select_local_targets(protocols):
    print()
    print("--- 本机自测 ---")
    print("将自动为每个选定协议启动本地从站，测试完自动停止")
    print("每个协议默认端口如下：")
    print()

    host = "127.0.0.1"
    default_ports = {p: _get_default_port(p) for p in protocols}

    for p in protocols:
        port = default_ports[p]
        status = "可用" if _is_port_available(host, port) else "已占用"
        mark = "✓" if status == "可用" else "✗"
        print(f"  {mark} {_display_name(p)} → {host}:{port}  [{status}]")
    print()

    print("======== 端口配置方式 ========")
    print("  [1] 自动分配（默认端口被占用时自动 +1 向上查找）")
    print("  [2] 自定义端口（为每个协议手动指定）")
    print("  [Q] 返回上一步")
    print()

    while True:
        mode = _safe_input("请选择 [1/2/q]: ").strip()

        if mode == "1":
            targets = {}
            print()
            for p in protocols:
                default_port = default_ports[p]
                if _is_port_available(host, default_port):
                    chosen = default_port
                    note = "默认可用"
                else:
                    chosen = _find_free_port(host, default_port)
                    if chosen is None:
                        print(f"  ✗ {_display_name(p)}：从 {default_port} 起 {MAX_PORT_SEARCH} 个端口都不可用")
                        raise GoBack()
                    note = f"默认 {default_port} 被占用，自动分配到 {chosen}"
                targets[p] = f"{host}:{chosen}"
                print(f"  {_display_name(p)} → {host}:{chosen}  [{note}]")
            print()
            if _confirm("确认？(y=确认 / n=重选 / q=返回): "):
                return targets
            continue

        if mode == "2":
            targets = {}
            print()
            print(f"为每个协议指定端口（范围 {MIN_USER_PORT}-65535，q=返回）")
            print()
            for p in protocols:
                default_port = default_ports[p]
                while True:
                    raw = _safe_input(f"{_display_name(p)} 端口 [默认 {default_port}]: ")
                    if not raw:
                        port = default_port
                    else:
                        try:
                            port = int(raw)
                        except ValueError:
                            print_warn("端口格式错误")
                            continue
                        if port < MIN_USER_PORT or port > 65535:
                            print(f"端口范围 {MIN_USER_PORT}-65535（非管理员端口）")
                            continue

                    if not _is_port_available(host, port):
                        print(f"端口 {port} 已被占用")
                        ans = _safe_input("是否自动分配可用端口？(y/n/q): ").lower()
                        if ans in ("y", "yes"):
                            auto = _find_free_port(host, port)
                            if auto is None:
                                print("未找到可用端口，请重新输入")
                                continue
                            port = auto
                            print(f"已自动分配到 {port}")
                        elif ans in ("n", "no"):
                            continue
                        else:
                            raise GoBack()

                    targets[p] = f"{host}:{port}"
                    break

            print()
            print("--- 最终配置 ---")
            for p, t in targets.items():
                print(f"  {_display_name(p)}: {t}")
            print()
            if _confirm("确认？(y=确认 / n=重选 / q=返回): "):
                return targets
            continue

        print("请输入 1、2 或 q")


def _select_lan_target():
    print()
    print("--- 局域网设备 ---")
    print("示例：192.168.1.100:5020")
    print("注意：所有选定协议将使用同一个目标 IP:端口")
    print()
    while True:
        raw = _safe_input("目标 IP:端口（q=返回上一步）: ")
        if not raw:
            print("输入不能为空，请重新输入")
            continue
        host, port, err = _parse_host_port(raw, default_host=None, default_port=5020)
        if err:
            print(f"{err}，请重新输入")
            continue
        if host in ("127.0.0.1", "localhost"):
            print("局域网设备不能用 127.0.0.1，请重新输入")
            continue

        target = f"{host}:{port}"
        print(f"目标: {target}")
        if _confirm("确认？(y=确认 / n=重输 / q=返回): "):
            return target


def _select_production_target():
    print()
    print("--- 真实工业设备 ---")
    print_warn("⚠️  生产环境测试可能导致设备停机、产线瘫痪、甚至安全事故")
    print_warn("⚠️  必须在获得设备所有者的书面授权后才能继续")
    print_warn("⚠️  生产网络复杂，可能存在防火墙、路由、网段隔离等问题")
    print()

    if not _confirm("确认已获得书面授权？(y=已授权 / n=返回上一步 / q=返回): "):
        raise GoBack()

    print()
    print("请输入设备信息：")
    while True:
        raw = _safe_input("目标 IP:端口（q=返回上一步）: ")
        if not raw:
            print("输入不能为空，请重新输入")
            continue
        host, port, err = _parse_host_port(raw, default_host=None, default_port=502)
        if err:
            print(f"{err}，请重新输入")
            continue
        if host in ("127.0.0.1", "localhost"):
            print("真实设备不能用 127.0.0.1，请重新输入")
            continue

        target = f"{host}:{port}"
        print()
        print("请再次确认设备信息和授权情况：")
        print(f"  目标设备: {target}")
        print(f"  已获授权: 是")
        if _confirm("确认开始测试？(y=确认 / n=重输 / q=返回): "):
            return target


PROTOCOL_CONNECT_PARAMS = {
    "modbus": {
        "default_port": 502,
        "extra": [
            {"key": "unit_id", "label": "Unit ID", "default": 1, "type": "int", "min": 1, "max": 255, "hint": "1-255，部分设备用 255"},
        ],
    },
    "s7comm": {
        "default_port": 102,
        "extra": [
            {"key": "rack", "label": "Rack", "default": 0, "type": "int", "min": 0, "max": 7, "hint": "通常为 0"},
            {"key": "slot", "label": "Slot", "default": 1, "type": "int", "min": 1, "max": 31, "hint": "S7-300/400 常用 2 或 3，S7-1200/1500 用 1"},
        ],
    },
    "dnp3": {
        "default_port": 20000,
        "extra": [
            {"key": "master_addr", "label": "Master Address", "default": 1, "type": "int", "min": 0, "max": 65519, "hint": "主站地址"},
            {"key": "outstation_addr", "label": "Outstation Address", "default": 10, "type": "int", "min": 0, "max": 65519, "hint": "从站地址"},
        ],
    },
    "iec104": {
        "default_port": 2404,
        "extra": [
            {"key": "common_addr", "label": "Common Address", "default": 1, "type": "int", "min": 0, "max": 65535, "hint": "公共地址，需与设备一致"},
        ],
    },
    "iec61850": {
        "default_port": 102,
        "extra": [
            {"key": "ied_ref", "label": "IED 引用", "default": "", "type": "str", "hint": "可选，留空自动发现"},
        ],
    },
    "enip": {
        "default_port": 44818,
        "extra": [
            {"key": "slot", "label": "CPU 槽号", "default": 0, "type": "int", "min": 0, "max": 255, "hint": "默认 0"},
        ],
    },
    "opcua": {
        "default_port": 4840,
        "extra": [
            {"key": "security_policy", "label": "安全策略", "default": "None", "type": "str", "hint": "None / Basic128Rsa15 / Basic256"},
        ],
        "use_endpoint": True,
    },
}


def _is_valid_ip(host):
    try:
        socket.inet_aton(host)
        return True
    except Exception:
        return False


def _parse_endpoint_url(url):
    url = url.strip()
    if not url.startswith("opc.tcp://"):
        return None, None, "Endpoint URL 必须以 opc.tcp:// 开头"
    rest = url[len("opc.tcp://"):]
    if ":" not in rest:
        return None, None, "Endpoint URL 必须包含端口，格式 opc.tcp://IP:端口"
    host, port_str = rest.rsplit(":", 1)
    if not host:
        return None, None, "主机地址不能为空"
    try:
        port = int(port_str)
    except ValueError:
        return None, None, "端口格式错误"
    if port < 1 or port > 65535:
        return None, None, "端口范围 1-65535"
    return host, port, None


def _prompt_int(prompt, default, min_val=None, max_val=None):
    while True:
        raw = _safe_input(prompt)
        if not raw:
            return default
        try:
            val = int(raw)
        except ValueError:
            print_warn("请输入整数")
            continue
        if min_val is not None and val < min_val:
            print_warn(f"取值不能小于 {min_val}")
            continue
        if max_val is not None and val > max_val:
            print_warn(f"取值不能大于 {max_val}")
            continue
        return val


def _select_connect_params(protocols, scenario):
    print()
    print(f"--- {SCENARIO_NAME.get(scenario, scenario)} 连接参数配置 ---")
    if scenario == "production":
        print_warn("⚠️  生产环境：请确认参数与设备实际配置完全一致")
    print()

    connect_params = {}
    targets = {}

    for p in protocols:
        schema = PROTOCOL_CONNECT_PARAMS.get(p)
        if not schema:
            print_warn(f"⚠️  协议 {p} 未定义连接参数模板，使用默认值")
            schema = {"default_port": 502, "extra": []}

        print(f"======== {_display_name(p)} ========")

        use_endpoint = schema.get("use_endpoint", False)
        if use_endpoint:
            default_port = schema["default_port"]
            while True:
                default_url = f"opc.tcp://192.168.1.100:{default_port}"
                raw = _safe_input(f"Endpoint URL [默认 {default_url}]: ")
                url = raw or default_url
                host, port, err = _parse_endpoint_url(url)
                if err:
                    print_warn(f"{err}，请重新输入")
                    continue
                break
            endpoint = url
        else:
            while True:
                host = _safe_input("设备 IP（必填，q=返回上一步）: ")
                if not host:
                    print("IP 不能为空，请重新输入")
                    continue
                if not _is_valid_ip(host):
                    print_warn(f"IP 格式无效：{host}，请重新输入")
                    continue
                break
            default_port = schema["default_port"]
            while True:
                raw = _safe_input(f"端口 [默认 {default_port}]: ")
                if not raw:
                    port = default_port
                    break
                try:
                    port = int(raw)
                except ValueError:
                    print_warn("端口格式错误，请输入整数")
                    continue
                if port < 1 or port > 65535:
                    print("端口范围 1-65535")
                    continue
                break

        extra = {}
        for field in schema.get("extra", []):
            key = field["key"]
            label = field["label"]
            default = field["default"]
            ftype = field["type"]
            hint = field.get("hint", "")
            prompt = f"{label}"
            if hint:
                prompt += f"（{hint}）"
            prompt += f" [默认 {default if default != '' else '空'}]: "
            if ftype == "int":
                val = _prompt_int(prompt, default, min_val=field.get("min"), max_val=field.get("max"))
            else:
                val = _safe_input(prompt)
                if val == "":
                    val = default
            extra[key] = val

        if use_endpoint:
            extra["endpoint"] = endpoint

        connect_params[p] = {"host": host, "port": port, "extra": extra}
        targets[p] = f"{host}:{port}"
        print(f"  → {host}:{port}")
        if extra:
            parts = [f"{k}={v}" for k, v in extra.items() if k != "endpoint"]
            if use_endpoint:
                parts.insert(0, f"endpoint={endpoint}")
            print(f"  → 参数: {', '.join(parts)}")
        print()

    print("--- 连接参数汇总 ---")
    for p, cp in connect_params.items():
        print(f"  {_display_name(p)}: {cp['host']}:{cp['port']}")
    print()
    if _confirm("确认连接参数？(y=确认 / n=重输 / q=返回): "):
        return connect_params, targets
    return None, None


def _select_scenario():
    print()
    print("======== 选择目标场景 ========")
    print("  [1] 本机自测       （每个协议用默认端口）")
    print("  [2] 局域网设备     （自定义 IP:端口）")
    print("  [3] 真实工业设备   （自定义 IP:端口，需授权）")
    print("  [Q] 返回上一步")
    print()

    while True:
        choice = _safe_input("请选择 [1/2/3/q]: ")
        if choice == "1":
            scenario = "local"
        elif choice == "2":
            scenario = "lan"
        elif choice == "3":
            scenario = "production"
        else:
            print("请输入 1、2、3 或 q")
            continue

        print(f"你选择的场景: {SCENARIO_NAME[scenario]}")
        if _confirm("确认？(y=确认 / n=重选 / q=返回): "):
            return scenario


def select_target(protocols):
    _step_header(4, "选择目标地址")
    print()
    print("  不同场景使用不同地址和超时策略")
    print("  本机自测：每个协议自动使用默认端口")
    print("  局域网/真实设备：逐个协议配置 IP、端口及协议参数")

    scenario = _select_scenario()

    if scenario == "local":
        targets = _select_local_targets(protocols)
        if targets is None:
            raise GoBack()
        return targets, scenario, None

    connect_params, targets = _select_connect_params(protocols, scenario)
    if connect_params is None:
        raise GoBack()
    return targets, scenario, connect_params


def check_target_reachable(target, timeout=6):
    if ":" in target:
        host, port_str = target.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            return False, "端口格式错误"
    else:
        host = target
        port = 5020

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except socket.timeout:
        return False, f"连接超时（{timeout}s）"
    except ConnectionRefusedError:
        return False, "连接被拒绝（目标未监听该端口）"
    except socket.gaierror:
        return False, "无法解析主机名"
    except OSError as e:
        return False, f"网络错误: {e}"


def print_troubleshooting(host, port, scenario, err):
    timeout = SCENARIO_TIMEOUT.get(scenario, 6)
    print()
    print("=" * 56)
    print(f"  ⚠️  目标不可达: {err}")
    print("=" * 56)
    print()
    print(f"目标: {host}:{port}")
    print(f"场景: {SCENARIO_NAME.get(scenario, scenario)}")
    print(f"超时: {timeout} 秒")
    print()
    print("请按以下顺序排查：")
    print(f"  [1] 检查目标 IP 是否正确 → 确认 {host} 拼写无误")
    print(f"  [2] 检查网络连通性 → ping {host}")
    print(f"  [3] 检查端口是否开放 → Test-NetConnection {host} -Port {port}")
    print(f"  [4] 检查目标防火墙 → 是否拦截 {port} 端口")
    print(f"  [5] 检查从站服务 → netstat -ano | findstr {port}")
    print(f"  [6] 检查跨网段路由 → 是否同一局域网/VPN")
    print()
    print("=" * 56)
    print("  如果以上 6 项均排查失败，请联系开发者")
    print("=" * 56)
    print(f"  开发者: {DEVELOPER_CONTACT['name']}")
    print(f"  邮箱:   {DEVELOPER_CONTACT['email']}")
    print()

    try:
        collect = input("是否自动收集环境信息（推荐）？(y/n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if collect in ("y", "yes"):
        try:
            from src.core.diagnose import run_diagnostics
            run_diagnostics(f"{host}:{port}", scenario)
        except Exception as e:
            print(f"[诊断] 收集失败: {type(e).__name__}: {e}")
            print("[诊断] 请手动截图上述排查信息发给开发者")
    else:
        print()
        print("提交时请附上：")
        print(f"  - 完整终端输出截图")
        print(f"  - 目标地址: {host}:{port}")
        print(f"  - 场景类型: {SCENARIO_NAME.get(scenario, scenario)}")
        print(f"  - 网络拓扑: (你的电脑 → 交换机/路由器 → 目标设备)")
        print()


def confirm_and_start(config):
    _step_header(6, "确认并开始")

    if "slave_mode" not in config:
        config["slave_mode"] = "strict"

    model = config.get("model", {})
    print()
    print("======== 全局模型配置 ========")
    print(f"  提供商: {model.get('provider')}")
    print(f"  模型名: {model.get('name')}")
    print(f"  地址:   {model.get('base_url')}")
    gpu = config.get("gpu", {})
    if gpu.get("enabled"):
        print(f"  GPU加速: 已启用 ({gpu.get('summary', '未知设备')})")
    else:
        reason = gpu.get("reason", "未启用")
        print(f"  GPU加速: 未启用 ({reason})")
    print()
    print("======== 协议与功能码 ========")
    for p in config["protocols"]:
        name = _display_name(p)
        codes = config["func_codes"].get(p, [])
        print(f"  {name}: {', '.join(codes)}")
    print()
    print("======== 目标与超时 ========")
    print(f"  场景: {SCENARIO_NAME.get(config.get('scenario', ''), '未知')}")
    targets = config.get("targets", {})
    for p, t in targets.items():
        print(f"  {_display_name(p)}: {t}")
    print(f"  超时: {config.get('timeout', 6)} 秒")
    if config.get("scenario") == "local":
        mode_name = "严格" if config["slave_mode"] == "strict" else "宽松"
        print(f"  [高级] 从站模式: [{mode_name}]（输入 L 切换）")
    elif config.get("connect_params"):
        print("  连接参数:")
        for p, cp in config["connect_params"].items():
            extra = cp.get("extra", {})
            parts = [f"{k}={v}" for k, v in extra.items()]
            extra_str = f"（{', '.join(parts)}）" if parts else ""
            print(f"    {_display_name(p)}: {cp['host']}:{cp['port']} {extra_str}")
    print()

    while True:
        ans = _safe_input("是否开始测试？(y=开始 / n=返回上一步 / q=返回): ").lower()
        if ans == "l" and config.get("scenario") == "local":
            config["slave_mode"] = "loose" if config["slave_mode"] == "strict" else "strict"
            mode_name = "严格" if config["slave_mode"] == "strict" else "宽松"
            print(f"  [高级] 从站模式已切换为: [{mode_name}]（输入 L 可切回）")
            print()
            continue
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("请输入 y / n / q")


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


def interactive_flow():
    steps = ["model", "protocol", "func_codes", "target", "check", "confirm"]
    state = {}
    idx = 0

    while 0 <= idx < len(steps):
        step = steps[idx]

        try:
            if step == "model":
                model_cfg = select_model()
                state["model"] = model_cfg
                gpu_cfg = select_gpu_acceleration(model_cfg)
                state["gpu"] = gpu_cfg
                idx += 1

            elif step == "protocol":
                protocols = select_protocol()
                state["protocols"] = protocols
                idx += 1

            elif step == "func_codes":
                _step_header(3, "选择功能码")
                print()
                print(f"  已选协议: {', '.join([_display_name(p) for p in state['protocols']])}")
                func_codes = {}
                for p in state["protocols"]:
                    codes = select_func_codes(p)
                    func_codes[p] = codes
                if not func_codes:
                    idx -= 1
                    continue
                state["func_codes"] = func_codes
                idx += 1

            elif step == "target":
                targets, scenario, connect_params = select_target(state["protocols"])
                state["targets"] = targets
                state["scenario"] = scenario
                state["connect_params"] = connect_params
                state["timeout"] = SCENARIO_TIMEOUT.get(scenario, 6)
                idx += 1

            elif step == "check":
                _step_header(5, "连通性检查")
                if state["scenario"] == "local":
                    print()
                    print("[检查] 本机自测，跳过连通性检查")
                    idx += 1
                    continue

                first_target = list(state["targets"].values())[0] if state["targets"] else None
                if not first_target:
                    idx += 1
                    continue

                host, port = _parse_target(first_target)
                print()
                print(f"[检查] 测试目标 {host}:{port} 连通性（超时 {state['timeout']}s）...")
                ok, err = check_target_reachable(first_target, timeout=state["timeout"])
                if not ok:
                    print_troubleshooting(host, port, state["scenario"], err)
                    print()
                    while True:
                        ans = _safe_input("是否仍要继续？(y=继续 / n=返回上一步 / q=返回): ").lower()
                        if ans in ("y", "yes"):
                            print("[警告] 继续运行，可能出现大量连接失败")
                            break
                        if ans in ("n", "no"):
                            raise GoBack()
                        print("请输入 y / n / q")
                else:
                    print(f"[检查] 目标可达 ✓")
                idx += 1

            elif step == "confirm":
                if confirm_and_start(state):
                    return state
                idx -= 1

        except GoBack:
            idx -= 1
            if idx < 0:
                return None

    return None
