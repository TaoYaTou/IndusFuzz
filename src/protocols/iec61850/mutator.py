import random

_PDU_TYPE_POOL = [
    0x81, 0x83, 0x86, 0xA8, 0xAB, 0xAC, 0xAF,
    0xB0, 0xB2, 0xB5, 0xB7, 0xB9, 0xBC,
    0xBF, 0xC1, 0xC2, 0xC5,
]


def mutate_payload(base_payload):
    if base_payload is None:
        return base_payload
    if len(base_payload) < 12:
        return base_payload

    try:
        mutated = bytearray(base_payload)
        available_types = ["keep_valid", "pdu_type", "random_byte"]

        # IEC61850: TPKT(0-3) COTP_type(4) ... pdu_type(10) invoke_id(13)
        if len(mutated) >= 5:
            available_types.append("cotp_type")
        if len(mutated) >= 11:
            available_types.append("invoke_id")

        mutation_type = random.choice(available_types)

        if mutation_type == "keep_valid":
            pass
        elif mutation_type == "pdu_type":
            mutated[10] = random.choice(_PDU_TYPE_POOL)
        elif mutation_type == "cotp_type":
            mutated[4] = random.choice([0xF0, 0xE0])
        elif mutation_type == "invoke_id":
            mutated[13] = random.randint(0, 255)
        elif mutation_type == "random_byte":
            pos = random.randint(4, len(mutated) - 1)
            mutated[pos] = random.randint(0, 255)

        return bytes(mutated)
    except Exception as e:
        print(f"[IEC61850-mutator] 变异失败: {type(e).__name__}: {e}")
        return base_payload
