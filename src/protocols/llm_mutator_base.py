import os
import re
import json

try:
    import openai
    import httpx
    _OPENAI_AVAILABLE = True
except ImportError:
    _OPENAI_AVAILABLE = False

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".indusfuzz", "config.json")
_HEX_CHARS = set("0123456789abcdefABCDEF")

from src.core.runtime_config import is_gpu_enabled


def _extra_body(resolved):
    body = {"num_predict": 4096}
    if is_gpu_enabled() and resolved.get("provider") == "ollama":
        body["num_gpu"] = 99
    return body


def _parse_error(err_str):
    s = err_str.lower()
    if "429" in err_str or "rate limit" in s:
        return "429", "云端 API 限流，免费额度已用完或请求过于频繁，请稍后重试或升级套餐"
    if "401" in err_str or "invalid_api_key" in s:
        return "401", "认证失败，API Key 无效或已过期"
    if "403" in err_str:
        return "403", "访问被拒绝，API Key 无该模型的访问权限"
    if "404" in err_str:
        return "404", "资源不存在，模型名或 API 地址错误"
    if "500" in err_str:
        return "500", "云端服务内部错误，请稍后重试"
    if "502" in err_str:
        return "502", "网关错误，云端服务不可用"
    if "503" in err_str:
        return "503", "云端服务暂时不可用，请稍后重试"
    if "timeout" in s or "timed out" in s:
        return "TIMEOUT", "请求超时，网络不通或服务响应过慢"
    if "connect" in s or "connection" in s:
        return "CONN", "无法连接服务器，请检查网络或 API 地址"
    return "", ""


def _load_model_config(log_prefix="LLM"):
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("model", {})
    except Exception as e:
        print(f"[{log_prefix}] 读取配置失败: {type(e).__name__}: {e}")
        return {}


def _resolve_provider(cfg, log_prefix="LLM"):
    provider = (cfg.get("provider") or "none").lower()
    if provider == "none":
        return None
    name = cfg.get("name") or "qwen2.5-coder:14b"
    base_url = cfg.get("base_url") or ""
    api_key = cfg.get("api_key") or ""
    if provider == "ollama":
        base_url = base_url or "http://localhost:11434/v1"
        api_key = api_key or "ollama"
    elif provider in ("cloud", "deepseek", "openai"):
        if not base_url:
            if provider == "deepseek":
                base_url = "https://api.deepseek.com/v1"
            elif provider == "openai":
                base_url = "https://api.openai.com/v1"
        if not base_url:
            print(f"[{log_prefix}] 云端 provider 缺少 base_url")
            return None
        if not api_key:
            print(f"[{log_prefix}] 云端 provider 缺少 api_key")
            return None
    elif provider == "custom":
        base_url = base_url or "http://localhost:8000/v1"
        api_key = api_key or "local"
    else:
        print(f"[{log_prefix}] 未知 provider: {provider}")
        return None
    return {"provider": provider, "base_url": base_url, "api_key": api_key, "name": name}


def _clean_line(line):
    line = line.strip()
    line = re.sub(r'^\d+[\.\)]\s*', '', line)
    line = line.replace("`", "").replace("hex", "").replace("plaintext", "")
    line = line.strip()
    if not line:
        return None
    if not all(c in _HEX_CHARS for c in line):
        return None
    if len(line) < 2:
        return None
    if len(line) % 2 != 0:
        line = line[:-1]
    if len(line) < 2:
        return None
    return line.lower()


def generate_mutations(base_payload_hex, count, prompt, log_prefix="LLM",
                       max_retries=3, status_collector=None, func_code_str=None,
                       stop_event=None):
    """Generate mutations via LLM, cooperative-cancellable via stop_event.

    stop_event (threading.Event, optional): if set, aborts immediately and returns [].
    """
    if stop_event and stop_event.is_set():
        print(f"[{log_prefix}] stop_event 已触发，跳过 LLM 变异")
        return []

    if not _OPENAI_AVAILABLE:
        print(f"[{log_prefix}] openai 库未安装，跳过 LLM 变异")
        if status_collector:
            status_collector.on_fallback_only(func_code_str or '?')
        return []

    model_cfg = _load_model_config(log_prefix)
    if not model_cfg:
        print(f"[{log_prefix}] ~/.indusfuzz/config.json 中无 model 配置")
        return []

    provider = model_cfg.get("provider", "none")
    if provider == "none" or not provider:
        print(f"[{log_prefix}] provider={provider}，跳过 LLM 变异")
        if status_collector:
            status_collector.on_fallback_only(func_code_str or '?')
        return []

    resolved = _resolve_provider(model_cfg, log_prefix)
    if resolved is None:
        print(f"[{log_prefix}] provider={provider} 解析失败，跳过 LLM 变异")
        if status_collector:
            status_collector.on_fallback_only(func_code_str or '?')
        return []

    try:
        base_url = resolved["base_url"]
        is_local = "localhost" in base_url or "127.0.0.1" in base_url
        if is_local:
            http_client = httpx.Client(trust_env=False, timeout=25)
            client = openai.OpenAI(
                base_url=base_url,
                api_key=resolved["api_key"],
                timeout=25,
                max_retries=0,
                http_client=http_client,
            )
        else:
            client = openai.OpenAI(
                base_url=base_url,
                api_key=resolved["api_key"],
                timeout=25,
                max_retries=0,
            )
    except Exception as e:
        print(f"[{log_prefix}] 创建客户端失败: {type(e).__name__}: {e}")
        return []

    print(f"[{log_prefix}] 使用模型: {resolved['name']} @ {resolved['base_url']}")
    if status_collector:
        if hasattr(status_collector, "set_model_info"):
            status_collector.set_model_info(
                provider=provider, name=resolved["name"], base_url=resolved["base_url"]
            )
        status_collector.on_call(func_code_str or '?')

    base_len = len(base_payload_hex) if base_payload_hex else 0

    for attempt in range(max_retries):
        if stop_event and stop_event.is_set():
            print(f"[{log_prefix}] stop_event 已触发，中止 LLM 变异")
            return []
        try:
            response = client.chat.completions.create(
                model=resolved["name"],
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                extra_body=_extra_body(resolved),
            )
            msg = response.choices[0].message
            content = msg.content if msg and msg.content else ""
            if not content:
                print(f"[{log_prefix}] 第 {attempt + 1} 次尝试返回空内容")
                if status_collector:
                    status_collector.on_error(func_code_str or '?', "EMPTY_RESP", "模型返回空内容")
                continue
            content = content.strip()
            print(f"[{log_prefix}] 原始返回:", content[:200])

            lines = content.split("\n")
            mutations = []
            seen = set()
            for line in lines:
                cleaned = _clean_line(line)
                if cleaned is None or cleaned in seen:
                    continue
                if base_len > 0:
                    clen = len(cleaned)
                    if clen < base_len // 2 or clen > base_len * 2:
                        print(f"[{log_prefix}] 丢弃长度异常变异: len={clen}, base={base_len}")
                        continue
                seen.add(cleaned)
                mutations.append(cleaned)

            if mutations:
                if status_collector:
                    status_collector.on_success(func_code_str or '?', len(mutations), count)
                return mutations[:count]
            print(f"[{log_prefix}] 第 {attempt + 1} 次尝试未生成有效变异")

        except Exception as e:
            err_str = str(e)
            code, note = _parse_error(err_str)
            if code:
                print(f"[{log_prefix}] 第 {attempt + 1} 次尝试失败 [{code}]：{note}")
                if status_collector:
                    status_collector.on_error(func_code_str or '?', code, note)
            else:
                print(f"[{log_prefix}] 第 {attempt + 1} 次尝试失败：{err_str[:200]}")
                if status_collector:
                    status_collector.on_error(func_code_str or '?', "UNKNOWN", err_str[:120])

    print(f"[{log_prefix}] 重试全部失败，返回空列表")
    if status_collector:
        status_collector.on_fallback_only(func_code_str or "?")
    return []
