import random

# 合法功能码 + 非法功能码混合池，确保 func_code 变异能同时产生 NORMAL 和 EXCEPTION
_FUNC_CODE_POOL = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x0F, 0x10, 0x2B,
                   0x5A, 0xA5, 0xFF]

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
        available_types = ["keep_valid", "func_code", "random_byte"]

        if len(mutated) >= 10:
            available_types.append("start_addr")
        if len(mutated) >= 12:
            available_types.append("quantity")

        mutation_type = _rng.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "func_code":
            mutated[7] = _rng.choice(_FUNC_CODE_POOL)
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