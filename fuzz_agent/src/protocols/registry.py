import os
import importlib

_PROTOCOLS = {}

_PLUGINS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "plugins"
)

_PROTOCOLS_DIR = os.path.dirname(os.path.abspath(__file__))


def register_protocol(name, protocol_class):
    if name in _PROTOCOLS:
        print(f"[注册表] 警告：协议 {name} 重复注册，将覆盖现有实现")
    _PROTOCOLS[name] = protocol_class


def get_protocol(name):
    if name not in _PROTOCOLS:
        print(f"[注册表] 协议 {name} 未注册")
        print(f"[注册表] 已注册协议: {list(_PROTOCOLS.keys())}")
        raise KeyError(f"协议 {name} 未注册")
    return _PROTOCOLS[name]


def list_protocols():
    return list(_PROTOCOLS.keys())


def auto_load_builtin():
    if not os.path.isdir(_PROTOCOLS_DIR):
        return
    for entry in os.listdir(_PROTOCOLS_DIR):
        entry_path = os.path.join(_PROTOCOLS_DIR, entry)
        if not os.path.isdir(entry_path):
            continue
        init_file = os.path.join(entry_path, "__init__.py")
        if not os.path.isfile(init_file):
            continue
        if entry.startswith("_") or entry == "base" or entry == "func_codes":
            continue
        try:
            importlib.import_module(f"src.protocols.{entry}")
        except Exception as e:
            print(f"[注册表] 警告：加载内置协议 {entry} 失败: {type(e).__name__}: {e}")


def auto_load_plugins():
    if not os.path.isdir(_PLUGINS_DIR):
        return

    for entry in os.listdir(_PLUGINS_DIR):
        plugin_path = os.path.join(_PLUGINS_DIR, entry)
        if not os.path.isdir(plugin_path):
            continue
        init_file = os.path.join(plugin_path, "__init__.py")
        if not os.path.isfile(init_file):
            continue
        try:
            importlib.import_module(f"plugins.{entry}")
        except Exception as e:
            print(f"[注册表] 警告：加载插件 {entry} 失败: {type(e).__name__}: {e}")