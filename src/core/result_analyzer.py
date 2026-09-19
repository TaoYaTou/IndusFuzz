# 各协议异常码在响应帧中的 hex 字符偏移（response 为 hex 字符串，1 字节 = 2 字符）
# (hex_start, hex_end)，None 表示该协议无固定异常码字段
_EXCEPTION_CODE_OFFSET = {
    "modbus": (16, 18),     # 字节[8] = hex[16:18]（MBAP 7字节 + fc|0x80 + exception_code）
    "s7comm": None,          # 无标准异常码字段
    "dnp3": None,            # 内部错误码，无固定偏移
    "iec104": (12, 14),      # 字节[6] = hex[12:14]（type_id 位置）
    "iec61850": None,        # MMS 结构复杂
    "enip": (16, 24),        # 字节[8:12] = hex[16:24]（status 字段，见 enip/client.py unpack("<I", response[8:12])）
    "opcua": None,           # 服务级状态码
}


def analyze_results(results):
    summary = {
        "总测试数 / Total Tests": len(results),
        "NORMAL数 / Normal Count": 0,
        "EXCEPTION数 / Exception Count": 0
    }

    exception_groups = {}
    suspicious_records = []

    for result in results:
        cls = result.get("classification", "")
        if cls == "NORMAL":
            summary["NORMAL数 / Normal Count"] += 1
        elif cls == "EXCEPTION":
            summary["EXCEPTION数 / Exception Count"] += 1
            protocol = (result.get("protocol") or "").lower()
            resp = result.get("response", "") or ""
            offset = _EXCEPTION_CODE_OFFSET.get(protocol)
            if offset and len(resp) >= offset[1]:
                exception_code = resp[offset[0]:offset[1]]
                exception_groups[exception_code] = exception_groups.get(exception_code, 0) + 1
            else:
                exception_groups["unknown"] = exception_groups.get("unknown", 0) + 1
        else:
            suspicious_records.append(result)

    return {
        "summary": summary,
        "exception_groups": exception_groups,
        "suspicious_records": suspicious_records
    }
