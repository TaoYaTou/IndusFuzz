from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "S7comm-LLM"


def _build_prompt(base_payload_hex, count):
    expected_len = len(base_payload_hex)
    return f"""This is an S7comm protocol message in hexadecimal format: {base_payload_hex}
Total length is {expected_len // 2} bytes.
Generate exactly {count} meaningful mutations of this message. Each mutation MUST:
- Keep the same total length ({expected_len // 2} bytes, i.e. {expected_len} hex chars)
- Be a single line of pure hexadecimal characters (no prefix, no markdown, no numbering)
Mutation strategies: function code changes, DB number changes, address boundary violations, length anomalies, random byte flips.
Do not include any explanations."""


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, status_collector=None, func_code_str=None, stop_event=None):
    prompt = _build_prompt(base_payload_hex, count)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str, stop_event=stop_event,
    )


if __name__ == "__main__":
    base_payload_hex = "0300000000120004"
    mutations = llm_generate_mutations(base_payload_hex, count=5)
    for mutation in mutations:
        print(mutation)
