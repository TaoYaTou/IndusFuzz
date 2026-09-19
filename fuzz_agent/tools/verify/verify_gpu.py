import os
import sys

FUZZ_AGENT = r"d:\Application\AllToolsSet\AgnetPrograms\IndusFuzz\fuzz_agent"
sys.path.insert(0, FUZZ_AGENT)
os.chdir(FUZZ_AGENT)

checks = []


def check(name, ok):
    checks.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name)


from src.core.gpu_detector import detect_gpu, get_gpu_summary
has_gpu, gpus, err = detect_gpu()
check("GPU检测返回结构正确", isinstance(has_gpu, bool) and (gpus is not None or err is not None))
if has_gpu:
    check("检测到NVIDIA GPU", gpus is not None and len(gpus) > 0)
    check("GPU名称非空", all(g.get("name") for g in gpus))
    summary = get_gpu_summary(gpus)
    check("GPU摘要含显存", "GB" in summary)
    print(f"  检测到: {summary}")
else:
    check("无GPU时返回错误信息", err is not None)
    print(f"  无GPU: {err}")

from src.core.runtime_config import set_gpu_config, is_gpu_enabled, get_gpu_summary
set_gpu_config(False, "")
check("runtime_config默认关闭", is_gpu_enabled() is False)
set_gpu_config(True, "RTX 4060 (8GB)")
check("runtime_config设置生效", is_gpu_enabled() is True)
check("runtime_config摘要", get_gpu_summary() == "RTX 4060 (8GB)")

from src.protocols.modbus.llm_mutator import _extra_body
set_gpu_config(False, "")
body_off = _extra_body({"provider": "ollama"})
check("GPU关闭时extra_body无num_gpu", "num_gpu" not in body_off)

set_gpu_config(True, "RTX 4060 (8GB)")
body_on_ollama = _extra_body({"provider": "ollama"})
check("GPU开启+ollama时extra_body含num_gpu=99", body_on_ollama.get("num_gpu") == 99)

body_on_cloud = _extra_body({"provider": "cloud"})
check("GPU开启+cloud时extra_body无num_gpu", "num_gpu" not in body_on_cloud)

for proto in ["modbus", "s7comm", "dnp3", "iec104", "iec61850", "enip", "opcua"]:
    mod = __import__(f"src.protocols.{proto}.llm_mutator", fromlist=["_extra_body"])
    body = mod._extra_body({"provider": "ollama"})
    check(f"{proto} llm_mutator 含_extra_body且GPU时num_gpu=99", body.get("num_gpu") == 99)

from src.core import menu
set_gpu_config(False, "")

inputs = iter(["y", "n"])
orig = menu._safe_input
menu._safe_input = lambda p: next(inputs)
try:
    cfg = {"provider": "ollama", "name": "qwen2.5-coder:7b", "base_url": "http://localhost:11434/v1"}
    gpu_cfg = menu.select_gpu_acceleration(cfg)
    captured = gpu_cfg
finally:
    menu._safe_input = orig
check("ollama+选y→GPU启用", captured.get("enabled") is True and len(captured.get("gpus", [])) > 0)
check("GPU摘要含RTX", "RTX" in captured.get("summary", ""))

inputs2 = iter(["n"])
menu._safe_input = lambda p: next(inputs2)
try:
    gpu_cfg2 = menu.select_gpu_acceleration({"provider": "ollama"})
finally:
    menu._safe_input = orig
check("ollama+选n→GPU未启用", gpu_cfg2.get("enabled") is False)

gpu_cfg3 = menu.select_gpu_acceleration({"provider": "cloud", "name": "gpt-4o", "base_url": "https://api.openai.com/v1"})
check("cloud模型不询问GPU直接返回未启用", gpu_cfg3.get("enabled") is False)

gpu_cfg4 = menu.select_gpu_acceleration({"provider": "none"})
check("none模型不询问GPU直接返回未启用", gpu_cfg4.get("enabled") is False)

print("=" * 60)
all_pass = all(ok for _, ok in checks)
print(f"GPU加速验证: {sum(1 for _, ok in checks if ok)}/{len(checks)} " + ("PASS" if all_pass else "FAIL"))
sys.exit(0 if all_pass else 1)
