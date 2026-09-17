import random

_SERVICE_POOL = [
    0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A,
    0x0D, 0x0E, 0x10, 0x11, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A,
    0x1B, 0x1C, 0x4C, 0x4D, 0x4E, 0x52, 0x54,
]


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 26:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        available_types = ["keep_valid", "service_code", "random_byte"]

        if len(mutated) >= 6:
            available_types.append("enip_command")
        if len(mutated) >= 10:
            available_types.append("session_handle")

        mutation_type = random.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "service_code":
            mutated[24] = random.choice(_SERVICE_POOL)
        elif mutation_type == "enip_command":
            mutated[0] = random.choice([0x65, 0x6F, 0x66]) & 0xFF
        elif mutation_type == "session_handle":
            pos = random.randint(4, 7)
            mutated[pos] = random.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = random.randint(4, len(mutated) - 1)
            mutated[pos] = random.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[ENIP-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
