import random

_SERVICE_POOL = sorted([
    446, 447, 461, 462, 463, 464,
    486, 487, 488, 489,
    525, 526, 527, 528, 529,
    629, 630, 673, 674,
    712,
    749, 750, 751, 752,
    787, 788, 789, 791,
])


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 16:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        available_types = ["keep_valid", "service_node_id", "random_byte"]

        if len(mutated) >= 12:
            available_types.append("msg_chunk_type")
        if len(mutated) >= 10:
            available_types.append("request_id")

        mutation_type = random.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "service_node_id":
            sid = random.choice(_SERVICE_POOL)
            idx = len(mutated) - 4
            if idx >= 0:
                mutated[idx] = sid & 0xFF
                mutated[idx + 1] = (sid >> 8) & 0xFF
                mutated[idx + 2] = (sid >> 16) & 0xFF
                mutated[idx + 3] = (sid >> 24) & 0xFF
        elif mutation_type == "msg_chunk_type":
            mutated[7] = random.choice([0x46, 0x01, 0x02, 0x00])
        elif mutation_type == "request_id":
            pos = random.randint(9, 12)
            mutated[pos] = random.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = random.randint(4, len(mutated) - 1)
            mutated[pos] = random.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[OPCUA-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
