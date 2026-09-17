"""
运行时全局配置。

用于在 fuzz_loop_llm 和各协议 llm_mutator 之间传递
无法通过参数逐层传递的配置（如 GPU 加速开关）。
"""

_gpu_enabled = False
_gpu_summary = ""


def set_gpu_config(enabled, summary=""):
    global _gpu_enabled, _gpu_summary
    _gpu_enabled = enabled
    _gpu_summary = summary


def is_gpu_enabled():
    return _gpu_enabled


def get_gpu_summary():
    return _gpu_summary
