from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "IEC61850-LLM"


def _build_prompt(base_payload_hex, count):
    expected_len = len(base_payload_hex)
    return f"""This is an IEC 61850 MMS over ISO 8650 APDU in hexadecimal: {base_payload_hex}
Total {expected_len // 2} bytes. Format: TPKT(4: 0x30+len) + COTP(6+) + MMS PDU(ASN.1 BER, byte 8 is PDU type).
Request PDU types: 0x81 initiate, 0xB0 read, 0xB2 write, 0xB5 getNameList, 0xB7 identify, 0xBC status, etc.
Generate exactly {count} mutations. Each MUST:
- Keep same total length ({expected_len // 2} bytes)
- Be single line of pure hex only
Mutation strategies: PDU type changes (0x81-0xC5 request range), COTP header flips, invoke ID changes, ASN.1 body byte mutations, TPKT start byte 0x30 anomalies.
No explanations."""


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, status_collector=None, func_code_str=None, stop_event=None):
    prompt = _build_prompt(base_payload_hex, count)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str, stop_event=stop_event,
    )


if __name__ == "__main__":
    mutations = llm_generate_mutations("0300000000120004", count=5)
    for m in mutations:
        print(m)
