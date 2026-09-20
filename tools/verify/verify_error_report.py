import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# FLAT MIGRATION (v1.8.1): scripts used to live under fuzz_agent/tools/verify/
# now they live at tools/verify/, so root is two levels up.
FUZZ_AGENT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, FUZZ_AGENT)
os.chdir(FUZZ_AGENT)

from src.core.report_generator import generate_error_report, generate_report
from src.core.fuzz_loop_llm import _summarize_suggestions

checks = []


def check(name, ok):
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


errors = [
    {
        "protocol": "dnp3",
        "error_type": "timeout",
        "elapsed": 120.0,
        "completed_func_codes": 8,
        "total_func_codes": 22,
        "reason": "fuzz 超过 120 秒未完成，可能是 LLM 推理过慢或目标无响应",
    },
    {
        "protocol": "modbus",
        "error_type": "timeout",
        "elapsed": 120.0,
        "completed_func_codes": 10,
        "total_func_codes": 18,
        "reason": "fuzz 超过 120 秒未完成，可能是 LLM 推理过慢或目标无响应",
    },
]

ollama_cfg = {
    "provider": "ollama",
    "name": "qwen2.5-coder:7b",
    "base_url": "http://localhost:11434/v1",
    "api_key": "ollama",
}

html, pdf, json_path = generate_error_report(errors, 7, llm_config=ollama_cfg, suggestion="test", lang="zh")
check("错误报告 HTML 生成", os.path.exists(html) and os.path.getsize(html) > 0)
check("错误报告 PDF 生成", os.path.exists(pdf) and os.path.getsize(pdf) > 0)
check("错误报告 JSON 生成", os.path.exists(json_path) and os.path.getsize(json_path) > 0)

with open(html, "r", encoding="utf-8") as f:
    err_html = f.read()
check("错误报告含异常协议表", "dnp3" in err_html and "modbus" in err_html)
check("错误报告含 LLM 配置", "ollama" in err_html and "qwen2.5-coder:7b" in err_html)
check("错误报告含超时类型", "timeout" in err_html)
check("错误报告含诊断建议区", "诊断与建议" in err_html)

sug = _summarize_suggestions(errors, ollama_cfg)
check("ollama 建议含'本地推理过慢'", "本地推理过慢" in sug)
check("ollama 建议不含'云端调用卡住'", "云端调用卡住" not in sug)
check("ollama 建议含完成进度", "18/40" in sug)
check("ollama 建议含小模型建议", "qwen2.5-coder:3b" in sug)

cloud_cfg = {"provider": "cloud", "name": "gpt-4o-mini", "base_url": "https://api.openai.com/v1", "api_key": "sk-xxx"}
sug_cloud = _summarize_suggestions(errors, cloud_cfg)
check("cloud 建议含云端排查", "云端 API" in sug_cloud)
check("cloud 建议不含本地推理过慢", "本地推理过慢" not in sug_cloud)

none_cfg = {"provider": "none", "name": "", "base_url": "", "api_key": ""}
sug_none = _summarize_suggestions(errors, none_cfg)
check("none 建议不含云端", "云端" not in sug_none)

results = [
    {"round": 1, "func_code": 0x01, "mutation": "aa", "response": "bb", "classification": "NORMAL"},
    {"round": 1, "func_code": 0x01, "mutation": "cc", "response": "dd", "classification": "EXCEPTION"},
]
rp, _ = generate_report(
    results,
    [],
    [],
    protocol_name="s7comm",
    target="127.0.0.1:15103",
    scenario="local",
    protocol_timed_out=True,
    protocol_timeout=120,
)
with open(rp, "r", encoding="utf-8") as f:
    timeout_html = f.read()
check("超时报告含强制中断警示", "被强制中断" in timeout_html)
check("超时报告含 120 秒说明", "120" in timeout_html)
check("超时报告含推理过慢原因", "推理过慢" in timeout_html)
check("超时报告含功能码建议", "功能码" in timeout_html)

rp2, _ = generate_report(
    results, [], [], protocol_name="s7comm", target="127.0.0.1:15103", scenario="local", protocol_timed_out=False
)
with open(rp2, "r", encoding="utf-8") as f:
    normal_html = f.read()
check("非超时报告不含强制中断", "被强制中断" not in normal_html)

print("=" * 60)
all_pass = all(ok for _, ok in checks)
print(f"错误报告+超时+建议验证: {sum(1 for _, ok in checks if ok)}/{len(checks)} " + ("PASS" if all_pass else "FAIL"))
sys.exit(0 if all_pass else 1)
