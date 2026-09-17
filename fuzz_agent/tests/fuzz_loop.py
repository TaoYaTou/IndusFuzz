from modbus_tools import build_modbus_request, send_modbus_payload, parse_modbus_response
from mutator import mutate_payload
import time

def classify_response(mutated_payload, response):
    if response is None:
        return "CONN_CLOSED"
    if len(response) == 0:
        return "EMPTY"
    if len(response) >= 2 and response[7] == 0x83:
        return "EXCEPTION"
    return "NORMAL"

def run_fuzz_loop(iterations=50):
    base = build_modbus_request(func_code=3, start_addr=0, quantity=10)
    print(f">>> 基准报文：{base.hex()}")
    print(f">>> 开始 {iterations} 次变异测试\n")
    
    stats = {"NORMAL": 0, "EXCEPTION": 0, "CONN_CLOSED": 0, "EMPTY": 0}
    results = []
    
    for i in range(iterations):
        mutated = mutate_payload(base)
        response = send_modbus_payload(mutated, timeout=2)
        category = classify_response(mutated, response)
        stats[category] = stats.get(category, 0) + 1
        
        print(f"[{i+1:03d}] 发送 {mutated.hex()} → {category} ({len(response) if response else 0} 字节)")
        
        results.append({
            "iteration": i + 1,
            "payload": mutated.hex(),
            "category": category,
            "response_hex": response.hex() if response else None
        })
        time.sleep(0.1)
    
    print(f"\n>>> 完成。统计：")
    for k, v in stats.items():
        print(f"    {k}: {v}")
    
    return results

if __name__ == "__main__":
    run_fuzz_loop(50)