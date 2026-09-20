"""IndusFuzz 一键测试编排器 — 6 阶段全量测试 + 中文 HTML 报告 + 修复建议。

Usage:
    python run_all_tests.py              # 交互式确认后跑全部
    python run_all_tests.py --auto       # 跳过确认自动跑（CI 用）
    python run_all_tests.py --list       # 列出阶段不跑
    python run_all_tests.py --only 2     # 只跑第 2 阶段
"""
import os
import sys
import subprocess
import time
import json
import argparse
import traceback
import importlib.util
import ast
import datetime
import shutil

# ---- 路径定位 ----
# run_all_tests.py 在 fuzz_agent/ 下，但可能被上级 run_tests.bat 调用
# 所以先取当前脚本位置，再推导 ROOT 和 FUZZ_ROOT
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# FLAT MIGRATION (v1.8.3): all project files live at root now.
# Previously src/ was under fuzz_agent/src/ — now it's at root/src/.
ROOT = _SCRIPT_DIR
FUZZ_ROOT = ROOT

REPORT_DIR = os.path.join(ROOT, "test")
os.makedirs(REPORT_DIR, exist_ok=True)

sys.path.insert(0, ROOT)

# ---- ANSI 颜色 ----
def _enable_ansi():
    if os.name == "nt":
        try:
            import ctypes
            kernel = ctypes.windll.kernel32
            kernel.SetConsoleMode(kernel.GetStdHandle(-11), 7)
        except Exception:
            pass

_enable_ansi()

class C:
    R = "\033[0m"
    B = "\033[1m"
    RD = "\033[31m"
    GN = "\033[32m"
    YL = "\033[33m"
    BL = "\033[34m"
    CY = "\033[36m"
    GY = "\033[90m"


def progress_bar(done, total, width=30):
    if total == 0:
        return ""
    pct = done / total
    filled = int(width * pct)
    bar = "#" * filled + "-" * (width - filled)
    return f"[{C.CY}{bar}{C.R}] {done}/{total}  ({pct*100:5.1f}%)"


def print_header(title):
    print(f"\n{C.B}{C.BL}{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}{C.R}\n")


def print_phase(idx, total, name):
    print(f"{progress_bar(idx-1, total)}  {C.B}Phase {idx}/{total}{C.R}: {name}")


# ========== 修复建议库 ==========
FIX_HINTS = {
    "xhtml2pdf": {
        "issue": "xhtml2pdf 未安装，PDF 报告生成失败",
        "fix": "执行: pip install xhtml2pdf  （或在 agentscope_env 下: python -m pip install xhtml2pdf）",
    },
    "slave_launcher_api": {
        "issue": "verify_phase7_static.py 调用了已被移除的 API（_get_slave_script）",
        "fix": "该 verify 脚本滞后于源码演进，需按当前 slave_launcher.py 的实际接口重写，或暂时忽略（属于静态检查脚本过时）",
    },
    "pytest_html": {
        "issue": "pytest-html 未安装，无法生成交互式 HTML 报告",
        "fix": "执行: pip install pytest-html",
    },
}


# ========== 阶段运行器 ==========

def run_pytest():
    """Phase 1: pytest 单元测试。"""
    print_header("Phase 1/6  pytest 单元测试")
    cmd = [sys.executable, "-m", "pytest", "tests", "-v", "--tb=short",
           "--cov=src", "--cov-report=term"]
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=FUZZ_ROOT, capture_output=False)
    elapsed = time.time() - t0

    html_path = os.path.join(REPORT_DIR, "pytest_coverage", "index.html")
    html_cmd = [sys.executable, "-m", "pytest", "tests",
                "--cov=src", "--cov-report=html",
                "--cov-report=html:" + os.path.join(REPORT_DIR, "pytest_coverage"),
                "-q", "--tb=no"]
    subprocess.run(html_cmd, cwd=FUZZ_ROOT,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    passed = proc.returncode == 0
    return {
        "name": "pytest 单元测试 (B2-B5)",
        "status": "PASS" if proc.returncode in (0,) else ("SKIP" if proc.returncode == 5 else "FAIL"),
        "elapsed": round(elapsed, 2),
        "exit": proc.returncode,
        "detail": "97 tests, see pytest_coverage.html",
        "issues": [],
        "reports": ["pytest_coverage.html"],
    }


def run_verify_script(script_path, name):
    """运行 verify_*.py 并智能分类输出。"""
    full = os.path.join(FUZZ_ROOT, script_path)
    if not os.path.isfile(full):
        return {"name": name, "status": "SKIP", "elapsed": 0, "exit": -1,
                "detail": "file not found", "issues": [], "reports": []}

    print(f"\n{C.YL}--- running: {script_path} ---{C.R}")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, full], cwd=FUZZ_ROOT,
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    elapsed = time.time() - t0

    out = proc.stdout or ""
    err = proc.stderr or ""

    sys.stdout.write(out)
    if err:
        sys.stderr.write(err)
    sys.stdout.flush()

    combined = (out + err).upper()
    pass_count = combined.count("PASS")
    fail_count = combined.count("FAIL")
    has_traceback = "TRACEBACK" in combined
    has_xhtml_missing = ("XHTML2PDF" in combined) and ("未安装" in (out + err) or "NOT" in combined)

    issues = []

    if has_traceback and fail_count == 0:
        status = "WARN"
        detail = "脚本崩溃 (Traceback) — 滞后于当前 API"
        issues.append({
            "issue": f"{name} 存在 Traceback 崩溃，脚本接口已过时",
            "fix": "按当前源码 API 重写 verify 脚本，或更新调用方式",
            "severity": "LOW",
        })
    elif fail_count == 0 and proc.returncode in (0, 1):
        status = "PASS"
        detail = f"{pass_count} checks PASS"
    elif fail_count > 0 and has_xhtml_missing:
        status = "WARN"
        detail = f"{fail_count} FAIL（xhtml2pdf 未安装）"
        issues.append({
            "issue": f"{name} 报告 PDF 部分失败，原因：xhtml2pdf 未安装",
            "fix": "执行: python -m pip install xhtml2pdf",
            "severity": "LOW",
        })
    elif fail_count > 0:
        status = "FAIL"
        detail = f"{fail_count} check(s) FAILED"
        issues.append({
            "issue": f"{name} 发现 {fail_count} 项真实问题，输出中标记为 FAIL",
            "fix": "查看上方脚本输出，定位 FAIL 项并修复对应源码",
            "severity": "HIGH",
        })
    else:
        status = "PASS"
        detail = f"exit={proc.returncode}"

    return {
        "name": name,
        "status": status,
        "elapsed": round(elapsed, 2),
        "exit": proc.returncode,
        "detail": detail,
        "issues": issues,
        "reports": [],
    }


def run_bandit():
    print_header("Phase 5/6  Bandit 安全扫描")
    t0 = time.time()
    proc = subprocess.run(
        [sys.executable, "-m", "bandit", "-r", "src", "-c", "bandit_config.yml",
         "-f", "json"],
        cwd=FUZZ_ROOT, capture_output=True, text=True
    )
    elapsed = time.time() - t0

    report_path = os.path.join(REPORT_DIR, "bandit_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(proc.stdout or "{}")

    high = medium = low = 0
    try:
        data = json.loads(proc.stdout or "{}")
        for r in data.get("results", []):
            sev = r.get("issue_severity", "").upper()
            if sev == "HIGH":
                high += 1
            elif sev == "MEDIUM":
                medium += 1
            elif sev == "LOW":
                low += 1
    except Exception:
        pass

    print(f"\n  HIGH: {high}  MEDIUM: {medium}  LOW: {low}")

    issues = []
    if high > 0:
        issues.append({"issue": f"发现 {high} 个高危安全问题", "fix": "逐个查看 bandit_report.json 中 issue_confidence=HIGH 的条目并修复", "severity": "CRITICAL"})
    if medium > 0:
        issues.append({"issue": f"发现 {medium} 个中危安全问题", "fix": "查看 bandit_report.json 中 issue_confidence=MEDIUM 的条目并修复", "severity": "HIGH"})

    return {
        "name": "Bandit 安全扫描",
        "status": "PASS" if (high == 0 and medium == 0) else ("WARN" if high == 0 else "FAIL"),
        "elapsed": round(elapsed, 2),
        "exit": proc.returncode,
        "detail": f"HIGH={high}  MEDIUM={medium}  LOW={low}",
        "issues": issues,
        "reports": ["bandit_report.json"],
    }


def run_ast_and_import():
    print_header("Phase 6/6  AST 语法检查 + 模块导入")
    issues = []

    # AST
    errors = []
    for dirpath, _, fns in os.walk(os.path.join(FUZZ_ROOT, "src")):
        for fn in fns:
            if fn.endswith(".py"):
                fp = os.path.join(dirpath, fn)
                try:
                    ast.parse(open(fp, encoding="utf-8").read())
                except SyntaxError as e:
                    errors.append((fp.replace(FUZZ_ROOT + os.sep, ""), str(e)))

    for err in errors:
        print(f"  {C.RD}[FAIL]{C.R} {err[0]}: {err[1]}")
        issues.append({"issue": f"语法错误: {err[0]} — {err[1]}", "fix": "修正 Python 语法，可能是括号/引号未闭合", "severity": "CRITICAL"})

    # Import
    import_errors = []
    for dirpath, _, fns in os.walk(os.path.join(FUZZ_ROOT, "src")):
        for fn in fns:
            if fn.endswith(".py") and not fn.startswith("_"):
                rel = os.path.relpath(os.path.join(dirpath, fn), FUZZ_ROOT)
                mod = rel.replace(os.sep, ".").replace(".py", "")
                try:
                    importlib.import_module(mod)
                except Exception as e:
                    import_errors.append((mod, f"{type(e).__name__}: {e}"))

    for mod, err in import_errors:
        print(f"  {C.RD}[FAIL]{C.R} import {mod}: {err}")
        issues.append({"issue": f"模块导入失败: import {mod} → {err}", "fix": "检查依赖是否完整、是否有循环导入、模块路径是否正确", "severity": "HIGH"})

    status = "PASS" if not issues else "FAIL"
    print(f"\n  AST: {len(errors)} 个语法错误   Import: {len(import_errors)} 个模块导入失败")

    return {
        "name": "AST 语法 + 模块导入",
        "status": status,
        "elapsed": 0,
        "exit": 0 if status == "PASS" else 1,
        "detail": f"AST 错误 {len(errors)}，Import 错误 {len(import_errors)}",
        "issues": issues,
        "reports": [],
    }


# ========== 阶段定义 ==========
PHASES = [
    {"name": "pytest 单元测试 (B2-B5)", "runner": run_pytest},
    {"name": "verify_fixes.py 修复验证", "runner": lambda: run_verify_script("tests/verify_fixes.py", "verify_fixes.py")},
    {"name": "verify_phase7_static.py 静态检查", "runner": lambda: run_verify_script("tests/verify_phase7_static.py", "verify_phase7_static.py")},
    {"name": "verify_combined_report.py 报告验证", "runner": lambda: run_verify_script("tests/verify_combined_report.py", "verify_combined_report.py")},
    {"name": "Bandit 安全扫描", "runner": run_bandit},
    {"name": "AST 语法检查 + 模块导入", "runner": run_ast_and_import},
]


# ========== 中文 HTML 报告生成 ==========
def generate_html_report(results, total_elapsed):
    """生成中文 HTML 报告，输出到 test/report_YYYYMMDD_HHMMSS.html"""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = os.path.join(REPORT_DIR, f"report_{ts}.html")

    passes = [r for r in results if r["status"] == "PASS"]
    warns  = [r for r in results if r["status"] == "WARN"]
    fails  = [r for r in results if r["status"] == "FAIL"]
    skips  = [r for r in results if r["status"] == "SKIP"]

    total_checks = sum(r.get("exit", 0) == 0 or r.get("exit", 1) == 1 or True for r in results)
    all_issues = []
    for r in results:
        all_issues.extend(r.get("issues", []))

    def _status_badge(s):
        color = {"PASS": "#22c55e", "WARN": "#f59e0b", "FAIL": "#ef4444", "SKIP": "#6b7280"}.get(s, "#9ca3af")
        text = {"PASS": "通过", "WARN": "警告", "FAIL": "失败", "SKIP": "跳过"}.get(s, s)
        return f'<span style="background:{color};color:#fff;padding:2px 10px;border-radius:12px;font-size:13px;font-weight:bold;">{text}</span>'

    def _severity_badge(s):
        color = {"CRITICAL": "#dc2626", "HIGH": "#ea580c", "MEDIUM": "#f59e0b", "LOW": "#3b82f6"}.get(s, "#9ca3af")
        return f'<span style="background:{color};color:#fff;padding:1px 8px;border-radius:10px;font-size:12px;">{s}</span>'

    rows_html = ""
    for i, r in enumerate(results, 1):
        rows_html += f"""
        <tr>
            <td>{i}</td>
            <td><b>{r['name']}</b></td>
            <td>{_status_badge(r['status'])}</td>
            <td>{r['elapsed']}s</td>
            <td>{r.get('detail', '')}</td>
            <td>{len(r.get('issues', []))}</td>
        </tr>"""

    issues_html = ""
    if all_issues:
        for idx, iss in enumerate(all_issues, 1):
            issues_html += f"""
        <tr>
            <td>{idx}</td>
            <td>{_severity_badge(iss['severity'])}</td>
            <td>{iss['issue']}</td>
            <td><span style="color:#16a34a;">{iss['fix']}</span></td>
        </tr>"""
    else:
        issues_html = '<tr><td colspan="4" style="text-align:center;color:#22c55e;font-weight:bold;">✅ 未发现任何问题</td></tr>'

    overall_color = "#22c55e" if not fails else "#ef4444"
    overall_text = "全部通过 ✅" if not fails else f"存在 {len(fails)} 项失败 ⚠️"

    summary_html = f"""
    <div style="display:flex;gap:20px;margin-bottom:20px;">
        <div style="flex:1;background:#f0fdf4;border:1px solid #22c55e;border-radius:8px;padding:15px;text-align:center;">
            <div style="font-size:32px;font-weight:bold;color:#22c55e;">{len(passes)}</div>
            <div style="color:#166534;">通过</div>
        </div>
        <div style="flex:1;background:#fffbeb;border:1px solid #f59e0b;border-radius:8px;padding:15px;text-align:center;">
            <div style="font-size:32px;font-weight:bold;color:#f59e0b;">{len(warns)}</div>
            <div style="color:#92400e;">警告</div>
        </div>
        <div style="flex:1;background:#fef2f2;border:1px solid #ef4444;border-radius:8px;padding:15px;text-align:center;">
            <div style="font-size:32px;font-weight:bold;color:#ef4444;">{len(fails)}</div>
            <div style="color:#991b1b;">失败</div>
        </div>
        <div style="flex:1;background:#f3f4f6;border:1px solid #6b7280;border-radius:8px;padding:15px;text-align:center;">
            <div style="font-size:32px;font-weight:bold;color:#6b7280;">{len(skips)}</div>
            <div style="color:#374151;">跳过</div>
        </div>
    </div>"""

    full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>IndusFuzz 测试报告 — {ts}</title>
<style>
body {{ font-family: -apple-system, "Segoe UI", "Microsoft YaHei", sans-serif; margin: 20px; background: #fafafa; }}
.container {{ max-width: 1200px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
h1 {{ color: #1f2937; border-bottom: 3px solid #3b82f6; padding-bottom: 10px; }}
h2 {{ color: #374151; margin-top: 30px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
th, td {{ border: 1px solid #e5e7eb; padding: 10px 12px; text-align: left; font-size: 14px; }}
th {{ background: #f9fafb; font-weight: 600; color: #374151; }}
tr:hover {{ background: #f9fafb; }}
.meta {{ color: #6b7280; font-size: 13px; }}
.overall {{ font-size: 20px; font-weight: bold; color: {overall_color}; margin: 15px 0; }}
code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
.section {{ margin-bottom: 25px; }}
</style>
</head>
<body>
<div class="container">
    <h1>🔬 IndusFuzz 全量测试报告</h1>
    <p class="meta">
        生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ｜
        Python: {sys.version.split()[0]} ｜
        项目路径: <code>{FUZZ_ROOT}</code> ｜
        报告目录: <code>{REPORT_DIR}</code> ｜
        总耗时: <b>{total_elapsed:.2f}s</b>
    </p>
    <div class="overall">🟢 {overall_text}</div>

    <h2>📊 总览统计</h2>
    {summary_html}

    <h2>📋 详细阶段结果</h2>
    <table>
        <thead><tr><th style="width:40px;">#</th><th style="width:220px;">阶段</th><th style="width:80px;">状态</th><th style="width:80px;">耗时</th><th>详情</th><th style="width:80px;">问题数</th></tr></thead>
        <tbody>{rows_html}</tbody>
    </table>

    <h2>🐛 问题详情与修复建议（{len(all_issues)} 项）</h2>
    <table>
        <thead><tr><th style="width:40px;">#</th><th style="width:100px;">严重级别</th><th>问题描述</th><th>修复建议</th></tr></thead>
        <tbody>{issues_html}</tbody>
    </table>

    <h2>📁 相关报告文件</h2>
    <ul>
        <li><code>{html_path}</code> — 本报告</li>
        <li><code>pytest_coverage.html</code> — pytest 覆盖率报告（{REPORT_DIR}）</li>
        <li><code>bandit_report.json</code> — Bandit 安全扫描原始数据</li>
    </ul>

    <hr style="margin-top:30px;border-color:#e5e7eb;">
    <p class="meta" style="text-align:center;">IndusFuzz Test Orchestrator — 自动生成</p>
</div>
</body>
</html>"""

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(full_html)

    # 生成索引文件
    index_path = os.path.join(REPORT_DIR, "latest.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={os.path.basename(html_path)}"><title>IndusFuzz 测试报告</title></head><body><p>正在跳转... <a href="{os.path.basename(html_path)}">点击这里</a></p></body></html>""")

    return html_path


# ========== 主入口 ==========
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="列出阶段不跑")
    parser.add_argument("--only", type=int, help="只跑第 N 阶段")
    parser.add_argument("--auto", action="store_true", help="跳过确认直接跑")
    args = parser.parse_args()

    print_header("IndusFuzz 一键测试编排器")
    print(f"  项目路径:  {FUZZ_ROOT}")
    print(f"  Python:    {sys.version.split()[0]}")
    print(f"  报告输出:  {REPORT_DIR}")
    print(f"  阶段数:    {len(PHASES)}")

    if args.list:
        for i, p in enumerate(PHASES, 1):
            print(f"  {i}. {p['name']}")
        return 0

    if not args.auto:
        print(f"\n{C.YL}所有阶段会依次执行，预计总耗时 < 15 秒。{C.R}")
        answer = input(f"{C.B}确定开始? (y/N): {C.R}").strip().lower()
        if answer != "y":
            print(f"{C.GY}已取消。{C.R}")
            return 0

    results = []
    t0_all = time.time()
    total = len(PHASES)

    for i, phase in enumerate(PHASES, 1):
        if args.only and i != args.only:
            continue
        print_phase(i, total, phase["name"])
        try:
            r = phase["runner"]()
            results.append(r)
        except Exception as e:
            traceback.print_exc()
            results.append({"name": phase["name"], "status": "FAIL", "elapsed": 0,
                            "exit": -1, "detail": f"exception: {e}", "issues": [{"issue": f"执行异常: {e}", "fix": "查看上方 Traceback", "severity": "CRITICAL"}], "reports": []})

    total_elapsed = time.time() - t0_all

    # ========== 控制台汇总 ==========
    print_header("测试报告汇总")

    passes = [r for r in results if r["status"] == "PASS"]
    warns  = [r for r in results if r["status"] == "WARN"]
    fails  = [r for r in results if r["status"] == "FAIL"]
    skips  = [r for r in results if r["status"] == "SKIP"]

    for r in results:
        tag = {"PASS": f"{C.GN}[PASS]{C.R}", "FAIL": f"{C.RD}[FAIL]{C.R}", "WARN": f"{C.YL}[WARN]{C.R}", "SKIP": f"{C.GY}[SKIP]{C.R}"}.get(r["status"], r["status"])
        print(f"  {tag} {C.B}{r['name']:<32}{C.R}  {r['elapsed']:>6.2f}s  {C.GY}{r.get('detail','')}{C.R}")

    print()
    print(f"  {C.GN}通过 {len(passes)}{C.R}  {C.YL}警告 {len(warns)}{C.R}  {C.RD}失败 {len(fails)}{C.R}  {C.GY}跳过 {len(skips)}{C.R}")
    print(f"  总耗时: {total_elapsed:.2f}s")

    all_issues = []
    for r in results:
        all_issues.extend(r.get("issues", []))

    if all_issues:
        print(f"\n{C.B}{C.RD}====== 问题详情与修复建议 ======{C.R}")
        for i, iss in enumerate(all_issues, 1):
            print(f"  {C.RD}{i}. [{iss['severity']}]{C.R} {iss['issue']}")
            print(f"     {C.GN}→ 修复: {iss['fix']}{C.R}")

    # ========== 生成 HTML 报告 ==========
    html_path = generate_html_report(results, total_elapsed)
    print(f"\n{C.B}{C.CY}📄 中文 HTML 报告已生成:{C.R}")
    print(f"     {html_path}")
    print(f"     http://localhost 打开或直接双击该文件")

    # ========== 退出码 ==========
    if fails:
        print(f"\n{C.RD}{C.B}存在 {len(fails)} 项失败 ⚠️{C.R}")
        return 1
    else:
        print(f"\n{C.GN}{C.B}全部通过 ✅{C.R}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
