from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "IEC104-LLM"


def _build_prompt(base_payload_hex, count):
    expected_len = len(base_payload_hex)
    return f"""This is an IEC 60870-5-104 APDU in hexadecimal: {base_payload_hex}
Total {expected_len // 2} bytes. Format: 0x68 + length + control(4) + ASDU(typeID+VSQ+COT+Origin+CommonAddr+IOA+data).
Generate exactly {count} mutations. Each MUST:
- Keep same total length ({expected_len // 2} bytes)
- Be single line of pure hex only
Mutation strategies: typeID changes (0x2D-0x7E range), VSQ byte flips, COT field manipulation, control sequence numbers, start byte 0x68 anomalies.
No explanations."""


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, status_collector=None, func_code_str=None, stop_event=None):
    prompt = _build_prompt(base_payload_hex, count)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str, stop_event=stop_event,
    )


if __name__ == "__main__":
    mutations = llm_generate_mutations("680e000100006401060001000001", count=5)
    for m in mutations:
        print(m)
