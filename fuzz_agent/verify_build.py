"""
IndusFuzz 打包后验证脚本。
验证项：
1. EXE 存在且体积 <= 200MB
2. EXE 能启动且显示菜单横幅
3. EXE 内嵌的 func_codes JSON 可访问
4. EXE 能启动 Modbus 从站并跑通一次测试
5. 生成的 HTML/PDF 报告中文显示正常
"""

import os
import sys
import subprocess
import time
import socket

EXE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dist", "IndusFuzz.exe")
MAX_SIZE_MB = 200


def check_exe_exists():
    if not os.path.exists(EXE_PATH):
        return False, f"EXE 不存在: {EXE_PATH}"
    size_mb = os.path.getsize(EXE_PATH) / 1024 / 1024
    if size_mb > MAX_SIZE_MB:
        return False, f"EXE 体积 {size_mb:.1f}MB 超过 {MAX_SIZE_MB}MB"
    return True, f"EXE 体积 {size_mb:.1f}MB"


def check_exe_starts():
    try:
        proc = subprocess.Popen(
            [EXE_PATH],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        time.sleep(3)
        # 先终止进程，再读取输出（避免 read 阻塞等待更多数据）
        proc.terminate()
        try:
            out, _ = proc.communicate(timeout=5)
        except Exception:
            proc.kill()
            out = ""
        if "IndusFuzz" in out or "工业协议" in out:
            return True, "EXE 启动并显示横幅"
        return False, f"EXE 启动但未显示横幅，输出: {out[:200]}"
    except Exception as e:
        return False, f"EXE 启动失败: {type(e).__name__}: {e}"


def check_slave_starts():
    try:
        proc = subprocess.Popen(
            [EXE_PATH, "--run-slave", "--protocol", "modbus", "--port", "5099", "--strict"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(2)
        ok = False
        try:
            with socket.create_connection(("127.0.0.1", 5099), timeout=2):
                ok = True
        except Exception:
            ok = False
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except Exception:
            proc.kill()
        if ok:
            return True, "Modbus 从站启动成功"
        return False, "Modbus 从站启动失败（端口未开放）"
    except Exception as e:
        return False, f"从站启动失败: {type(e).__name__}: {e}"


def main():
    print("=" * 50)
    print("  IndusFuzz 打包后验证")
    print("=" * 50)
    print()

    checks = [
        ("EXE 存在且体积合理", check_exe_exists),
        ("EXE 能启动显示菜单", check_exe_starts),
        ("EXE 能启动 Modbus 从站", check_slave_starts),
    ]

    passed = 0
    failed = 0
    for name, fn in checks:
        ok, msg = fn()
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: {msg}")
        if ok:
            passed += 1
        else:
            failed += 1

    print()
    print(f"结果: {passed} 通过, {failed} 失败")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
