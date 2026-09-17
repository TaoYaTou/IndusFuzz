import random

_TYPE_ID_POOL = [
    0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x3A, 0x3B, 0x3C,
    0x3D, 0x3E, 0x3F, 0x40, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69,
    0x6A, 0x6B, 0x6E, 0x6F, 0x70, 0x71, 0x78, 0x79, 0x7A, 0x7B,
    0x7C, 0x7D, 0x7E,
]


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 8:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        available_types = ["keep_valid", "type_id", "random_byte"]

        # IEC104: start(0) length(1) ctrl(2-5) type_id(6) vsq(7) cot(8-9)
        if len(mutated) >= 8:
            available_types.append("vsq")
        if len(mutated) >= 10:
            available_types.append("cot")

        mutation_type = random.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "type_id":
            mutated[6] = random.choice(_TYPE_ID_POOL)
        elif mutation_type == "vsq":
            mutated[7] = random.randint(0, 255)
        elif mutation_type == "cot":
            mutated[8] = random.randint(0, 255)
            mutated[9] = random.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = random.randint(2, len(mutated) - 1)
            mutated[pos] = random.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[IEC104-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
