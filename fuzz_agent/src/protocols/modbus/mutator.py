import random

# 合法功能码池
_VALID_FUNC_CODES = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x0F, 0x10, 0x2B]
# 非法功能码池（必触发设备异常响应，用于保证 EXCEPTION 检出）
_ILLEGAL_FUNC_CODES = [0x5A, 0xA5, 0xFF]
# 混合池（合法 + 非法）
_FUNC_CODE_POOL = _VALID_FUNC_CODES + _ILLEGAL_FUNC_CODES

# 独立随机数生成器，避免全局 random 被其他模块干扰导致验证不可复现
_rng = random.Random()


def seed_mutator(seed):
    """设置 mutator 的随机种子（用于验证场景的确定性）。"""
    _rng.seed(seed)


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 8:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        # illegal_func_code 专用分支：直接写入非法功能码，保证掺码分支必产出 5A/A5/FF
        available_types = ["keep_valid", "func_code", "illegal_func_code", "random_byte"]

        if len(mutated) >= 10:
            available_types.append("start_addr")
        if len(mutated) >= 12:
            available_types.append("quantity")

        mutation_type = _rng.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "func_code":
            mutated[7] = _rng.choice(_FUNC_CODE_POOL)
        elif mutation_type == "illegal_func_code":
            # M1 掺码分支：强制写入非法功能码，触发设备异常响应
            mutated[7] = _rng.choice(_ILLEGAL_FUNC_CODES)
        elif mutation_type == "start_addr":
            mutated[8] = _rng.randint(0, 255)
            mutated[9] = _rng.randint(0, 255)
        elif mutation_type == "quantity":
            mutated[10] = _rng.randint(0, 255)
            mutated[11] = _rng.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = _rng.randint(7, len(mutated) - 1)
            mutated[pos] = _rng.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[Modbus-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
