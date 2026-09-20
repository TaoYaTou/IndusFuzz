from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "Modbus-LLM"


def _build_prompt(base_payload_hex, count, target_func_code=None):
    payload_len = len(base_payload_hex) // 2
    if target_func_code is not None:
        return f"""
        This is a Modbus TCP ADU in hexadecimal format: {base_payload_hex}
        Total length is {payload_len} bytes.
        The target function code for this mutation is 0x{target_func_code:02X}.
        Generate exactly {count} mutations. Each mutation MUST:
        - Keep the same total length ({payload_len} bytes, i.e. {payload_len * 2} hex chars)
        - Be a single line of pure hexadecimal characters (no prefix, no markdown)
        Do not include any explanations.
        """
    return f"""
    This is a Modbus TCP ADU in hexadecimal format: {base_payload_hex}
    Total length is {payload_len} bytes.
    Generate exactly {count} mutations. Each mutation MUST:
    - Keep the same total length ({payload_len} bytes, i.e. {payload_len * 2} hex chars)
    - Be a single line of pure hexadecimal characters (no prefix, no markdown, no numbering)
    Mutation strategies to apply:
    - Function code changes
    - Address boundary violations
    - Quantity exceptions
    Do not include any explanations.
    """


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, target_func_code=None,
                           status_collector=None, func_code_str=None, stop_event=None):
    prompt = _build_prompt(base_payload_hex, count, target_func_code)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str, stop_event=stop_event,
    )


if __name__ == "__main__":
    base_payload_hex = "000100000006010300000001"
    mutations = llm_generate_mutations(base_payload_hex, count=5)
    for mutation in mutations:
        print(mutation)
