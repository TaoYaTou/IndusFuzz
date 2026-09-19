import os
import sys
import glob

ROOT = os.path.dirname(os.path.abspath(__file__))
FUZZ_AGENT = os.path.dirname(os.path.dirname(ROOT))  # FLAT MIGRATION: scripts at tools/verify/, root is two levels up
sys.path.insert(0, FUZZ_AGENT)
os.chdir(FUZZ_AGENT)

results = []


def check(item, expect, got):
    status = "PASS" if expect == got else "FAIL"
    results.append((status, item, expect, got))
    print(f"[{status}] {item}: 期望 {expect}，实际 {got}")


try:
    import src.core.fuzz_loop_llm  # noqa: F401
    check("7.2 fuzz_loop_llm 导入", "OK", "OK")
except Exception as e:
    check("7.2 fuzz_loop_llm 导入", "OK", f"CRASH: {e}")
    sys.exit(1)

from src.protocols import registry
protocols = sorted(registry.list_protocols())
check("7.2 registry 协议数", "7", str(len(protocols)))
check("7.2 registry 协议列表", "dnp3,enip,iec104,iec61850,modbus,opcua,s7comm", ",".join(protocols))

try:
    import src.core.menu  # noqa: F401
    check("7.3 menu.py 导入", "OK", "OK")
except Exception as e:
    check("7.3 menu.py 导入", "OK", f"CRASH: {e}")

from src.core import slave_launcher
missing = []
for p in ["modbus", "s7comm", "dnp3", "iec104", "iec61850", "enip", "opcua"]:
    path = slave_launcher._get_slave_script(p)
    if not path:
        missing.append(p)
check("7.4 从站脚本发现(7个)", "0缺失", f"{len(missing)}缺失{(':' + ','.join(missing)) if missing else ''}")

from src.core import report_generator
cfg_keys = sorted(report_generator.PROTOCOL_CONFIG.keys())
check("7.5 PROTOCOL_CONFIG 条目数", "7", str(len(cfg_keys)))
check("7.5 PROTOCOL_CONFIG 覆盖", "dnp3,enip,iec104,iec61850,modbus,opcua,s7comm", ",".join(cfg_keys))

# v1.7.1 重构后 timeout=25 收敛至 llm_mutator_base.py，7 个协议 llm_mutator.py 为薄壳继承基类
base_path = os.path.join(FUZZ_AGENT, "src", "protocols", "llm_mutator_base.py")
base_ok = False
if os.path.exists(base_path):
    with open(base_path, "r", encoding="utf-8") as fh:
        base_ok = "timeout=25" in fh.read()
check("7.7 llm_mutator_base timeout=25", "True", str(base_ok))

core_menu = open(os.path.join(FUZZ_AGENT, "src", "core", "menu.py"), encoding="utf-8").read()
core_fll = open(os.path.join(FUZZ_AGENT, "src", "core", "fuzz_loop_llm.py"), encoding="utf-8").read()
anti = []
for name, content in (("menu.py", core_menu), ("fuzz_loop_llm.py", core_fll)):
    for proto in ("s7comm", "dnp3", "iec104", "iec61850", "opcua"):
        if f"elif" in content and f'"{proto}"' in content:
            for line in content.splitlines():
                if line.strip().startswith("elif") and proto in line:
                    anti.append(f"{name}:{line.strip()[:60]}")
check("7.8 核心无协议 if-elif 反模式", "0", str(len(anti)))
for a in anti:
    print("    -> " + a)

hosts = []
for f in glob.glob(os.path.join(FUZZ_AGENT, "server", "*_server.py")):
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    if '0.0.0.0' in content:
        hosts.append(os.path.basename(f))
    if 'DEFAULT_HOST = "127.0.0.1"' not in content:
        hosts.append(os.path.basename(f) + "(无127.0.0.1默认)")
check("5.12.1 server 默认绑定 127.0.0.1", "全部合规", "违规: " + ",".join(hosts) if hosts else "全部合规")

danger = []
for pattern in ("eval(", "exec(", "pickle.loads", "os.system"):
    for f in glob.glob(os.path.join(FUZZ_AGENT, "server", "*_server.py")) + glob.glob(
        os.path.join(FUZZ_AGENT, "src", "protocols", "*", "*.py")
    ):
        with open(f, "r", encoding="utf-8") as fh:
            if pattern in fh.read():
                danger.append(f"{os.path.relpath(f, FUZZ_AGENT)}:{pattern}")
check("5.12.4 无危险调用", "0", str(len(danger)))
for d in danger:
    print("    -> " + d)

key_hits = []
for f in glob.glob(os.path.join(FUZZ_AGENT, "src", "protocols", "*", "*.py")):
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    for marker in ("sk-", "api_key=\"", "api_key='", "API_KEY=\"", "API_KEY='"):
        if marker in content:
            key_hits.append(f"{os.path.relpath(f, FUZZ_AGENT)}:{marker}")
check("5.12.2 无硬编码密钥", "0", str(len(key_hits)))
for k in key_hits:
    print("    -> " + k)

strict_hits = []
for f in glob.glob(os.path.join(FUZZ_AGENT, "server", "*_server.py")):
    with open(f, "r", encoding="utf-8") as fh:
        content = fh.read()
    name = os.path.basename(f)
    if "--strict" not in content or "--port" not in content or "--host" not in content:
        strict_hits.append(name)
check("5.12.5+ 全从站支持 --host/--port/--strict", "全部合规", "缺失: " + ",".join(strict_hits) if strict_hits else "全部合规")

fails = [r for r in results if r[0] == "FAIL"]
print(f"\n阶段7+5.12 静态检查: 总计 {len(results)} 项，通过 {len(results) - len(fails)} 项，失败 {len(fails)} 项")
sys.exit(1 if fails else 0)

