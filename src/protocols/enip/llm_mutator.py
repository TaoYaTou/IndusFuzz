from src.protocols.llm_mutator_base import generate_mutations

LOG_PREFIX = "ENIP-LLM"


def _build_prompt(base_payload_hex, count):
    expected_len = len(base_payload_hex)
    return f"""This is an EtherNet/IP CIP request in hexadecimal: {base_payload_hex}
Total {expected_len // 2} bytes. Format: ENIP encapsulation(24 bytes: command+length+session+status+sender_context+options) + CIP request(service_code+path_size+path+data).
CIP service codes (request direction): 0x01 Get_Attributes_All, 0x0E Get_Attribute_Single, 0x10 Set_Attribute_Single, 0x05 Reset, 0x4C Read_Tag, 0x4D Write_Tag, 0x54 Forward_Open, 0x52 Unconnected_Send, etc.
ENIP commands: 0x65 RegisterSession, 0x6F SendRRData, 0x66 UnRegisterSession.
Generate exactly {count} mutations. Each MUST:
- Keep same total length ({expected_len // 2} bytes)
- Be single line of pure hex only
Mutation strategies: service_code changes (0x01-0x1C common, 0x4C-0x54 object-specific), ENIP command flips (0x65/0x6F/0x66), session_handle anomalies, encapsulation header byte mutations, CIP path changes.
No explanations."""


def llm_generate_mutations(base_payload_hex, count=5, max_retries=3, status_collector=None, func_code_str=None, stop_event=None):
    prompt = _build_prompt(base_payload_hex, count)
    return generate_mutations(
        base_payload_hex, count, prompt, LOG_PREFIX,
        max_retries=max_retries, status_collector=status_collector, func_code_str=func_code_str, stop_event=stop_event,
    )


if __name__ == "__main__":
    mutations = llm_generate_mutations("0000000000000000", count=5)
    for m in mutations:
        print(m)
