import os
import sys
import json
import ast
import importlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

OK = "[OK]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def _check_dir(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name)
    if os.path.isdir(path):
        print(f"{OK} 协议目录存在: {path}")
        return True
    print(f"{FAIL} 协议目录不存在: {path}")
    return False


def _check_func_codes(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", "func_codes", f"{protocol_name}_func_codes.json")
    if not os.path.exists(path):
        print(f"{FAIL} 功能码文件不存在: {path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"{FAIL} 功能码 JSON 解析失败: {e}")
        return False

    if data.get("protocol") != protocol_name:
        print(f"{FAIL} JSON protocol 字段不匹配: {data.get('protocol')} != {protocol_name}")
        return False
    if not data.get("default_port"):
        print(f"{FAIL} JSON 缺少 default_port 字段")
        return False
    if data.get("default_port", 0) < 1024:
        print(f"{WARN} default_port < 1024，需要管理员权限")
    if not data.get("func_codes"):
        print(f"{FAIL} JSON 缺少 func_codes 字段或为空")
        return False
    print(f"{OK} 功能码文件正常（{len(data['func_codes'])} 个功能码，端口 {data['default_port']}）")
    return True


def _check_init(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "__init__.py")
    if not os.path.exists(path):
        print(f"{FAIL} __init__.py 不存在")
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "register_protocol" not in content:
        print(f"{FAIL} __init__.py 未调用 register_protocol")
        return False
    print(f"{OK} __init__.py 已注册协议")
    return True


def _check_client(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "client.py")
    if not os.path.exists(path):
        print(f"{FAIL} client.py 不存在")
        return False

    try:
        from src.protocols.base import ProtocolBase
    except Exception as e:
        print(f"{FAIL} 无法导入 ProtocolBase: {e}")
        return False

    try:
        mod = importlib.import_module(f"src.protocols.{protocol_name}.client")
    except Exception as e:
        print(f"{FAIL} 导入 client.py 失败: {e}")
        return False

    client_class = None
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and issubclass(obj, ProtocolBase) and obj is not ProtocolBase:
            client_class = obj
            break

    if client_class is None:
        print(f"{FAIL} client.py 未定义 ProtocolBase 子类")
        return False

    required = ["build_request", "send_payload", "parse_response", "get_default_port", "get_func_codes", "run_fuzz"]
    missing = []
    for method in required:
        impl = getattr(client_class, method, None)
        base_impl = getattr(ProtocolBase, method, None)
        if impl is None or impl is base_impl:
            missing.append(method)

    if missing:
        print(f"{FAIL} client 缺少方法: {', '.join(missing)}")
        return False

    print(f"{OK} client.py 完整（类名 {client_class.__name__}）")
    return True


def _check_mutator(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "mutator.py")
    if not os.path.exists(path):
        print(f"{FAIL} mutator.py 不存在")
        return False
    try:
        mod = importlib.import_module(f"src.protocols.{protocol_name}.mutator")
        if not hasattr(mod, "mutate_payload"):
            print(f"{FAIL} mutator.py 缺少 mutate_payload 函数")
            return False
    except Exception as e:
        print(f"{FAIL} 导入 mutator 失败: {e}")
        return False
    print(f"{OK} mutator.py 正常")
    return True


def _check_llm_mutator(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "llm_mutator.py")
    if not os.path.exists(path):
        print(f"{WARN} llm_mutator.py 不存在（LLM 变异不可用）")
        return True
    try:
        mod = importlib.import_module(f"src.protocols.{protocol_name}.llm_mutator")
        if not hasattr(mod, "llm_generate_mutations"):
            print(f"{FAIL} llm_mutator.py 缺少 llm_generate_mutations 函数")
            return False
    except Exception as e:
        print(f"{FAIL} 导入 llm_mutator 失败: {e}")
        return False
    print(f"{OK} llm_mutator.py 正常")
    return True


def _check_server(protocol_name):
    path = os.path.join(PROJECT_ROOT, "server", f"{protocol_name}_server.py")
    if not os.path.exists(path):
        print(f"{WARN} 模拟从站不存在: {path}")
        return True
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "--strict" in content:
        print(f"{OK} 模拟从站支持 --strict")
    else:
        print(f"{WARN} 模拟从站未支持 --strict（建议补上）")
    if "--port" in content:
        print(f"{OK} 模拟从站支持 --port")
    else:
        print(f"{WARN} 模拟从站未支持 --port")
    return True


def _check_menu_scan(protocol_name):
    try:
        from src.core.menu import _scan_protocols
        result = _scan_protocols()
        if protocol_name in result:
            print(f"{OK} menu.py 自动扫描到协议（端口 {result[protocol_name]['default_port']}）")
            return True
        print(f"{FAIL} menu.py 未扫描到协议，请检查 func_codes JSON")
        return False
    except Exception as e:
        print(f"{FAIL} 调用 _scan_protocols 失败: {e}")
        return False


def _check_core_no_duplicates():
    core_dir = os.path.join(PROJECT_ROOT, "src", "core")
    if not os.path.isdir(core_dir):
        print(f"{WARN} src/core 目录不存在，跳过重复函数检查")
        return True
    target_files = ["report_generator.py", "fuzz_loop_llm.py", "menu.py", "slave_launcher.py"]
    problems = []
    for fname in target_files:
        fpath = os.path.join(core_dir, fname)
        if not os.path.exists(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read(), filename=fname)
        except SyntaxError as e:
            print(f"{WARN} {fname} 语法错误，无法做 AST 检查: {e}")
            continue
        seen = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("_") or node.name == "__init__":
                    continue
                key = node.name
                if key in seen:
                    problems.append((fname, key, seen[key], node.lineno))
                else:
                    seen[key] = node.lineno
    if problems:
        print(f"{FAIL} 核心文件存在重复函数定义（Python 以后定义的为准，旧的变成死代码）：")
        for fname, name, first_line, second_line in problems:
            print(f"    {fname}: {name} 在行 {first_line} 和 {second_line} 各定义了一次")
        return False
    print(f"{OK} 核心文件无重复函数定义")
    return True


def _check_report_config(protocol_name):
    try:
        from src.core.report_generator import PROTOCOL_CONFIG
        if protocol_name in PROTOCOL_CONFIG:
            print(f"{OK} report_generator 已配置协议")
            return True
        print(f"{WARN} report_generator 未配置协议（报告将使用默认值）")
        return True
    except Exception as e:
        print(f"{FAIL} 检查 PROTOCOL_CONFIG 失败: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python tools/check_protocol.py <protocol_name>")
        sys.exit(1)

    protocol_name = sys.argv[1].strip()
    if not protocol_name:
        print("协议名不能为空")
        sys.exit(1)

    print("=" * 60)
    print(f"  协议自检: {protocol_name}")
    print("=" * 60)
    print()

    results = [
        ("协议目录", _check_dir(protocol_name)),
        ("功能码文件", _check_func_codes(protocol_name)),
        ("协议注册", _check_init(protocol_name)),
        ("client 实现", _check_client(protocol_name)),
        ("mutator", _check_mutator(protocol_name)),
        ("llm_mutator", _check_llm_mutator(protocol_name)),
        ("模拟从站", _check_server(protocol_name)),
        ("menu 扫描", _check_menu_scan(protocol_name)),
        ("报告配置", _check_report_config(protocol_name)),
        ("核心文件无重复函数", _check_core_no_duplicates()),
    ]

    print()
    print("=" * 60)
    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"  自检失败：{len(failed)} 项异常")
        for name in failed:
            print(f"    - {name}")
        print()
        print("  协议接入不完整，请修复失败项后再运行")
        sys.exit(1)
    print("  自检通过：所有项目正常")
    print("=" * 60)


if __name__ == "__main__":
    main()
