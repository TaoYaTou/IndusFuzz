import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# FLAT MIGRATION (v1.8.1): scripts used to live under fuzz_agent/tools/verify/
# now they live at tools/verify/, so root is two levels up.
FUZZ_AGENT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, FUZZ_AGENT)
os.chdir(FUZZ_AGENT)

from src.core.report_generator import generate_combined_report, generate_error_report, LOG_FILENAME, _strip_emoji
from src.core.runtime_config import set_gpu_config

checks = []


def check(name, ok):
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


set_gpu_config(False, "")

single_data = [{
    "protocol_name": "s7comm",
    "target": "127.0.0.1:5020",
    "results": [
        {"round": 1, "func_code": 0x04, "mutation": "aa", "response": "bb", "classification": "NORMAL", "severity": "low"},
        {"round": 1, "func_code": 0x11, "mutation": "cc", "response": "dd", "classification": "EXCEPTION", "severity": "high"},
    ],
    "skipped": [],
    "build_failures": [],
    "llm_status": None,
    "slave_mode": "strict",
    "protocol_timed_out": False,
}]

multi_data = single_data + [{
    "protocol_name": "dnp3",
    "target": "127.0.0.1:20000",
    "results": [
        {"round": 1, "func_code": 0x01, "mutation": "ee", "response": "ff", "classification": "NORMAL", "severity": "low"},
    ],
    "skipped": [],
    "build_failures": [],
    "llm_status": None,
    "slave_mode": "strict",
    "protocol_timed_out": True,
}]

log_path = os.path.join(FUZZ_AGENT, "reports", LOG_FILENAME)
if os.path.exists(log_path):
    os.remove(log_path)

rp1, pdf1, lp1 = generate_combined_report(single_data, scenario="local")
check("单协议报告HTML生成", os.path.exists(rp1) and os.path.getsize(rp1) > 0)
check("单协议报告PDF生成", os.path.exists(pdf1) and os.path.getsize(pdf1) > 0)
check("日志文件生成", os.path.exists(lp1) and os.path.getsize(lp1) > 0)

with open(rp1, "r", encoding="utf-8") as f:
    html1 = f.read()
check("单协议HTML含中英双语标题", "模糊测试报告" in html1 and "Fuzz Test Report" in html1)
check("单协议HTML含协议选择器(单协议不应有)", "protocol-section" not in html1 or "filterProtocol" not in html1)
check("单协议HTML含s7comm内容", "s7comm" in html1 or "S7Comm" in html1)

rp2, pdf2, lp2 = generate_combined_report(multi_data, scenario="local")
check("多协议报告HTML生成", os.path.exists(rp2) and os.path.getsize(rp2) > 0)
check("多协议报告PDF生成", os.path.exists(pdf2) and os.path.getsize(pdf2) > 0)

with open(rp2, "r", encoding="utf-8") as f:
    html2 = f.read()
check("多协议HTML含协议选择器", "filterProtocol" in html2 and "全部" in html2)
check("多协议HTML含两个协议内容", "S7Comm" in html2 and "DNP3" in html2)
check("多协议HTML含汇总统计表", "汇总统计" in html2 or "Overall Summary" in html2)
check("多协议HTML含超时状态", "超时" in html2 or "Timeout" in html2)

check("日志文件追加(两次运行同一文件)", lp1 == lp2)
with open(lp1, "r", encoding="utf-8") as f:
    log_content = f.read()
check("日志含两次RUN标记", log_content.count("RUN START") == 2)
check("日志含s7comm和dnp3", "s7comm" in log_content and "dnp3" in log_content)

check("strip_emoji清理emoji", _strip_emoji("⚠️🔴🟡🟢 text") == " text")

err_html, err_pdf = generate_error_report(
    [{"protocol": "dnp3", "error_type": "timeout", "elapsed": 120.0, "reason": "test"}],
    1, llm_config={"provider": "ollama", "name": "qwen2.5-coder:7b"},
    suggestion="test suggestion", lang="zh",
)
check("错误报告HTML生成", os.path.exists(err_html))
check("错误报告PDF生成", os.path.exists(err_pdf))
err_json = err_html.replace(".html", ".json")
check("错误报告无JSON文件", not os.path.exists(err_json))

report_dir = os.path.join(FUZZ_AGENT, "reports")
json_files = [f for f in os.listdir(report_dir) if f.endswith(".json")]
check("reports目录无JSON文件", len(json_files) == 0)

print("=" * 60)
all_pass = all(ok for _, ok in checks)
print(f"整合报告验证: {sum(1 for _, ok in checks if ok)}/{len(checks)} " + ("PASS" if all_pass else "FAIL"))
sys.exit(0 if all_pass else 1)

