import random

_FUNC_CODE_POOL = [
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09,
    0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13,
    0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D,
    0x1E,
]


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 8:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        available_types = ["keep_valid", "func_code", "random_byte"]

        # DNP3 帧布局: start(0-1) length(2) control(3) func_code(4-5) dest(6-7) src(8-9)
        if len(mutated) >= 8:
            available_types.append("dest_addr")
        if len(mutated) >= 10:
            available_types.append("src_addr")

        mutation_type = random.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "func_code":
            mutated[5] = random.choice(_FUNC_CODE_POOL)
        elif mutation_type == "dest_addr":
            mutated[6] = random.randint(0, 255)
            mutated[7] = random.randint(0, 255)
        elif mutation_type == "src_addr":
            mutated[8] = random.randint(0, 255)
            mutated[9] = random.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = random.randint(4, len(mutated) - 3)
            mutated[pos] = random.randint(0, 255)

        # keep_valid 分支保持 CRC 合法，其余变异类型破坏尾部 CRC 以触发异常
        if mutation_type != "keep_valid" and len(mutated) >= 2:
            mutated[-2] = random.randint(0, 255)
            mutated[-1] = random.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[DNP3-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
