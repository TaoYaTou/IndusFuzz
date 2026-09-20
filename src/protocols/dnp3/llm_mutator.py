from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "DNP3-LLM"


def _build_prompt(base_payload_hex, count):
    expected_len = len(base_payload_hex)
    return f"""This is a DNP3 protocol message in hexadecimal format: {base_payload_hex}
Total length is {expected_len // 2} bytes.
Generate exactly {count} meaningful mutations. Each MUST:
- Keep the same total length ({expected_len // 2} bytes)
- Be a single line of pure hex chars only
Mutation strategies: function code changes (0x01-0x15), destination/source address changes, control byte flips, start bytes, checksum region anomalies.
Do not include any explanations."""


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, status_collector=None, func_code_str=None, stop_event=None):
    prompt = _build_prompt(base_payload_hex, count)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str, stop_event=stop_event,
    )


if __name__ == "__main__":
    mutations = llm_generate_mutations("05640500000101010000", count=5)
    for m in mutations:
        print(m)
