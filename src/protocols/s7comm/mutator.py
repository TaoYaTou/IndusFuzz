import random

_FUNC_CODE_POOL = [
    0x00, 0x04, 0x05, 0x07, 0x1A, 0x1B, 0x1C,
    0x1D, 0x1E, 0x1F, 0x28, 0x29, 0xF0
]


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 10:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        available_types = ["func_code", "random_byte"]

        # S7comm 帧布局: header(0-7) + func_code(8) + ... + db_number(14-15) + start_addr(16-17) + length(18-19)
        if len(mutated) >= 16:
            available_types.append("db_number")
        if len(mutated) >= 18:
            available_types.append("start_addr")
        if len(mutated) >= 20:
            available_types.append("length")

        mutation_type = random.choice(available_types)

        if mutation_type == "func_code":
            mutated[8] = random.choice(_FUNC_CODE_POOL)
        elif mutation_type == "db_number":
            mutated[14] = random.randint(0, 255)
            mutated[15] = random.randint(0, 255)
        elif mutation_type == "start_addr":
            mutated[16] = random.randint(0, 255)
            mutated[17] = random.randint(0, 255)
        elif mutation_type == "length":
            mutated[18] = random.randint(0, 255)
            mutated[19] = random.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = random.randint(8, len(mutated) - 1)
            mutated[pos] = random.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[S7comm-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
