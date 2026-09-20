import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# FLAT MIGRATION (v1.8.3): scripts used to live under fuzz_agent/tools/verify/
# now they live at tools/verify/, so root is two levels up.
FUZZ_AGENT = os.path.dirname(os.path.dirname(_HERE))
sys.path.insert(0, FUZZ_AGENT)
os.chdir(FUZZ_AGENT)

from src.core.report_generator import _render_slave_notice, generate_report
from src.core import menu

checks = []


def check(name, ok):
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


strict_html = "\n".join(_render_slave_notice("s7comm", "local", "zh", "strict"))
check("严格模式行显示", "模拟从站模式" in strict_html and "严格" in strict_html)
check("严格模式无警示框", "宽松模式警示" not in strict_html)

loose_html = "\n".join(_render_slave_notice("s7comm", "local", "zh", "loose"))
check("宽松模式行显示", "宽松" in loose_html)
check("宽松模式警示框", "宽松模式警示" in loose_html and "全 NORMAL 是预期行为" in loose_html)
check("警示框含切换指引", "输入 L" in loose_html)

lan_html = "\n".join(_render_slave_notice("s7comm", "lan", "zh", "strict"))
check("非local场景不显示模式行", lan_html == "")

en_loose = "\n".join(_render_slave_notice("s7comm", "local", "en", "loose"))
check("英文版警示框", "Loose Mode Warning" in en_loose)

strict_en = "\n".join(_render_slave_notice("s7comm", "local", "en", "strict"))
check("英文版严格模式行", "Slave Mode" in strict_en and "Strict" in strict_en)

results = [
    {
        "round": 1,
        "func_code": 0x11,
        "mutation": "aa",
        "response": "03000001000a00000385010000000000",
        "classification": "EXCEPTION",
    }
]
rp, lp = generate_report(
    results, [], [], protocol_name="s7comm", target="127.0.0.1:15103", scenario="local", slave_mode="loose"
)
with open(rp, "r", encoding="utf-8") as f:
    html = f.read()
check("宽松报告HTML含模式行", "模拟从站模式" in html)
check("宽松报告HTML含警示框", "宽松模式警示" in html)
check("宽松报告PDF生成", os.path.exists(rp.replace(".html", ".pdf")))

rp2, _ = generate_report(results, [], [], protocol_name="s7comm", target="127.0.0.1:15103", scenario="local")
with open(rp2, "r", encoding="utf-8") as f:
    html2 = f.read()
check("默认参数=严格模式", "严格（从站校验请求报文）" in html2)
check("默认无警示框", "宽松模式警示" not in html2)

inputs = iter(["l", "y"])
captured = {}
orig_safe_input = menu._safe_input
menu._safe_input = lambda prompt: next(inputs)
try:
    cfg = {
        "model": {"provider": "none", "name": "", "base_url": ""},
        "protocols": ["s7comm"],
        "func_codes": {"s7comm": ["0x04"]},
        "targets": {"s7comm": "127.0.0.1:5020"},
        "scenario": "local",
        "timeout": 2,
    }
    ok = menu.confirm_and_start(cfg)
    captured["ret"] = ok
    captured["mode"] = cfg.get("slave_mode")
finally:
    menu._safe_input = orig_safe_input
check("L切换到宽松并确认开始", captured.get("ret") is True and captured.get("mode") == "loose")

inputs2 = iter(["y"])
menu._safe_input = lambda prompt: next(inputs2)
try:
    cfg2 = {
        "model": {"provider": "none", "name": "", "base_url": ""},
        "protocols": ["s7comm"],
        "func_codes": {"s7comm": ["0x04"]},
        "targets": {"s7comm": "127.0.0.1:5020"},
        "scenario": "local",
        "timeout": 2,
    }
    ok2 = menu.confirm_and_start(cfg2)
    mode2 = cfg2.get("slave_mode")
finally:
    menu._safe_input = orig_safe_input
check("不按L默认严格", ok2 is True and mode2 == "strict")

inputs3 = iter(["l", "l", "y"])
menu._safe_input = lambda prompt: next(inputs3)
try:
    cfg3 = {
        "model": {"provider": "none", "name": "", "base_url": ""},
        "protocols": ["s7comm"],
        "func_codes": {"s7comm": ["0x04"]},
        "targets": {"s7comm": "127.0.0.1:5020"},
        "scenario": "lan",
        "timeout": 6,
    }
    ok3 = menu.confirm_and_start(cfg3)
    lan_mode = cfg3.get("slave_mode")
finally:
    menu._safe_input = orig_safe_input
check("lan场景L无效且不写入模式", ok3 is True and lan_mode == "strict")

from src.core.slave_launcher import start_slave
import inspect

sig = inspect.signature(start_slave)
check("start_slave默认strict=True", sig.parameters["strict"].default is True)

print("=" * 60)
all_pass = all(ok for _, ok in checks)
print(f"接线验证: {sum(1 for _, ok in checks if ok)}/{len(checks)} " + ("PASS" if all_pass else "FAIL"))
sys.exit(0 if all_pass else 1)
