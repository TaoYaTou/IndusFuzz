"""
GPU 检测模块。

多级检测策略：
1. nvidia-smi（NVIDIA GPU，最可靠）
2. torch.cuda（如果安装了 PyTorch）
3. AMD/其他：暂不支持，返回 False

被 menu.py 在用户选择"启用 GPU 加速"后调用，
无 GPU 时返回错误信息，有 GPU 时返回设备信息。
"""
import shutil
import subprocess


def _check_nvidia_smi():
    if not shutil.which("nvidia-smi"):
        return False, None, "未找到 nvidia-smi，系统可能没有 NVIDIA GPU 或未安装驱动"
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return False, None, f"nvidia-smi 执行失败: {result.stderr.strip()}"
        lines = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
        if not lines:
            return False, None, "nvidia-smi 未返回 GPU 信息"
        gpus = []
        for line in lines:
            parts = line.split(",")
            name = parts[0].strip() if parts else "Unknown"
            mem_mb = 0
            if len(parts) > 1:
                try:
                    mem_mb = int(parts[1].strip())
                except ValueError:
                    mem_mb = 0
            gpus.append({"name": name, "memory_mb": mem_mb})
        return True, gpus, None
    except subprocess.TimeoutExpired:
        return False, None, "nvidia-smi 执行超时"
    except Exception as e:
        return False, None, f"nvidia-smi 检测异常: {type(e).__name__}: {e}"


def _check_torch_cuda():
    try:
        import torch
    except ImportError:
        return False, None, None
    try:
        if not torch.cuda.is_available():
            return False, None, None
        count = torch.cuda.device_count()
        gpus = []
        for i in range(count):
            name = torch.cuda.get_device_name(i)
            props = torch.cuda.get_device_properties(i)
            gpus.append({"name": name, "memory_mb": int(props.total_memory / 1024 / 1024)})
        return True, gpus, None
    except Exception:
        return False, None, None


def detect_gpu():
    """
    检测系统是否有可用的 GPU。

    Returns:
        (has_gpu: bool, gpus: list[dict]|None, error: str|None)
        gpus 元素: {"name": str, "memory_mb": int}
    """
    has_gpu, gpus, err = _check_nvidia_smi()
    if has_gpu:
        return True, gpus, None

    has_gpu, gpus, err = _check_torch_cuda()
    if has_gpu:
        return True, gpus, None

    return False, None, err or "未检测到可用的 NVIDIA GPU"


def get_gpu_summary(gpus):
    if not gpus:
        return "无 GPU"
    parts = []
    for g in gpus:
        mem_gb = g["memory_mb"] / 1024
        parts.append(f"{g['name']} ({mem_gb:.0f}GB)")
    return ", ".join(parts)
