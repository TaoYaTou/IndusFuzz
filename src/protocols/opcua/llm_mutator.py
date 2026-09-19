from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "OPCUA-LLM"


def _build_prompt(base_payload_hex, count):
    expected_len = len(base_payload_hex)
    return f"""This is an OPC UA binary protocol MSG chunk in hexadecimal: {base_payload_hex}
Total {expected_len // 2} bytes. Format: MSG(3) + len(4) + chunk_header(8: F+flags+seq+reqId) + RequestHeader(serviceNodeId=446/629/673/712 etc.).
OPC UA service node IDs: 446 OpenSecureChannel, 461 CreateSession, 629 Read, 673 Write, 712 Call, 749 CreateMonitoredItems, 787 CreateSubscription.
Generate exactly {count} mutations. Each MUST:
- Keep same total length ({expected_len // 2} bytes)
- Be single line of pure hex only
Mutation strategies: serviceNodeId changes, chunk header flips, security flag anomalies, request_id changes, header byte mutations, extension object boundary shifts.
No explanations."""


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, status_collector=None, func_code_str=None):
    prompt = _build_prompt(base_payload_hex, count)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str,
    )


if __name__ == "__main__":
    mutations = llm_generate_mutations("4d5347", count=5)
    for m in mutations:
        print(m)
