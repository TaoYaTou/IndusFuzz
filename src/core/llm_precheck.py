"""
LLM 预连通性检查 + fuzz 整体超时熔断。

被 fuzz_loop_llm.py 在每个协议开始前调用，
失败时会把 fuzz_llm_status 置为 error 并记录原因。
"""
import time


LLM_PRECHECK_TIMEOUT = 15   # 预连通性测试超时（秒）
PROTOCOL_FUZZ_TIMEOUT = 120 # 单协议整体 fuzz 超时（秒）


def precheck_llm(model_cfg, lang="zh"):
    """
    在 fuzz 开始前做一次真正的 LLM 调用（只发 "ping" + max_tokens=5）。

    Returns:
        (ok: bool, msg: str, elapsed: float|None, diagnostics: dict)
        diagnostics 包含 detailed 错误分类，给 report 用。
    """
    diagnostics = {
        "check": "llm_precheck",
        "provider": model_cfg.get("provider", "none"),
        "base_url": model_cfg.get("base_url", ""),
        "model_name": model_cfg.get("name", ""),
        "error_code": None,
        "error_type": None,
        "suggestion": None,
    }

    provider = model_cfg.get("provider", "none")
    if provider in ("none", "", None):
        msg_zh = "未配置 LLM provider（none），所有变异将使用本地随机变异"
        msg_en = "No LLM provider configured, all mutations will be local random"
        diagnostics["error_type"] = "no_provider"
        return True, msg_zh if lang == "zh" else msg_en, None, diagnostics

    # Ollama 本地 — 如果 provider=ollama 跳过预检查
    if provider == "ollama":
        msg_zh = "本地 Ollama provider，跳过预连通性检查"
        return True, msg_zh, None, diagnostics

    try:
        import openai
    except ImportError:
        msg_zh = "openai 库未安装，无法测试 LLM 连通性"
        diagnostics["error_type"] = "missing_openai_lib"
        return False, msg_zh, None, diagnostics

    resolved = _resolve_for_precheck(model_cfg)
    if resolved is None:
        diagnostics["error_type"] = "config_unresolvable"
        return False, f"LLM 配置无法解析（provider={provider}）", None, diagnostics

    start = time.time()
    try:
        base_url = resolved["base_url"]
        is_local = "localhost" in base_url or "127.0.0.1" in base_url
        if is_local:
            import httpx
            http_client = httpx.Client(trust_env=False, timeout=LLM_PRECHECK_TIMEOUT)
            client = openai.OpenAI(
                base_url=base_url,
                api_key=resolved["api_key"],
                timeout=LLM_PRECHECK_TIMEOUT,
                http_client=http_client,
            )
        else:
            client = openai.OpenAI(
                base_url=base_url,
                api_key=resolved["api_key"],
                timeout=LLM_PRECHECK_TIMEOUT,
            )
        response = client.chat.completions.create(
            model=resolved["name"],
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        elapsed = time.time() - start
        diagnostics["elapsed"] = round(elapsed, 2)
        return (
            True,
            f"LLM 连通正常（{elapsed:.2f}s，模型 {resolved['name']}）",
            elapsed,
            diagnostics,
        )
    except Exception as e:
        elapsed = time.time() - start
        err_str = str(e)
        s = err_str.lower()

        # 分类错误
        if "timeout" in s or "timed out" in s or "connect timeout" in s:
            diagnostics["error_code"] = "TIMEOUT"
            diagnostics["error_type"] = "network_timeout"
            diagnostics["suggestion"] = "网络不通或 API 地址错误，检查 base_url 能否从本机访问；如果是内网 API 确认防火墙没拦"
        elif "429" in err_str or "rate limit" in s or "quota" in s or "insufficient" in s:
            diagnostics["error_code"] = "429"
            diagnostics["error_type"] = "rate_limited"
            diagnostics["suggestion"] = "云端 API 限流或免费额度用完，本次 fuzz 将完全使用本地随机变异"
        elif "401" in err_str or "invalid_api_key" in s or "authentication" in s or "unauthorized" in s:
            diagnostics["error_code"] = "401"
            diagnostics["error_type"] = "auth_failed"
            diagnostics["suggestion"] = "API Key 无效或已过期，请在配置菜单里重新输入"
        elif "403" in err_str or "forbidden" in s:
            diagnostics["error_code"] = "403"
            diagnostics["error_type"] = "access_denied"
            diagnostics["suggestion"] = "API Key 没有该模型的访问权限"
        elif "404" in err_str or "not found" in s:
            diagnostics["error_code"] = "404"
            diagnostics["error_type"] = "model_not_found"
            diagnostics["suggestion"] = "模型名错误或 base_url 路径错误，检查配置"
        elif "400" in err_str or "bad request" in s:
            diagnostics["error_code"] = "400"
            diagnostics["error_type"] = "bad_request"
            diagnostics["suggestion"] = "请求格式错误，可能是 base_url 路径不对（v1/chat/completions）"
        elif "500" in err_str:
            diagnostics["error_code"] = "500"
            diagnostics["error_type"] = "server_internal"
            diagnostics["suggestion"] = "云端服务内部错误，稍后重试"
        elif "502" in err_str:
            diagnostics["error_code"] = "502"
            diagnostics["error_type"] = "gateway_error"
            diagnostics["suggestion"] = "云端网关错误，稍后重试或更换端点"
        elif "503" in err_str:
            diagnostics["error_code"] = "503"
            diagnostics["error_type"] = "service_unavailable"
            diagnostics["suggestion"] = "云端服务暂不可用，稍后重试"
        elif "connection refused" in s:
            diagnostics["error_code"] = "CONN_REFUSED"
            diagnostics["error_type"] = "connection_refused"
            diagnostics["suggestion"] = "无法连接到 API 服务器，检查 base_url 和网络"
        else:
            diagnostics["error_code"] = "UNKNOWN"
            diagnostics["error_type"] = "unknown"
            diagnostics["suggestion"] = f"未知错误：{err_str[:200]}，请将此错误信息反馈"

        diagnostics["raw_error"] = err_str[:500]
        diagnostics["elapsed"] = round(elapsed, 2)
        return False, f"LLM 连通失败 [{diagnostics['error_code']}]：{err_str[:120]}", elapsed, diagnostics


def _resolve_for_precheck(model_cfg):
    """和 llm_mutator._resolve_provider 逻辑相同，但独立复制避免 cross-module dep。"""
    provider = model_cfg.get("provider", "none")
    if provider in ("ollama", "local"):
        base_url = model_cfg.get("base_url") or "http://localhost:11434/v1"
        name = model_cfg.get("name") or "qwen2.5-coder"
        return {"base_url": base_url, "api_key": model_cfg.get("api_key") or "ollama", "name": name}
    if provider == "none":
        return None
    base_url = model_cfg.get("base_url")
    name = model_cfg.get("name")
    api_key = model_cfg.get("api_key")
    if not base_url or not name:
        return None
    return {"base_url": base_url, "api_key": api_key or "", "name": name}


def make_timeout_excepthook_for_protocol(protocol_name, diagnostics, lang="zh"):
    """
    在协议超时后被调用 — 向 diagnostics 写入原因，fuzz_loop 会用 diagnostics 写 error_report。
    这个函数本身不生成报告，只是收集诊断信息。
    """
    diagnostics["timeout_triggered"] = True
    diagnostics["error_type"] = "protocol_timeout"
    diagnostics["error_code"] = "TIMEOUT"
    provider = diagnostics.get("provider", "unknown")
    if lang == "zh":
        if provider == "ollama":
            diagnostics["suggestion"] = (
                f"协议 {protocol_name} 的 fuzz 超过 {PROTOCOL_FUZZ_TIMEOUT} 秒未完成。"
                "当前使用本地 Ollama，最可能原因是本地模型推理过慢。"
                "建议：1) 选择更少的功能码（5-10 个）；"
                "2) 使用更小的模型（如 qwen2.5-coder:3b）；"
                "3) 如使用 CPU 推理，考虑 GPU 加速。"
            )
        elif provider in ("none", "", None):
            diagnostics["suggestion"] = (
                f"协议 {protocol_name} 的 fuzz 超过 {PROTOCOL_FUZZ_TIMEOUT} 秒未完成。"
                "当前未配置 LLM，超时可能是目标设备无响应或网络问题。"
            )
        else:
            diagnostics["suggestion"] = (
                f"协议 {protocol_name} 的 fuzz 超过 {PROTOCOL_FUZZ_TIMEOUT} 秒未完成，"
                "可能是云端 API 响应过慢或网络不稳定。"
                "建议：1) 选择更少的功能码；"
                "2) 确认 API Key 有效且额度充足；"
                "3) 如网络不稳定，改用本地 Ollama。"
            )
    else:
        if provider == "ollama":
            diagnostics["suggestion"] = (
                f"Protocol {protocol_name} fuzz exceeded {PROTOCOL_FUZZ_TIMEOUT}s. "
                "Using local Ollama — likely slow local inference. "
                "Suggestions: 1) Select fewer function codes (5-10); "
                "2) Use a smaller model (e.g. qwen2.5-coder:3b); "
                "3) Enable GPU acceleration if on CPU."
            )
        elif provider in ("none", "", None):
            diagnostics["suggestion"] = (
                f"Protocol {protocol_name} fuzz exceeded {PROTOCOL_FUZZ_TIMEOUT}s. "
                "No LLM configured — likely target not responding or network issue."
            )
        else:
            diagnostics["suggestion"] = (
                f"Protocol {protocol_name} fuzz exceeded {PROTOCOL_FUZZ_TIMEOUT}s. "
                "Likely slow cloud API response or unstable network. "
                "Suggestions: 1) Select fewer function codes; "
                "2) Verify API key and quota; "
                "3) Switch to local Ollama if network is unstable."
            )
    return diagnostics
