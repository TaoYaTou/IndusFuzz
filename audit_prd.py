"""IndusFuzz 完整审计脚本 — 结构化输出 JSON

按 PRD 5.12/5.14/5.15 维度逐项执行，输出可机读指标。
用法: python audit_prd.py  (项目根目录)
"""
import os, sys, json, re, subprocess, struct
from pathlib import Path

ROOT = Path(__file__).parent
PY = str(ROOT / "agentscope_env" / "Scripts" / "python.exe")

results = {}

# ========== 5.15 目录规范体检 (12 维度) ==========
audit_5_15 = {}

# 维度 1: 顶层必存在文件
top_required = ["main.py","requirements.txt","README.md","README.zh.md","CHANGELOG.md","LICENSE",".gitignore","IndusFuzz.spec"]
d1 = {f: (ROOT/f).exists() for f in top_required}
audit_5_15["dim1_top_level"] = d1

# 维度 2: src/ 结构
d2 = {
    "__init__.py": (ROOT/"src/__init__.py").exists(),
    "core/": (ROOT/"src/core").is_dir(),
    "protocols/": (ROOT/"src/protocols").is_dir(),
    "integrations/": (ROOT/"src/integrations").is_dir(),
    "base.py": (ROOT/"src/protocols/base.py").exists(),
    "registry.py": (ROOT/"src/protocols/registry.py").exists(),
    "llm_mutator_base.py": (ROOT/"src/protocols/llm_mutator_base.py").exists(),
}
audit_5_15["dim2_src_structure"] = d2

# 维度 3: src/core 13 个
core_13 = ["version.py","menu.py","fuzz_loop_llm.py","report_generator.py",
    "slave_launcher.py","security.py","llm_precheck.py","llm_status.py",
    "runtime_config.py","diagnose.py","gpu_detector.py","color_output.py","result_analyzer.py"]
d3 = {f: (ROOT/"src/core"/f).exists() for f in core_13}
audit_5_15["dim3_core_13"] = d3

# 维度 4: src/protocols 结构
d4 = {}
protos = ["modbus","s7comm","dnp3","iec104","iec61850","enip","opcua"]
for p in protos:
    d4[p] = {
        "client.py": (ROOT/"src/protocols"/p/"client.py").exists(),
        "mutator.py": (ROOT/"src/protocols"/p/"mutator.py").exists(),
        "llm_mutator.py": (ROOT/"src/protocols"/p/"llm_mutator.py").exists(),
    }
audit_5_15["dim4_protocols"] = d4

# 维度 5: func_codes JSON 字段完整性
func_dir = ROOT/"src/protocols/func_codes"
d5 = {}
for f in sorted(func_dir.glob("*.json")):
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        d5[f.name] = {
            "has_protocol": "protocol" in d,
            "has_port": "default_port" in d,
            "codes_nonempty": isinstance(d.get("func_codes"), list) and len(d["func_codes"]) > 0,
            "n_codes": len(d.get("func_codes", [])),
        }
    except Exception as e:
        d5[f.name] = {"error": str(e)}
audit_5_15["dim5_func_codes"] = d5

# 维度 6: server/ 7 个
d6 = {}
for p in protos:
    sf = ROOT/"server"/f"{p}_server.py"
    content = sf.read_text(encoding="utf-8", errors="replace") if sf.exists() else ""
    d6[p] = {
        "exists": sf.exists(),
        "has_port_arg": "--port" in content or '"--port"' in content,
        "has_strict_arg": "--strict" in content or '"--strict"' in content,
        "binds_127": "127.0.0.1" in content,
        "binds_0_0_0": "0.0.0.0" in content,
    }
audit_5_15["dim6_servers"] = d6

# 维度 7: tests/ 目录（无 verify_*.py 混入、无 legacy）
tests_dir = ROOT/"tests"
d7 = {}
if tests_dir.is_dir():
    verify_files = list(tests_dir.glob("**/verify_*.py"))
    legacy = list(tests_dir.glob("**/legacy/**"))
    d7 = {
        "conftest.py": (tests_dir/"conftest.py").exists(),
        "test_py_count": len(list(tests_dir.glob("test_*.py"))),
        "verify_files_found": [str(p.relative_to(ROOT)) for p in verify_files],
        "legacy_found": [str(p.relative_to(ROOT)) for p in legacy],
    }
else:
    d7 = {"error": "tests/ not found"}
audit_5_15["dim7_tests"] = d7

# 维度 8: tools/
tools_dir = ROOT/"tools"
d8 = {
    "check_protocol.py": (tools_dir/"check_protocol.py").exists(),
    "clean_before_release.py": (tools_dir/"clean_before_release.py").exists(),
    "verify_dir": (tools_dir/"verify").is_dir(),
    "legacy_dir": (tools_dir/"legacy").is_dir(),
}
audit_5_15["dim8_tools"] = d8

# 维度 9: .github/
gh_dir = ROOT/".github"
d9 = {
    "exists": gh_dir.is_dir(),
    "workflows": list((gh_dir/"workflows").glob("*.yml")) if (gh_dir/"workflows").is_dir() else [],
}
audit_5_15["dim9_github"] = d9

# 维度 10: assets/
d10 = {
    "simhei.ttf": (ROOT/"assets/fonts/simhei.ttf").exists(),
    "icon.ico": (ROOT/"assets/concept_a_hex/icon.ico").exists(),
}
audit_5_15["dim10_assets"] = d10

# 维度 11: 临时文件检查（git ls-files）
try:
    r = subprocess.run(["git","ls-files"], capture_output=True, text=True, cwd=str(ROOT))
    tracked = r.stdout.splitlines()
    bad_patterns = ["__pycache__", ".pyc", ".pytest_cache", ".coverage", "coverage_html",
                    "htmlcov", "build/", "dist/", ".log", "reports/*.html", "reports/*.pdf"]
    d11 = {}
    for pat in bad_patterns:
        matches = [f for f in tracked if pat.replace("*","") in f or pat in f]
        if pat == "reports/*.html":
            matches = [f for f in tracked if f.startswith("reports/") and f.endswith(".html")]
        elif pat == "reports/*.pdf":
            matches = [f for f in tracked if f.startswith("reports/") and f.endswith(".pdf")]
        d11[pat] = matches[:5]  # 只列前5个
except Exception as e:
    d11 = {"error": str(e)}
audit_5_15["dim11_tempfiles"] = d11

# 维度 12: .gitignore 关键模式
gi = (ROOT/".gitignore").read_text(encoding="utf-8") if (ROOT/".gitignore").exists() else ""
critical = ["__pycache__", "agentscope_env", "reports/", "dist/", "build/", "htmlcov", "coverage_html",
            ".pytest_cache", ".coverage", "*.log"]
d12 = {pat: pat in gi for pat in critical}
audit_5_15["dim12_gitignore"] = d12

results["5.15"] = audit_5_15

# ========== 5.14 pytest 测试代码质量 ==========
audit_5_14 = {}

# 5.14.1 配置文件
pytest_ini = ROOT/"pytest.ini"
pyproject = ROOT/"pyproject.toml"
d141 = {
    "pytest.ini_exists": pytest_ini.exists(),
    "pyproject_exists": pyproject.exists(),
}
if pytest_ini.exists():
    d141["ini_content"] = pytest_ini.read_text(encoding="utf-8")[:500]
audit_5_14["5.14.1_config"] = d141

# 5.14.2 工具链检查
def pip_show(pkg):
    r = subprocess.run([PY,"-m","pip","show",pkg], capture_output=True, text=True, cwd=str(ROOT))
    return r.returncode == 0
audit_5_14["5.14.2_tools"] = {
    "pytest-cov": pip_show("pytest-cov"),
    "pytest-timeout": pip_show("pytest-timeout"),
    "flake8": pip_show("flake8"),
    "bandit": pip_show("bandit"),
}

# 5.14.3 空断言检查
audit_5_14["5.14.3_bad_asserts"] = []
if tests_dir.is_dir():
    for f in tests_dir.rglob("*.py"):
        try:
            content = f.read_text(encoding="utf-8")
            for lineno, line in enumerate(content.splitlines(), 1):
                if "assert True" in line or "or True" in line:
                    audit_5_14["5.14.3_bad_asserts"].append(f"{f.relative_to(ROOT)}:{lineno} {line.strip()}")
        except: pass

# 5.14.4 绝对路径硬编码
audit_5_14["5.14.4_abs_paths"] = []
for base in [tests_dir, ROOT/"src"]:
    for f in base.rglob("*.py"):
        try:
            content = f.read_text(encoding="utf-8")
            for lineno, line in enumerate(content.splitlines(), 1):
                if re.search(r'["\']([A-Z]:\\[^\s"\']+)["\']', line) or re.search(r'["\'](/(?:home|Users)/[^\s"\']+)["\']', line):
                    audit_5_14["5.14.4_abs_paths"].append(f"{f.relative_to(ROOT)}:{lineno}")
        except: pass

# 5.14.5 pytest collect + run
d145 = {}
try:
    r = subprocess.run([PY,"-m","pytest","tests/","--collect-only","-q"], capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    d145["collect_exit"] = r.returncode
    last_line = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
    m = re.search(r"(\d+)\s+(item|test)", last_line)
    d145["collected_items"] = int(m.group(1)) if m else None
except Exception as e:
    d145["error"] = str(e)

# 跑 pytest 全量
try:
    r = subprocess.run([PY,"-m","pytest","tests/","-q","--tb=short"], capture_output=True, text=True, cwd=str(ROOT), timeout=180)
    d145["pytest_exit"] = r.returncode
    for line in r.stdout.strip().splitlines()[-10:]:
        if "passed" in line or "failed" in line or "error" in line or "skipped" in line:
            d145["pytest_summary"] = line.strip()
except Exception as e:
    d145["pytest_error"] = str(e)

audit_5_14["5.14.5_pytest"] = d145

results["5.14"] = audit_5_14

# ========== 5.12 安全基线 ==========
audit_5_12 = {}

# flake8 扫 src/
try:
    r = subprocess.run([PY,"-m","flake8","src/","--max-line-length=120","--statistics"], capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    lines = r.stdout.strip().splitlines()
    audit_5_12["flake8_src_summary"] = lines[-5:] if len(lines)>5 else lines
    # 统计 error/warning
    e_count = sum(1 for l in lines if l and l[0].isdigit() and re.match(r"\d+\s+[EWF]\d+", l))
except Exception as e:
    audit_5_12["flake8_error"] = str(e)

# flake8 扫 tests/
try:
    r = subprocess.run([PY,"-m","flake8","tests/","--max-line-length=120","--statistics"], capture_output=True, text=True, cwd=str(ROOT), timeout=60)
    lines = r.stdout.strip().splitlines()
    audit_5_12["flake8_tests_summary"] = lines[-5:] if len(lines)>5 else lines
except Exception as e:
    audit_5_12["flake8_tests_error"] = str(e)

# bandit 扫 src/ (只报告 HIGH)
try:
    r = subprocess.run([PY,"-m","bandit","-r","src/","-lll","--format","json"], capture_output=True, text=True, cwd=str(ROOT), timeout=120)
    data = json.loads(r.stdout) if r.stdout.strip().startswith("{") else {"results": []}
    results_hi = [x for x in data.get("results",[]) if x.get("issue_confidence") == "HIGH"]
    audit_5_12["bandit_src"] = {
        "high_count": len(results_hi),
        "top5": [{
            "file": x["filename"].replace(str(ROOT)+"/",""),
            "line": x["line_number"],
            "test_id": x["test_id"],
            "issue": x["issue_text"][:80],
        } for x in results_hi[:5]],
    }
except Exception as e:
    audit_5_12["bandit_error"] = str(e)

# 明文 Key 检查
audit_5_12["plaintext_key_patterns"] = []
key_patterns = [
    (r'sk-[A-Za-z0-9]{20,}', "OpenAI key"),
    (r'AKIA[0-9A-Z]{16}', "AWS access key"),
    (r'secret[_-]?key\s*=\s*["\'][^"\']{10,}["\']', "secret_key assignment"),
    (r'password\s*=\s*["\'][^"\']+["\']', "password assignment"),
]
for base in [ROOT/"src", ROOT/"config", ROOT/"tools"]:
    if not base.is_dir(): continue
    for f in base.rglob("*.py"):
        if "__pycache__" in str(f): continue
        try:
            for lineno, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(),1):
                for pat, label in key_patterns:
                    if re.search(pat, line, re.I):
                        audit_5_12["plaintext_key_patterns"].append(f"{f.relative_to(ROOT)}:{lineno} [{label}]")
        except: pass

results["5.12"] = audit_5_12

# ========== 输出 ==========
out_file = ROOT/"audit_result.json"
out_file.write_text(json.dumps(results, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(f"Audit JSON -> {out_file}")
print(f"=== PRD 5.15 目录规范体检 ===")
# 快速摘要
dim1_fail = [k for k,v in results["5.15"]["dim1_top_level"].items() if not v]
dim2_fail = [k for k,v in results["5.15"]["dim2_src_structure"].items() if not v]
dim3_fail = [k for k,v in results["5.15"]["dim3_core_13"].items() if not v]
print(f"  dim1 顶层缺失: {dim1_fail or '(全OK)'}")
print(f"  dim2 src缺失:  {dim2_fail or '(全OK)'}")
print(f"  dim3 core13缺失: {dim3_fail or '(全OK)'}")
print(f"  dim7 verify混tests/: {results['5.15']['dim7_tests'].get('verify_files_found','none')}")
print(f"  dim8 tools缺失:  {[k for k,v in results['5.15']['dim8_tools'].items() if not v] or '(全OK)'}")
print(f"  dim10 simhei.ttf: {results['5.15']['dim10_assets']['simhei.ttf']}")
print(f"  dim12 gitignore缺: {[k for k,v in results['5.15']['dim12_gitignore'].items() if not v]}")
print(f"=== PRD 5.14 pytest ===")
print(f"  配置: pytest.ini={results['5.14']['5.14.1_config']['pytest.ini_exists']}")
print(f"  工具: {results['5.14']['5.14.2_tools']}")
p = results['5.14'].get('5.14.5_pytest',{})
print(f"  pytest: collected={p.get('collected_items')} summary={p.get('pytest_summary')}")
print(f"  空断言: {len(results['5.14']['5.14.3_bad_asserts'])} 个")
print(f"  绝对路径硬编码: {len(results['5.14']['5.14.4_abs_paths'])} 处")
print(f"=== PRD 5.12 安全 ===")
print(f"  bandit HIGH: {results['5.12'].get('bandit_src',{}).get('high_count','?')}")
print(f"  明文Key模式: {len(results['5.12']['plaintext_key_patterns'])} 处")
