IndusFuzz 协议扩展 PRD（架构重构版 v2.0）
一、文档信息
项目	内容
产品名称	IndusFuzz（工业协议模糊测试智能体）
当前版本	v2.0.0
目标版本	v2.0.0（真实设备支持纳入扩展标准）
文档主题	协议扩展架构重构与规范（含真实设备支持）
目标读者	后续开发者、协议维护者
更新日期	2026-09-18（v2.0 真实设备支持纳入扩展标准 + 9 方法接口 + 11 步流程 + 17 项清单）

## 协议扩展 Checklist 执行角色

你是一名资深工业协议实现专家 + Python 工程师，对 Modbus、S7Comm、DNP3、IEC 104/61850、EtherNet/IP、OPC UA 等协议有实际编码经验。执行本 Checklist 时：
- 每阶段完成后跑对应验证命令，不跳步
- 发现问题立刻记录反模式到第十六章
- 阶段 7（全面检查）9 项全过才算完成（7.1~7.9，含 7.9 安全基线回归）

## 协议扩展检查维度（每个协议都要过）

| 维度 | 关注点 | 阶段对应 |
|------|--------|---------|
| 正确性 | build_request 符合协议规范、run_fuzz 签名一致 | 阶段 2/5 |
| 兼容性 | 新增协议后其他 7 个协议仍能正常跑 | 阶段 7.1/7.6 |
| 健壮性 | mutator 不越界、llm_mutator 处理空返回/超时/429 | 阶段 2.5/7.7 |
| 可维护性 | 不引入反模式 A-Z 新变种 | 阶段 7.8 |
| 一致性 | func_codes -> client -> mutator -> server -> report_generator 五处数量一致 | 阶段 5.2 + 十七章 |

二、v1.6.0 五项架构改进
#	改进	目标
1	统一接口替代 if-elif 分支	新增协议只需在 client.py 实现 run_fuzz，fuzz_loop_llm.py 无需改动
2	报告配置集中化	所有协议配置合并到 PROTOCOL_CONFIG 一处维护
3	menu / slave_launcher 自动扫描	删除硬编码字典，新增协议无需修改核心代码
4	模拟从站加 --strict 参数	支持严格模式，便于验证从站端异常处理逻辑
5	新增自检工具	tools/check_protocol.py 一键检查新协议完整性
三、项目完整目录结构
text
fuzz_agent/
├── src/
│   ├── __init__.py
│   ├── protocols/
│   │   ├── __init__.py
│   │   ├── base.py                         # ProtocolBase（含 run_fuzz 抽象方法）
│   │   ├── registry.py                     # register_protocol() + auto_load_builtin()
│   │   ├── llm_mutator_base.py             # LLM 变异基类（timeout/retry/错误分类/长度校验/None 防护统一收敛）
│   │   ├── func_codes/                     # 功能码 JSON（自动扫描，共 7 个）
│   │   │   ├── modbus_func_codes.json
│   │   │   ├── s7comm_func_codes.json
│   │   │   ├── dnp3_func_codes.json
│   │   │   ├── iec104_func_codes.json
│   │   │   ├── iec61850_func_codes.json
│   │   │   ├── enip_func_codes.json
│   │   │   └── opcua_func_codes.json
│   │   ├── modbus/
│   │   │   ├── __init__.py
│   │   │   ├── client.py                   # 含 run_fuzz 实现
│   │   │   ├── modbus_tools.py             # Modbus 报文构造/发送工具
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py              # 薄壳，委托 llm_mutator_base
│   │   ├── s7comm/
│   │   │   ├── __init__.py
│   │   │   ├── client.py                   # 含 run_fuzz 实现
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py
│   │   ├── dnp3/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py
│   │   ├── iec104/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py
│   │   ├── iec61850/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py
│   │   ├── enip/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py
│   │   ├── opcua/
│   │   │   ├── __init__.py
│   │   │   ├── client.py
│   │   │   ├── mutator.py
│   │   │   └── llm_mutator.py
│   │   └── <新协议>/                        # 新增协议按此模板
│   │       ├── __init__.py
│   │       ├── client.py
│   │       ├── mutator.py
│   │       └── llm_mutator.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── version.py                      # 版本号唯一来源
│   │   ├── menu.py                         # 自动扫描 func_codes/，6 步交互向导
│   │   ├── fuzz_loop_llm.py                # 通用 run()，无 if-elif，含超时熔断
│   │   ├── result_analyzer.py              # 结果统计分析
│   │   ├── report_generator.py             # HTML/PDF/LOG 报告，PROTOCOL_CONFIG 集中配置
│   │   ├── slave_launcher.py               # 自动按 server/<name>_server.py 约定路径查找
│   │   ├── diagnose.py                     # 连通性诊断
│   │   ├── security.py                     # DPAPI 加密 API Key + HTTPS 强制 + 打码
│   │   ├── llm_precheck.py                 # LLM 连通性预检 + 端口连通性检查
│   │   ├── llm_status.py                   # 每协议 LLM 调用状态收集
│   │   ├── runtime_config.py               # 全局运行时开关（如 GPU）
│   │   ├── gpu_detector.py                 # GPU 检测（nvidia-smi / torch）
│   │   └── color_output.py                 # ANSI 彩色输出（Windows VT 降级）
│   └── integrations/                       # MCP 工具链（桩文件，开发中）
│       ├── __init__.py
│       ├── vulnclaw_mcp.py
│       ├── codeguard_mcp.py
│       └── codeinspectus_mcp.py
├── config/
│   └── __init__.py            # config 包（运行配置在 src/core/runtime_config.py）
├── server/
│   ├── __init__.py
│   ├── modbus_server.py                    # 支持 --port --strict
│   ├── s7comm_server.py
│   ├── dnp3_server.py
│   ├── iec104_server.py
│   ├── iec61850_server.py
│   ├── enip_server.py
│   ├── opcua_server.py
│   └── <新协议>_server.py
├── tools/
│   ├── check_protocol.py                   # 协议自检工具（11 项检查）
│   └── clean_before_release.py             # 发布前清理临时/报告文件
├── tests/
│   ├── __init__.py
│   ├── fuzz_loop.py                        # fuzz_loop 单元测试
│   ├── test_tools.py
│   ├── test_mutator.py
│   ├── test_reporter.py
│   ├── verify_fuzz_flow.py                 # 完整 fuzz 流程验证
│   ├── verify_combined_report.py           # 合并报告验证
│   ├── verify_error_report.py              # 错误报告验证
│   ├── verify_fixes.py                     # 修复点验证
│   ├── verify_gpu.py
│   ├── verify_phase7_static.py
│   ├── verify_strict_e2e.py
│   ├── verify_strict_wiring.py
│   └── legacy/                             # 遗留测试脚本
├── reports/                                # 生成的报告
├── assets/
│   ├── fonts/simhei.ttf                    # PDF 中文字体
│   └── concept_a_hex/                      # 应用 Logo 图标
├── docs/
│   ├── IndusFuzz 协议扩展 PRD.md            # 本文档
│   ├── IndusFuzz 审计PRD.md
│   └── IndusFuzz 审计修复总结PRD.md
├── main.py
├── requirements.txt
├── start_fuzz.bat
├── modbus_fuzzer.spec
├── .gitignore
└── README.md
四、改进 1：统一接口替代 if-elif 分支
4.1 设计原则
ProtocolBase 新增 run_fuzz 方法，每个协议在 client.py 实现。fuzz_loop_llm.py 通过注册表获取协议类，调用统一的 run_fuzz 接口，不再为每个协议写 _run_xxx 分支。

4.2 src/protocols/base.py
python
class ProtocolBase:
    name = "base"

    def build_request(self, **kwargs) -> bytes:
        raise NotImplementedError

    def send_payload(self, payload, host, port) -> bytes:
        raise NotImplementedError

    def parse_response(self, raw) -> dict:
        raise NotImplementedError

    def get_default_port(self) -> int:
        raise NotImplementedError

    def get_func_codes(self) -> list:
        raise NotImplementedError

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures):
        raise NotImplementedError
4.3 Modbus client.py 的 run_fuzz（节选）
python
class ModbusClient(ProtocolBase):
    name = "modbus"
    default_port = 5020

    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures):
        from src.protocols.modbus.modbus_tools import build_modbus_request, send_modbus_payload
        from src.protocols.modbus.llm_mutator import llm_generate_mutations
        from src.protocols.modbus.mutator import mutate_payload as local_mutate

        total_funcs = len(func_codes)
        for idx, fc_str in enumerate(func_codes, start=1):
            try:
                func_code = int(fc_str, 16) if isinstance(fc_str, str) else int(fc_str)
            except (ValueError, TypeError):
                skipped.append({"round": idx, "func_code": fc_str, "reason": "格式无效"})
                continue

            base_payload = build_modbus_request(func_code=func_code)
            if base_payload is None:
                skipped.append({"round": idx, "func_code": func_code, "reason": "基准报文构造失败"})
                build_failures.append({"func_code": func_code, "stage": "基准报文构造", "reason": "失败"})
                continue

            base_hex = base_payload.hex()
            mutations = []
            try:
                mutations = llm_generate_mutations(base_hex, count=5)
            except Exception as e:
                print(f"[Modbus-LLM] 异常: {e}")

            if not mutations:
                mutations = self._generate_local_fallback(base_payload, base_hex, local_mutate, count=5)

            if not mutations:
                skipped.append({"round": idx, "func_code": func_code, "reason": "无有效变异"})
                continue

            for i, mutation in enumerate(mutations[:5], start=1):
                try:
                    mutation_bytes = bytes.fromhex(mutation)
                except ValueError:
                    build_failures.append({"func_code": func_code, "stage": "变异报文解析", "reason": mutation})
                    continue

                response = send_modbus_payload(mutation_bytes, host=host, port=port, timeout=timeout)
                classification = self._classify(mutation_bytes, response)
                print(f"[0x{func_code:02X}] {idx}/{total_funcs}, #{i}: {mutation} -> {classification}")

                results.append({
                    "round": idx, "func_code": func_code,
                    "mutation": mutation,
                    "response": response.hex() if response else "",
                    "classification": classification,
                })

    def _classify(self, mutated, response):
        if response is None:
            return "CONN_CLOSED"
        if len(response) == 0:
            return "EMPTY"
        if len(response) >= 8 and len(mutated) >= 8:
            if response[7] == (mutated[7] | 0x80):
                return "EXCEPTION"
        return "NORMAL"

    def _generate_local_fallback(self, base_payload, base_hex, mutate_fn, count=5, max_attempts=30):
        seen = set()
        mutations = []
        for _ in range(max_attempts):
            if len(mutations) >= count:
                break
            m = mutate_fn(base_payload)
            if not m:
                continue
            hex_m = m.hex()
            if hex_m == base_hex or hex_m in seen:
                continue
            seen.add(hex_m)
            mutations.append(hex_m)
        return mutations
4.4 S7Comm client.py 的 run_fuzz
结构与 Modbus 相同，差异点：

_classify 只返回 NORMAL / CONN_CLOSED / EMPTY（S7comm 无异常码）

调用 S7CommClient.send_payload 而非 send_modbus_payload

4.5 src/core/fuzz_loop_llm.py 的 run()（重构后）
python
from src.protocols.registry import get_protocol


def run(config):
    protocols = config.get("protocols", [])
    func_codes_map = config.get("func_codes", {})
    timeout = config.get("timeout", 6)
    scenario = config.get("scenario", "lan")

    targets = config.get("targets") or {
        p: config.get("target", "127.0.0.1:5020") for p in protocols
    }

    all_results = []
    all_skipped = []
    all_build_failures = []
    report_paths = []

    for protocol_name in protocols:
        func_codes = func_codes_map.get(protocol_name, [])
        if not func_codes:
            continue

        target = targets.get(protocol_name)
        if not target:
            continue

        host, port = _parse_target(target)

        protocol_results = []
        protocol_skipped = []
        protocol_build_failures = []

        print(f"\n>>> 开始协议: {protocol_name}")
        print(f">>> 目标: {host}:{port}")
        print(f">>> 场景: {scenario}")
        print(f">>> 超时: {timeout} 秒")

        try:
            protocol_class = get_protocol(protocol_name)
            protocol_class().run_fuzz(
                func_codes, host, port, timeout,
                protocol_results, protocol_skipped, protocol_build_failures
            )
        except KeyError as e:
            print(f"[错误] 协议未注册: {e}")
            continue
        except Exception as e:
            print(f"[错误] 协议 {protocol_name} 执行异常: {type(e).__name__}: {e}")
            traceback.print_exc()
            continue

        if protocol_results:
            try:
                report_path, log_path = generate_report(
                    protocol_results, protocol_skipped, protocol_build_failures,
                    protocol_name=protocol_name, target=target, scenario=scenario
                )
                report_paths.append((protocol_name, report_path, log_path))
            except Exception as e:
                print(f"报告生成失败: {e}")

        all_results.extend(protocol_results)
        all_skipped.extend(protocol_skipped)
        all_build_failures.extend(protocol_build_failures)

    print(f"\n=== 全部协议总计 ===")
    print(f"总数：{len(all_results)}, CONN_CLOSED：{sum(1 for r in all_results if r.get('classification') == 'CONN_CLOSED')}")
    print(f"跳过：{len(all_skipped)}, 失败：{len(all_build_failures)}")

    try:
        analyze_results(all_results)
    except Exception as e:
        print(f"分析失败: {e}")

    print("\n=== 报告文件 ===")
    for pname, rpath, lpath in report_paths:
        print(f"[{pname}] 报告: {rpath}")
核心变化：删除所有 _run_modbus / _run_s7comm / _run_dnp3 等分支函数，改为统一的 protocol_class().run_fuzz(...) 调用。

五、改进 2：report_generator.py 配置集中化
5.1 集中配置结构
python
PROTOCOL_CONFIG = {
    "modbus": {
        "display_name": "Modbus TCP",
        "func_name_map": {
            0x01: "Read Coils",
            0x02: "Read Discrete Inputs",
            0x03: "Read Holding Registers",
            0x04: "Read Input Registers",
            0x05: "Write Single Coil",
            0x06: "Write Single Register",
            0x07: "Read Exception Status",
            0x08: "Diagnostics",
            0x0B: "Get Comm Event Counter",
            0x0C: "Get Comm Event Log",
            0x0F: "Write Multiple Coils",
            0x10: "Write Multiple Registers",
            0x11: "Report Slave ID",
            0x14: "Read File Record",
            0x15: "Write File Record",
            0x16: "Mask Write Register",
            0x17: "Read/Write Multiple Registers",
            0x18: "Read FIFO Queue",
            0x2B: "Read Device Identification",
        },
        "write_funcs": {0x05, 0x06, 0x0F, 0x10, 0x15, 0x16, 0x17},
        "critical_funcs": {0x08, 0x10, 0x0F, 0x17, 0x15},
        "slave_note": {
            "zh": "本报告使用本地 Modbus 模拟从站（基于 pymodbus）进行测试。模拟从站会返回真实的 Modbus 协议异常响应（如 Illegal Function、Illegal Data Address、Illegal Data Value、Slave Device Failure），因此报告中会出现 EXCEPTION 分类。但模拟从站无法完全模拟真实 PLC 的状态机、边界条件和故障处理逻辑。要获得更有意义的模糊测试结果，建议连接真实的 Modbus 设备（PLC、RTU、网关）。",
            "en": "This report was generated against a local Modbus simulator (pymodbus-based). The simulator returns real Modbus exception responses, so EXCEPTION classifications appear in this report. However, the simulator cannot fully replicate the state machine, boundary conditions, and fault handling of a real PLC. Testing against a real Modbus device is recommended.",
        },
    },
    "s7comm": {
        "display_name": "S7Comm",
        "func_name_map": {
            0x00: "CPU Services",
            0x04: "Read Variable",
            0x05: "Write Variable",
            0x07: "Block Download",
            0x1A: "Upload",
            0x1B: "End Upload",
            0x1C: "Download Block",
            0x1D: "Download Ended",
            0x1E: "Start Upload",
            0x1F: "Diagnostics",
            0x28: "PLC Stop",
            0x29: "PLC Control",
            0xF0: "Setup Communication",
        },
        "write_funcs": {0x05, 0x07, 0x1C, 0x1D},
        "critical_funcs": {0x28, 0x29, 0x07},
        "slave_note": {
            "zh": "本报告使用本地 S7comm 模拟从站进行测试。该模拟从站仅实现了最简单的请求-响应回环，对所有请求返回固定格式响应，不产生异常响应，因此全 NORMAL 是预期行为。要获得有意义的模糊测试结果，需要连接真实的西门子 PLC。",
            "en": "This report was generated against a local S7comm simulator. The simulator only implements a basic request-response loop, returning a fixed response format for all requests, and does not generate exception responses, so an all-NORMAL result is expected. Meaningful fuzzing results require a real Siemens PLC.",
        },
    },
}
5.2 引用方式
python
def _get_func_name(func_code, protocol_name):
    cfg = PROTOCOL_CONFIG.get(protocol_name, {})
    return cfg.get("func_name_map", {}).get(func_code, "Unknown")


def _get_display_name(protocol_name):
    cfg = PROTOCOL_CONFIG.get(protocol_name, {})
    return cfg.get("display_name", protocol_name)


def _get_write_funcs(protocol_name):
    cfg = PROTOCOL_CONFIG.get(protocol_name, {})
    return cfg.get("write_funcs", set())


def _get_critical_funcs(protocol_name):
    cfg = PROTOCOL_CONFIG.get(protocol_name, {})
    return cfg.get("critical_funcs", set())


def _get_slave_note(protocol_name, lang="zh"):
    cfg = PROTOCOL_CONFIG.get(protocol_name, {})
    return cfg.get("slave_note", {}).get(lang, "")
5.3 classify_severity 重构
python
def classify_severity(func_code, classification, response_hex, protocol_name="modbus"):
    if classification == "NORMAL":
        return None, None, None, ""

    if classification == "EXCEPTION":
        code = response_hex[16:18].lower() if response_hex and len(response_hex) >= 18 else ""
        if code in INFO_LEAK_EXC_CODES:
            return "low", "low", "info_leak", code
        if code:
            return "medium", "medium", "device_fault", code
        return "medium", "medium", "no_exc_code", ""

    if classification == "EMPTY":
        return "medium", "medium", "empty_resp", ""

    if classification == "CONN_CLOSED":
        if func_code in _get_critical_funcs(protocol_name):
            return "high", "high", "critical_disconnect", ""
        if func_code in _get_write_funcs(protocol_name):
            return "high", "high", "write_disconnect", ""
        return "medium", "medium", "read_disconnect", ""

    return "medium", "medium", "unclassified", ""
5.4 集中配置文件编辑守则
#### 为什么需要守则
v1.6.0 实施时曾出现一个典型事故：对 report_generator.py 做了两次 Edit，第一次新增 `_get_func_name`（新版，用 PROTOCOL_CONFIG），第二次只改了调用方引用但漏掉删掉旧版 `_get_func_name`（硬编码 PROTOCOL_FUNC_MAPS），导致文件里**两个同名函数共存**、Python 以后定义的为准、旧的变成死代码。结果 `classify_severity` 走的是新 helper，但 `_get_func_name` 却落到旧实现上——旧的字典 `PROTOCOL_FUNC_MAPS` 已被删除，NameError。

#### 三条核心守则
**守则 1：改配置结构时，先删旧字典再写新字典**
```
反模式：
  步骤 A：在文件中间加 PROTOCOL_CONFIG = {...}
  步骤 B：在文件尾部加 PROTOCOL_DISPLAY_NAME / PROTOCOL_FUNC_MAPS 等旧字典
  步骤 C：去调用方一个一个改引用 → 改一半漏一半 → 新字典变摆设

正确顺序：
  步骤 1：删除所有旧字典定义（PROTOCOL_DISPLAY_NAME / PROTOCOL_FUNC_MAPS / PROTOCOL_WRITE_FUNCS / PROTOCOL_CRITICAL_FUNCS / SLAVE_NOTES）
  步骤 2：写 PROTOCOL_CONFIG = {...} 一处集中配置
  步骤 3：写 _get_xxx() 辅助函数（每个配置字段一个 getter）
  步骤 4：改调用方时，全文搜索旧字典名（rg "PROTOCOL_FUNC_MAPS"），逐个替换，确保零残留
```

**守则 2：改函数时，先删旧函数定义再写新的**
```
反模式：
  步骤 A：在文件顶部加 _get_func_name 新版
  步骤 B：在文件尾部加 _get_func_name 旧版（忘了删）

正确顺序：
  步骤 1：全文搜索函数名，标记所有定义位置和调用位置
  步骤 2：删除所有旧版定义（哪怕有多份）
  步骤 3：写一份新的完整实现
  步骤 4：确认文件中该函数名只出现一次（def 定义处）
  步骤 5：立即跑 ast.parse 或 python -c "import 模块" 验证没有 NameError
```

**守则 3：一次改动只做一件事，改完立即 smoke test**
```
反模式：一次 Edit 里同时加新函数、删旧函数、改调用方、改测试，出错时不知道是哪步引的

正确流程：
  步骤 A：只改数据结构（字典 → 集中配置）
  步骤 B：python -c "from src.core.report_generator import PROTOCOL_CONFIG; print('OK')"
  步骤 C：只改 helper 函数（_get_xxx 用新配置）
  步骤 D：python -c "from src.core.report_generator import _get_func_name; print(_get_func_name(0x01,'modbus'))"
  步骤 E：只改调用方（classify_severity / _render_slave_notice / _build_html）
  步骤 F：python -c "from src.core.report_generator import generate_report; print('OK')"
```

#### 报告配置字段清单（PROTOCOL_CONFIG 里每个协议必须有这些键）
键	类型	必填	默认值	说明
display_name	str	是	protocol_name	报告里显示的协议名
func_name_map	dict	是	{}	功能码→名称映射，func_code 为 int 键
write_funcs	set[int]	是	set()	写类功能码（用于 CONN_CLOSED 分级）
critical_funcs	set[int]	是	set()	关键功能码（停机/重启/下载），CONN_CLOSED 直接 HIGH
slave_note	dict{zh: str, en: str}	是	{}	模拟从站说明文本（scenario=local 时显示）

#### 新增协议时的 PROTOCOL_CONFIG 条目模板
```python
"newproto": {
    "display_name": "NewProto",
    "func_name_map": {
        0x01: "Read Data",
        0x02: "Write Data",
    },
    "write_funcs": {0x02},
    "critical_funcs": {0x0D},
    "slave_note": {
        "zh": "本报告使用本地模拟从站，仅用于连通性测试。",
        "en": "Local simulator, connectivity test only.",
    },
},
```

六、改进 3：menu.py 和 slave_launcher.py 自动扫描
6.1 menu.py 自动扫描
删除 PROTOCOL_META 硬编码字典，改为扫描 src/protocols/func_codes/：

python
def _scan_protocols():
    result = {}
    if not os.path.isdir(FUNC_CODES_DIR):
        return result
    for fname in os.listdir(FUNC_CODES_DIR):
        if not fname.endswith("_func_codes.json"):
            continue
        fpath = os.path.join(FUNC_CODES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            proto = data.get("protocol")
            port = data.get("default_port")
            codes = data.get("func_codes", [])
            if not proto or not port or not codes:
                continue
            result[proto] = {
                "name": proto,
                "default_port": port,
                "func_codes": codes,
            }
        except Exception:
            continue
    return result
应用方式：

_display_name(protocol_key) → 返回 protocol_key 或首字母大写（或无显示名，直接用 key）

_get_default_port(protocol_key) → _scan_protocols()[protocol_key]["default_port"]

_load_registry() 内部直接复用扫描结果

6.2 slave_launcher.py 自动查找
删除 PROTOCOL_SLAVE_SCRIPTS 硬编码字典，改为按约定路径查找：

python
def _get_slave_script(protocol_name):
    path = os.path.join(PROJECT_ROOT, "server", f"{protocol_name}_server.py")
    if os.path.exists(path):
        return path
    return None


def supports_protocol(protocol_name):
    return _get_slave_script(protocol_name) is not None


def list_supported_protocols():
    server_dir = os.path.join(PROJECT_ROOT, "server")
    if not os.path.isdir(server_dir):
        return []
    result = []
    for fname in os.listdir(server_dir):
        if fname.endswith("_server.py"):
            result.append(fname[:-len("_server.py")])
    return result
约定：新增协议时，从站脚本必须命名为 server/<protocol_name>_server.py。

七、改进 4：模拟从站加 --strict 参数
7.1 设计
模式	行为
默认（无参数）	固定响应，不校验报文
--strict	校验报文格式，非法请求返回异常码或关闭连接
7.2 server/s7comm_server.py 示例
python
import os
import sys
import socket
import threading

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10102
BUFFER_SIZE = 4096


def _parse_args():
    port = DEFAULT_PORT
    strict = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            try:
                port = int(args[i + 1])
            except ValueError:
                print(f"[S7comm-从站] 无效端口: {args[i + 1]}")
                sys.exit(1)
            i += 2
        elif args[i] == "--strict":
            strict = True
            i += 1
        else:
            i += 1
    return port, strict


def _build_response(trans_id, func_code):
    body = bytes([func_code & 0xFF, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    header = bytes([0x03, 0x00]) + trans_id.to_bytes(2, "big") + len(body).to_bytes(2, "big") + bytes([0x00, 0x00])
    return header + body


def _build_error_response(trans_id, error_code=0x01):
    body = bytes([0x80 | error_code, 0x00, 0x00, 0x00, 0x00, 0x00])
    header = bytes([0x03, 0x00]) + trans_id.to_bytes(2, "big") + len(body).to_bytes(2, "big") + bytes([0x00, 0x00])
    return header + body


def _validate_request(data):
    if len(data) < 8:
        return False, "报文过短"
    if data[0] != 0x03 or data[1] != 0x00:
        return False, "无效起始字节"
    declared_len = int.from_bytes(data[4:6], "big")
    if declared_len != len(data) - 6:
        return False, "长度字段不匹配"
    return True, None


def _handle_client(conn, addr, strict):
    print(f"[S7comm-从站] 客户端已连接: {addr} (strict={strict})")
    try:
        while True:
            data = conn.recv(BUFFER_SIZE)
            if not data:
                break

            trans_id = int.from_bytes(data[2:4], "big") if len(data) >= 4 else 0
            func_code = data[7] if len(data) >= 8 else 0x04

            print(f"[S7comm-从站] 收到 {len(data)} 字节 (transId={trans_id}, func=0x{func_code:02X})")

            if strict:
                ok, reason = _validate_request(data)
                if not ok:
                    print(f"[S7comm-从站] strict 模式：校验失败 - {reason}")
                    try:
                        conn.sendall(_build_error_response(trans_id, 0x01))
                    except Exception:
                        break
                    continue

            response = _build_response(trans_id, func_code)
            try:
                conn.sendall(response)
            except Exception as e:
                print(f"[S7comm-从站] 发送响应失败: {e}")
                break
    except Exception as e:
        print(f"[S7comm-从站] 处理异常: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


def run_server(host=DEFAULT_HOST, port=DEFAULT_PORT, strict=False):
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except PermissionError:
        print(f"[S7comm-从站] 端口 {port} 需要管理员权限")
        server_sock.close()
        return
    except OSError as e:
        print(f"[S7comm-从站] 端口 {port} 被占用: {e}")
        server_sock.close()
        return

    server_sock.listen(5)
    mode_str = "严格" if strict else "宽松"
    print(f"[S7comm-从站] 服务已启动，监听 {host}:{port}（{mode_str}模式）")

    try:
        while True:
            try:
                conn, addr = server_sock.accept()
                t = threading.Thread(target=_handle_client, args=(conn, addr, strict), daemon=True)
                t.start()
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"[S7comm-从站] accept 失败: {e}")
    except KeyboardInterrupt:
        print("\n[S7comm-从站] 已停止")
    finally:
        server_sock.close()


if __name__ == "__main__":
    port, strict = _parse_args()
    run_server(DEFAULT_HOST, port, strict)
7.3 slave_launcher.start_slave 增加 strict 参数
python
def start_slave(protocol_name, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=10, strict=False):
    ...
    cmd = [sys.executable, slave_script, "--port", str(port)]
    if strict:
        cmd.append("--strict")
    proc = subprocess.Popen(cmd, cwd=PROJECT_ROOT, ...)
7.4 menu.py 本机自测增加模式选择
在 _select_local_targets 里追加：

text
======== 从站模式 ========
  [1] 宽松模式（默认，固定响应，用于连通性测试）
  [2] 严格模式（校验报文，非法请求返回异常）
  [Q] 返回上一步
选完写入 state["strict"] = True/False，传给 slave_launcher.start_slave。

八、改进 5：新增自检工具 tools/check_protocol.py
8.1 完整代码
python
import os
import sys
import json
import importlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


OK = "[OK]"
WARN = "[WARN]"
FAIL = "[FAIL]"


def _check_dir(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name)
    if os.path.isdir(path):
        print(f"{OK} 协议目录存在: {path}")
        return True
    print(f"{FAIL} 协议目录不存在: {path}")
    return False


def _check_func_codes(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", "func_codes", f"{protocol_name}_func_codes.json")
    if not os.path.exists(path):
        print(f"{FAIL} 功能码文件不存在: {path}")
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        print(f"{FAIL} 功能码 JSON 解析失败: {e}")
        return False

    if data.get("protocol") != protocol_name:
        print(f"{FAIL} JSON protocol 字段不匹配: {data.get('protocol')} != {protocol_name}")
        return False
    if not data.get("default_port"):
        print(f"{FAIL} JSON 缺少 default_port 字段")
        return False
    if data.get("default_port", 0) < 1024:
        print(f"{WARN} default_port < 1024，需要管理员权限")
    if not data.get("func_codes"):
        print(f"{FAIL} JSON 缺少 func_codes 字段或为空")
        return False
    print(f"{OK} 功能码文件正常（{len(data['func_codes'])} 个功能码，端口 {data['default_port']}）")
    return True


def _check_init(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "__init__.py")
    if not os.path.exists(path):
        print(f"{FAIL} __init__.py 不存在")
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "register_protocol" not in content:
        print(f"{FAIL} __init__.py 未调用 register_protocol")
        return False
    if protocol_name not in content:
        print(f"{WARN} __init__.py 中未出现协议名 {protocol_name}")
    print(f"{OK} __init__.py 已注册协议")
    return True


def _check_client(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "client.py")
    if not os.path.exists(path):
        print(f"{FAIL} client.py 不存在")
        return False

    try:
        from src.protocols.base import ProtocolBase
    except Exception as e:
        print(f"{FAIL} 无法导入 ProtocolBase: {e}")
        return False

    try:
        mod = importlib.import_module(f"src.protocols.{protocol_name}.client")
    except Exception as e:
        print(f"{FAIL} 导入 client.py 失败: {e}")
        return False

    client_class = None
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and issubclass(obj, ProtocolBase) and obj is not ProtocolBase:
            client_class = obj
            break

    if client_class is None:
        print(f"{FAIL} client.py 未定义 ProtocolBase 子类")
        return False

    required = ["build_request", "send_payload", "parse_response", "get_default_port", "get_func_codes", "run_fuzz"]
    missing = []
    for method in required:
        impl = getattr(client_class, method, None)
        base_impl = getattr(ProtocolBase, method, None)
        if impl is None or impl is base_impl:
            missing.append(method)

    if missing:
        print(f"{FAIL} client 缺少方法: {', '.join(missing)}")
        return False

    print(f"{OK} client.py 完整（类名 {client_class.__name__}）")
    return True


def _check_mutator(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "mutator.py")
    if not os.path.exists(path):
        print(f"{FAIL} mutator.py 不存在")
        return False
    try:
        mod = importlib.import_module(f"src.protocols.{protocol_name}.mutator")
        if not hasattr(mod, "mutate_payload"):
            print(f"{FAIL} mutator.py 缺少 mutate_payload 函数")
            return False
    except Exception as e:
        print(f"{FAIL} 导入 mutator 失败: {e}")
        return False
    print(f"{OK} mutator.py 正常")
    return True


def _check_llm_mutator(protocol_name):
    path = os.path.join(PROJECT_ROOT, "src", "protocols", protocol_name, "llm_mutator.py")
    if not os.path.exists(path):
        print(f"{WARN} llm_mutator.py 不存在（LLM 变异不可用）")
        return True
    try:
        mod = importlib.import_module(f"src.protocols.{protocol_name}.llm_mutator")
        if not hasattr(mod, "llm_generate_mutations"):
            print(f"{FAIL} llm_mutator.py 缺少 llm_generate_mutations 函数")
            return False
    except Exception as e:
        print(f"{FAIL} 导入 llm_mutator 失败: {e}")
        return False
    print(f"{OK} llm_mutator.py 正常")
    return True


def _check_server(protocol_name):
    path = os.path.join(PROJECT_ROOT, "server", f"{protocol_name}_server.py")
    if not os.path.exists(path):
        print(f"{WARN} 模拟从站不存在: {path}")
        return True
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "--strict" in content:
        print(f"{OK} 模拟从站支持 --strict")
    else:
        print(f"{WARN} 模拟从站未支持 --strict（建议补上）")
    if "--port" in content:
        print(f"{OK} 模拟从站支持 --port")
    else:
        print(f"{WARN} 模拟从站未支持 --port")
    return True


def _check_menu_scan(protocol_name):
    try:
        from src.core.menu import _scan_protocols
        result = _scan_protocols()
        if protocol_name in result:
            print(f"{OK} menu.py 自动扫描到协议（端口 {result[protocol_name]['default_port']}）")
            return True
        print(f"{FAIL} menu.py 未扫描到协议，请检查 func_codes JSON")
        return False
    except Exception as e:
        print(f"{FAIL} 调用 _scan_protocols 失败: {e}")
        return False


def _check_report_config(protocol_name):
    try:
        from src.core.report_generator import PROTOCOL_CONFIG
        if protocol_name in PROTOCOL_CONFIG:
            print(f"{OK} report_generator 已配置协议")
            return True
        print(f"{WARN} report_generator 未配置协议（报告将使用默认值）")
        return True
    except Exception as e:
        print(f"{FAIL} 检查 PROTOCOL_CONFIG 失败: {e}")
        return False


def main():
    if len(sys.argv) < 2:
        print("用法: python tools/check_protocol.py <protocol_name>")
        sys.exit(1)

    protocol_name = sys.argv[1].strip()
    if not protocol_name:
        print("协议名不能为空")
        sys.exit(1)

    print("=" * 60)
    print(f"  协议自检: {protocol_name}")
    print("=" * 60)
    print()

    results = [
        ("协议目录", _check_dir(protocol_name)),
        ("功能码文件", _check_func_codes(protocol_name)),
        ("协议注册", _check_init(protocol_name)),
        ("client 实现", _check_client(protocol_name)),
        ("mutator", _check_mutator(protocol_name)),
        ("llm_mutator", _check_llm_mutator(protocol_name)),
        ("模拟从站", _check_server(protocol_name)),
        ("menu 扫描", _check_menu_scan(protocol_name)),
        ("报告配置", _check_report_config(protocol_name)),
    ]

    print()
    print("=" * 60)
    failed = [name for name, ok in results if not ok]
    if failed:
        print(f"  自检失败：{len(failed)} 项异常")
        for name in failed:
            print(f"    - {name}")
        sys.exit(1)
    print("  自检通过：所有项目正常")
    print("=" * 60)


if __name__ == "__main__":
    main()
8.2 使用方式
powershell
cd D:\Application\AllToolsSet\AgnetPrograms\IndusFuzz\fuzz_agent
python tools/check_protocol.py modbus
python tools/check_protocol.py s7comm
python tools/check_protocol.py dnp3
输出示例：

text
============================================================
  协议自检: dnp3
============================================================

[OK] 协议目录存在: ...\src\protocols\dnp3
[OK] 功能码文件正常（30 个功能码，端口 20000）
[OK] __init__.py 已注册协议
[OK] client.py 完整（类名 DNP3Client）
[OK] mutator.py 正常
[OK] llm_mutator.py 正常
[OK] 模拟从站支持 --strict
[OK] 模拟从站支持 --port
[OK] menu.py 自动扫描到协议（端口 20000）
[OK] report_generator 已配置协议
[OK] 核心文件无重复函数定义

============================================================
  自检通过：所有项目正常
============================================================
九、新增协议完整流程（v2.0 版，含真实设备支持）

> v2.0 起，新增协议必须一步到位支持真实设备。不再有"只写模拟从站"的过渡阶段。
> 当前 7 个协议（modbus/s7comm/dnp3/iec104/iec61850/enip/opcua）已全部支持真实设备。

### v1.0 → v2.0 关键差异

| 项 | v1.0（旧） | v2.0（新） |
|----|-----------|-----------|
| 协议抽象接口 | 6 个方法 | 9 个方法（+connect/disconnect/is_connected） |
| send_payload | 无状态 socket | 双模式（持久连接 + 无状态回退） |
| menu.py | 只需注册协议名 | 需同步加连接参数配置表 |
| README | 只需说明协议 | 需同步加真实设备测试指南 |
| 检查清单 | 11 项 | 17 项 |

### 9 个抽象方法（base.py:ProtocolBase）

```python
class ProtocolBase:
    # ===== 基础方法（6 个） =====
    def build_request(self, **kwargs) -> bytes: ...
    def send_payload(self, payload, host, port) -> bytes: ...
    def parse_response(self, raw) -> dict: ...
    def get_default_port(self) -> int: ...
    def get_func_codes(self) -> list: ...
    def run_fuzz(self, func_codes, host, port, timeout, results, skipped, build_failures, llm_status=None, stop_event=None) -> None: ...

    # ===== 真实设备支持（v2.0 新增 3 个） =====
    def connect(self, host, port, **kwargs) -> bool:
        """建立持久 TCP 连接 + 协议握手"""
    def disconnect(self) -> None:
        """关闭持久连接，清理状态"""
    def is_connected(self) -> bool:
        """返回当前连接状态"""
```

### 各协议握手内容（connect 必须实现）

| 协议 | 握手内容 |
|------|----------|
| Modbus TCP | TCP 连接 + 连通性验证 |
| S7Comm | TCP + COTP CR→CC + S7 Setup |
| DNP3 | TCP + 链路重置 |
| IEC 104 | TCP + STARTDT act→con |
| IEC 61850 | TCP + MMS Initiate |
| EtherNet/IP | TCP + RegisterSession |
| OPC UA | TCP + HEL→ACK |

### 双模式 send_payload（必须实现）

```python
def send_payload(self, payload, host=None, port=None):
    if self._persistent and self._sock:
        # 真实设备：复用持久连接
        try:
            self._sock.sendall(payload)
            return self._recv_frame()  # 按协议帧长循环接收
        except Exception:
            self._conn_failures += 1
            if self._conn_failures > 3:
                return None
            self._reconnect()
    else:
        # 模拟从站：无状态 socket
        ...
```

### 11 步流程

**步骤 1：创建协议目录**
```
src/protocols/<name>/
├── __init__.py
├── client.py
├── mutator.py
└── llm_mutator.py
```

**步骤 2：编写功能码定义 JSON**
`src/protocols/func_codes/<name>_func_codes.json`
格式：`protocol` / `default_port` / `func_codes` 三个必填字段。

**步骤 3：实现 client.py（含 9 个方法）**
必须实现 9 个方法（见上方）。重点：
- connect 必须实现协议握手（参照上方握手表）
- send_payload 必须双模式（persistent + 无状态回退）
- _recv_frame 必须按协议帧长循环接收（不能一次性 recv(4096) 然后截断）
- 失败熔断：连续 >3 次连接失败则放弃，不再重连
- kwargs 必须贯穿（unit_id/timeout/endpoint/rack/slot 等协议特异参数）

**步骤 4：实现 mutator.py**
参照 modbus/mutator.py，改两处：功能码池 + 关键字节偏移量。
功能码池必须含非法码（0x5A/0xA5/0xFF），否则从站永远返回 NORMAL（反模式 S）。

**步骤 5：实现 llm_mutator.py**
复制任一现有协议的 llm_mutator.py（薄壳），改三处：
日志前缀 [<协议名>-LLM] / prompt 协议名 / prompt 变异策略。
注意：OpenAI client 构造、超时、重试、错误分类全部在基类 llm_mutator_base.py，薄壳不要自己写。

**步骤 6：注册协议**
`src/protocols/<name>/__init__.py`：
```python
from src.protocols.registry import register_protocol
from src.protocols.<name>.client import XxxClient
register_protocol("<name>", XxxClient)
```

**步骤 7：menu.py 注册连接参数（v2.0 新增）**
在 menu.py 的 PROTOCOL_CONNECT_PARAMS 里加上新协议的参数：
```python
PROTOCOL_CONNECT_PARAMS = {
    "<name>": {
        "display_name": "协议显示名",
        "params": [
            {"key": "host", "label": "设备 IP", "required": True},
            {"key": "port", "label": "端口", "default": 默认端口},
            {"key": "xxx", "label": "协议特异参数名", "default": 默认值},
        ]
    },
}
```
同时在 menu.py 的 PROTOCOL_CONNECT_PARAMS 里加新协议的连接参数（参照已有协议）。

**步骤 8：slave_launcher.py 注册从站**
在 PROTOCOL_SLAVE_SCRIPTS 里加一行：`"<name>": "server/<name>_server.py"`。
（若 slave_launcher 已自动扫描，跳过此步，但需验证自动发现正确。）

**步骤 9：fuzz_loop_llm.py 通用分支**
真实设备分支已有通用逻辑，无需额外修改。只需确认新协议通过 registry 被统一调用。

**步骤 10：report_generator.py 加配置**
在 PROTOCOL_CONFIG 里加一条，含 display_name / func_name_map / write_funcs / critical_funcs / slave_note。

**步骤 11：README 加真实设备测试指南（v2.0 新增）**
在 README.md 和 README.zh.md 的"真实设备测试指南"章节，补充新协议的：
- 连接参数表（必填项 + 默认值）
- 设备兼容性（支持哪些设备型号）
- 失败排查（该协议特有的错误码）

十、新增协议检查清单（v2.0 版，17 项）

| # | 项目 | 文件 | 必填 | 说明 |
|---|------|------|------|------|
| 1 | 协议目录 | src/protocols/<name>/ | ✅ | 4 个文件 |
| 2 | 功能码 JSON | src/protocols/func_codes/<name>_func_codes.json | ✅ | protocol/default_port/func_codes |
| 3 | __init__.py 注册 | src/protocols/<name>/__init__.py | ✅ | register_protocol |
| 4 | build_request | client.py | ✅ | 报文构造 |
| 5 | send_payload（双模式） | client.py | ✅ | persistent + 无状态回退 |
| 6 | parse_response | client.py | ✅ | 响应解析 |
| 7 | get_default_port | client.py | ✅ | 默认端口 |
| 8 | get_func_codes | client.py | ✅ | 功能码列表 |
| 9 | run_fuzz | client.py | ✅ | 模糊测试主循环 |
| 10 | connect + disconnect + is_connected | client.py | ✅ | v2.0 新增，真实设备连接生命周期 |
| 11 | mutator.py | src/protocols/<name>/mutator.py | ✅ | 含非法码池 |
| 12 | llm_mutator.py | src/protocols/<name>/llm_mutator.py | ✅ | 薄壳，基类处理 LLM |
| 13 | menu.py 连接参数注册 | src/core/menu.py | ✅ | v2.0 新增，PROTOCOL_CONNECT_PARAMS |
| 14 | slave_launcher.py 注册 | src/core/slave_launcher.py | ✅ | PROTOCOL_SLAVE_SCRIPTS（或自动扫描验证） |
| 15 | fuzz_loop 测试分支 | src/core/fuzz_loop_llm.py | ✅ | 通用分支，registry 统一调用 |
| 16 | report_generator 配置 | src/core/report_generator.py | ✅ | PROTOCOL_CONFIG 条目 |
| 17 | README 真实设备指南 | README.md + README.zh.md | ✅ | v2.0 新增，连接参数表 + 兼容性 + 故障排查 |

v1.0 → v2.0 简化与强化：

| 项目 | v1.0 | v2.0 |
|------|------|------|
| menu.py 需手改 PROTOCOL_META | ✅ 需要 | ❌ 自动扫描（但需手加 PROTOCOL_CONNECT_PARAMS） |
| slave_launcher.py 需手改 | ✅ 需要 | ❌ 自动查找（需验证） |
| fuzz_loop_llm.py 需新增 _run_xxx | ✅ 需要 | ❌ 只调用 run_fuzz |
| report_generator.py 4 处分散配置 | ✅ 需要 | ❌ 集中 PROTOCOL_CONFIG |
| 自检工具 | ❌ 无 | ✅ tools/check_protocol.py |
| 真实设备支持 | ❌ 无 | ✅ 9 方法接口 + 17 项清单 |
十一、模板复用速查表（v2.0）

| 新协议文件 | 复制自 | 需要修改 |
|-----------|--------|----------|
| client.py | s7comm/client.py | 类名、协议名、端口、报文构造、run_fuzz、connect 握手、disconnect、_recv_frame 帧长 |
| mutator.py | modbus/mutator.py | 功能码池（含非法码）、字节偏移量 |
| llm_mutator.py | 任一薄壳 | 日志前缀、prompt 协议名 |
| __init__.py | s7comm/__init__.py | 类名、协议名 |
| server/<name>_server.py | server/s7comm_server.py | 响应格式、默认端口、argparse 三参数 |
| PROTOCOL_CONFIG 条目 | PROTOCOL_CONFIG["s7comm"] | 功能码映射、write/critical 集合、slave_note |
| PROTOCOL_CONNECT_PARAMS 条目 | menu.py 中 s7comm | display_name、params 列表 |

十二、验证流程（v2.0）

```bash
# 1. 协议自检
python tools/check_protocol.py <name>

# 2. 模拟从站流程
python tests/verify_fuzz_flow.py --protocol <name>

# 3. 启动从站测试
python server/<name>_server.py --strict

# 4. 真实设备连接测试（可选但强烈建议）
# 用局域网内一台不关键的设备测试 connect 是否成功
python -c "from src.protocols.<name>.client import XxxClient; c=XxxClient(); print(c.connect('设备IP', 端口))"

# 5. 菜单显示测试
python main.py
# 选 lan 场景，看新协议是否出现在列表中，连接参数表单是否正确渲染
```
十三、目录规范约定
类别	约定
协议目录名	全小写，与 JSON 的 protocol 字段一致
功能码 JSON	<协议名>_func_codes.json，必须含 protocol / default_port / func_codes
默认端口	必须 ≥ 1024
类名	<协议名>Client
日志前缀	[<协议名>] / [<协议名>-LLM] / [<协议名>-从站]
从站脚本	server/<协议名>_server.py，支持 --port 和 --strict
报告文件	report_<协议名>_<时间戳>.html / .pdf
依赖	尽量用标准库
十四、版本规划
版本	主要变更	状态
v1.5.0	Modbus + S7Comm，if-elif 分支	✅ 已完成
v1.6.0	架构重构（5 项改进）	✅ 已完成（2026-09-16）
v1.6.1	DNP3 接入 + 反模式 E-H + 十七/十八章（多位置一致性清单 + Checklist）	✅ 已完成（2026-09-16）
v1.6.2	IEC 60870-5-104 接入 + 反模式 I	✅ 已完成（2026-09-16）
v1.6.3	IEC 61850 MMS 接入 + 反模式 J	✅ 已完成（2026-09-16）
v1.7.0	7 协议全量 + ENIP/OPC UA + 反模式 K-N + LLMStatus/security/DPAPI	✅ 已完成
v1.7.1	llm_mutator 基类化重构 + color_output + stop_event + 反模式 O-W（6 轮审计全闭环）	✅ 已完成（2026-09-17）
v1.7.2	第 7 轮六层审计 + L1/L2 一致性修复 + 反模式 X-Y（从站 CLI 接口统一、基类签名对齐）	✅ 已完成（2026-09-18）
v1.8.0	真实 PLC 设备适配（connect/disconnect/is_connected 连接生命周期、persistent 长连接+失败熔断、_recv_frame 帧循环接收、kwargs 贯穿）+ 第 8-10 轮审计闭环 + 反模式 Z（测试 mock 打错模块层级）+ 反模式 K 收尾（4 协议循环变量统一 func_code）	✅ 已完成（2026-09-18）
v2.0.0	真实设备支持纳入扩展标准（9 方法接口 + 11 步流程 + 17 项清单 + menu.py PROTOCOL_CONNECT_PARAMS + README 真机指南）	✅ 已完成（2026-09-18）
v2.1.0	桌面端（Tauri / PyQt）+ 多协议并行	📋 规划中
十五、附录：常见问题
Q1：新增协议后菜单没显示？
运行 python tools/check_protocol.py <name> 检查。重点看 func_codes JSON 是否存在、func_codes 字段是否非空。

Q2：从站启动超时？

检查 server/<name>_server.py 是否存在

检查是否支持 --port 参数

端口被占用时系统会自动 +1 向上查找

Q3：报告里功能码显示为 Unknown？
在 PROTOCOL_CONFIG[<name>]["func_name_map"] 里补充功能码映射。

Q4：为什么模拟从站不需要变异？
变异是主站侧行为。从站只负责"回答"，不负责"变异"。从站的定位是"连通性测试靶子"，要获得有意义的测试结果需连接真实设备。

Q5：run_fuzz 为什么放在 client.py 而不是单独文件？
run_fuzz 是协议实现的一部分（它是"如何执行该协议的模糊测试流程"），与 build_request / send_payload 属于同一抽象层级。放在 client.py 里可以让协议实现更内聚，也避免额外文件。

Q6：PROTOCOL_CONFIG 里如果漏了某个协议会怎样？
报告生成时会用默认值：

func_name_map 缺失 → 显示 Unknown

write_funcs / critical_funcs 缺失 → 分级只看 CONN_CLOSED

slave_note 缺失 → 不显示模拟从站提示

运行 python tools/check_protocol.py <name> 可检测出缺失项。

Q7：报告生成时 NameError: name 'PROTOCOL_FUNC_MAPS' is not defined？
这是 v1.6.0 重构时的典型残留 bug：旧字典已经删了但还有引用没清。按以下步骤排查：

1. 全文搜索旧字典名（rg "PROTOCOL_FUNC_MAPS" 或 rg "PROTOCOL_DISPLAY_NAME"）
2. 全文搜索重复函数定义（rg "^def _get_func_name" 看是否出现两次以上）
3. 运行 python tools/check_protocol.py modbus，"核心文件无重复函数" 这一项会自动检测

根因通常是：重构配置时同时存在新旧两套函数（旧函数硬编码旧字典，新函数用 PROTOCOL_CONFIG），旧函数没删干净。Python 以后定义的为准，所以调用链会落到旧函数上触发 NameError。

Q8：多次 Edit 同一个文件时怎么防止出错？
按 5.4 节"集中配置文件编辑守则"三条执行，最关键的操作习惯：

- 每次 Edit 只做一件事（加字典、删旧函数、改 helper、改调用方 分开做）
- 每步改完立即 python -c "import 模块" 验证
- 改完所有步骤后跑 check_protocol.py，让 AST 扫描兜底

十六、反模式与防护清单
以下是 v1.6.0 实施过程中踩过的坑，**后续所有开发者必须避开**。
#### 反模式 A：多文件分散配置 → 一处集中时的残留
| 症状 | 根因 | 修复 |
|------|------|------|
| NameError: PROTOCOL_FUNC_MAPS | 旧字典已删，但还有函数引用它 | rg 搜旧名 → 替换 → 删旧定义 |
| 两个 _get_func_name 共存 | 重构时旧函数没删 | 全文搜 "^def _get_func_name" → 保留一份 |
| classify_severity 和 _get_func_name 混用新旧 helper | 分多次改、没回头看 | 改完一份文件立即 python -c 全量 import |

**防护**：`tools/check_protocol.py` 第 10 项"核心文件无重复函数"（AST 自动扫描）；5.4 节三条守则。

#### 反模式 B：if-elif 分支膨胀
| 症状 | 根因 | 修复 |
|------|------|------|
| fuzz_loop_llm.py 出现 _run_dnp3、_run_xxx 分支 | 新协议加了但没有实现 run_fuzz | 检查 ProtocolBase.run_fuzz 是否为抽象方法、是否有 NotImplementedError |
| 新增协议后 fuzz_loop_llm.py 必须加分支 | 架构没对齐 ProtocolBase.run_fuzz | 必须把 run_fuzz 放在 client.py，fuzz_loop_llm.py 只调 registry |

**防护**：check_protocol.py 会验证 client 继承 ProtocolBase 且实现 run_fuzz；fuzz_loop_llm.py 禁止写 if-elif（代码里 grep 一遍）。

#### 反模式 C：menu.py / slave_launcher.py 硬编码
| 症状 | 根因 | 修复 |
|------|------|------|
| 新增协议后菜单没显示但 JSON 存在 | 手改 PROTOCOL_META 时漏了新协议 | 必须删除 PROTOCOL_META，用扫描函数 |
| slave_launcher.py 报找不到从站 | 手改 PROTOCOL_SLAVE_SCRIPTS 时漏了新协议 | 必须删除字典，按 server/<name>_server.py 约定路径查找 |

**防护**：grep -n "PROTOCOL_META\|PROTOCOL_SLAVE_SCRIPTS" src/core/ → 结果为空才对。

#### 反模式 D：registry 未自动加载
| 症状 | 根因 | 修复 |
|------|------|------|
| registry: [] 空列表 | __init__.py 没被 import | main.py 必须调用 auto_load_builtin() |
| check_protocol.py 能找到协议但 main.py 找不到 | auto_load_builtin 只在 main.py 调 | check_protocol.py 直接 import src.protocols.<name> 触发 __init__，与 main.py 路径不同 |

**防护**：registry.py 的 auto_load_builtin() 通过扫描 src/protocols/<name>/__init__.py 自动加载，main.py 必须调用。

#### 反模式 E：import 顺序放错 → 依赖先于使用
| 症状 | 根因 | 修复 |
|------|------|------|
| ImportError: cannot import name 'struct' 或 NameError: name 'struct' is not defined | 新建 client.py 时把 `import struct` 写到文件底部，但 `struct.pack` 在前面的 `build_dnp3_request` 里已经用到了 | **所有 import 必须在文件顶部**，按 stdlib → 第三方 → 本项目 的顺序 |
| 写代码时边写边加 import 导致顺序混乱 | 没先规划依赖关系 | 写新文件前先列好要用到的模块，顶部一次性写全 |

**防护**：写完新文件立即 `python -c "import src.protocols.<name>.client"` 验证无 ImportError。AST 不会帮你查这个（AST 只看语法对不对，不检查运行时依赖）。

#### 反模式 F：协议字段知识错误 → 瞎编功能码
| 症状 | 根因 | 修复 |
|------|------|------|
| 功能码名字像 `Read Binary Input` 这种混了 Modbus 风格 | 没查 DNP3 标准文档就凭印象瞎编 | 必须查官方协议文档或权威参考（IEC 60870-5 或 dnp3.org） |
| 漏了半截功能码（0x00 / 0x0A / 0x0C / 0x16-0x1E / 响应码 0x81-0x82） | 只看了功能码表的一部分 | **对照完整功能码表逐条核对**，确保不缺不漏 |
| 协议层 `_FUNC_NAME_MAP` 有 19 个但标准有 31 个 | 从其他协议模板抄了部分条目 | 每个协议独立查文档，不抄其他协议的功能码 |

**防护**：新增协议的功能码定义必须**对照官方文档完整列表**。写完后用临时脚本断言数量和内容：
```python
# 写完 func_codes JSON 后立即跑
import json
data = json.load(open("src/protocols/func_codes/<name>_func_codes.json"))
assert len(data["func_codes"]) == N   # N 是你查文档得到的准确数量
```

#### 反模式 G：report_generator.py 同协议条目出现两次
| 症状 | 根因 | 修复 |
|------|------|------|
| Python 不报错但只有后面那条生效，前面那条变死代码 | 在旧条目还没删的情况下先写了新条目 | 按 5.4 守则：**先整块删旧的，再写新的** |
| 两个条目一个是空配置（`func_name_map: {}`）一个是完整配置 | 第一次加了空占位，第二次补全内容但忘了删空的 | 全文搜 `"dnp3": {` 看出现几次，必须只有一次 |

**防护**：
- `rg -c '"<name>": \{' src/core/report_generator.py` → 计数必须 = 1
- check_protocol.py 第 10 项"核心文件无重复函数"虽然只查**函数**定义，但人工改 PROTOCOL_CONFIG 时必须自己注意
- 写完立即 `python -c "from src.core.report_generator import PROTOCOL_CONFIG; print(len(PROTOCOL_CONFIG))"` 看协议总数对不对

#### 反模式 H：功能码定义分散 5 处 → 改一处忘四处
| 症状 | 根因 | 修复 |
|------|------|------|
| func_codes JSON 有 31 个但 mutator.py _FUNC_CODE_POOL 只有 19 个 | 改了 JSON 但忘了改 mutator、server、report_generator、client | **改功能码必须全链路改**，共 5 处（见下表） |
| report_generator 用旧名字但 client.py 用新名字 | 改顺序混乱、中间没验证 | 写临时脚本一次性验证 5 处内容完全一致 |

**防护**：改功能码前先看"十七、多位置功能码一致性清单"，改完跑"十八、新增协议 Checklist"。

#### 反模式 I：请求/响应码混淆 → func_codes JSON 数量漂
| 症状 | 根因 | 修复 |
|------|------|------|
| JSON 34 个但 REQUEST_TYPES 只有 33 个，差 1 个 | 把响应方向的 ASDU（如 0x46 M_EI_NA_1 初始化结束）放进了 func_codes | func_codes JSON **只列主站能发送的请求码**，响应码放在 client.py `_FUNC_NAME_MAP` 里用于报告显示即可 |
| report_generator func_name_map 数量比 JSON 多一倍 | 把 0x01-0x40（监测方向上行）也塞进了"请求码" | func_codes JSON = 纯请求（C_开头 / 系统命令 / 参数 / 文件传输），client.py func_name_map = 请求 + 响应 + 监视方向全部（报告显示用） |

**防护**：
- func_codes JSON 数量 = REQUEST_TYPES 数量 = mutator.py _FUNC_CODE_POOL 数量 = server _KNOWN_FUNCS 数量（4 个位置必须一致）
- client.py _FUNC_NAME_MAP 数量 ≥ 上面 4 个位置（多出来的是监视方向 + 响应码，用于报告显示）
- IEC104 分类规则：TypeID 0x2D-0x40 是下行控制命令、0x64-0x71 是系统/参数命令、0x78-0x7E 是文件传输 → 这些才进 func_codes；0x01-0x28 是上行监视方向、0x46 是响应 → 只进 func_name_map

#### 反模式 J：手动对齐多位置时漏了一个码
| 症状 | 根因 | 修复 |
|------|------|------|
| JSON 17 个但 REQUEST_TYPES 只有 16 个，差 0x83 | 手动写集合时漏掉一个码（0x83 CONFIRMED_REQUEST 是 MMS 通用容器，很容易被忽略） | 写断言脚本：`assert set(json_codes) == REQUEST_TYPES`，不要靠肉眼数 |
| report_generator write_funcs 集合漏了 1 个 | 复制粘贴时漏行 | 用 JSON codes 作为基准，其他 3 处（client REQUEST / mutator POOL / server KNOWN）都从 JSON 生成，不靠手动复制 |

**防护**：
- 阶段 2 写完 func_codes JSON 后，把 JSON 读出来作为其他集合的基准来源
- 写断言脚本验证 4 个位置的 set 完全相等
- 如果发现某个码在 JSON 里有但在 client REQUEST 里没有，**立即修正**（不要跳过等后面处理）

#### 反模式 K：client.py 循环内变量名各协议不同 → 批量 patch 写错变量
| 症状 | 根因 | 修复 |
|------|------|------|
| `NameError: name 'func_code' is not defined` 在 enip / iec104 / iec61850 / opcua 的 client.py 跑 fuzz 时触发 | 7 个协议的 run_fuzz 循环变量名**不一致**：<br>• modbus / s7comm / dnp3 → `func_code`<br>• **enip → `service_code`**<br>• **iec104 → `type_id`**<br>• **iec61850 → `pdu_type`**<br>• **opcua → `service_id`**<br><br>批量 patch 脚本假设所有协议都叫 `func_code`，结果 4 个协议崩了 | **patch 前先探测每个协议的变量名**：<br>`grep 'for idx, fc' client.py` → 找到循环定义行<br>`grep '= int(fc_str' client.py` → 找到赋值行<br>然后用真实变量名替换 |
| opcua client.py 缺 `on_fallback_used` / `on_fallback_only` 两个调用 | 不同协议的 fallback 逻辑代码结构略有差异，批量 patch 的正则可能漏匹配 | patch 后手动打开每个 client.py 检查三个位置：<br>1. `llm_generate_mutations(... func_code_str=...)`<br>2. `[LLM] 变异不足 → on_fallback_used`<br>3. `[LLM] 未生成变异 → on_fallback_only` |

**防护**：
- 任何跨协议批量 patch 前，先跑一次**探测脚本**：对每个 client.py 输出 `for idx` 那行和 `= int(fc_str` 那行，收集到真实变量名
- patch 完成后跑 grep：`grep -n 'on_fallback_\|llm_generate_mutations.*func_code_str' src/protocols/*/client.py`，确保 7 个协议都命中
- 新增协议时，**run_fuzz 里的循环变量名统一叫 `func_code`**，消除后续 patch 时的变量名不一致问题

#### 反模式 L：fuzz_loop_llm.py 未调 auto_load_builtin() → 协议未注册
| 症状 | 根因 | 修复 |
|------|------|------|
| `[注册表] 协议 opcua 未注册` + `[注册表] 已注册协议: []` | registry 提供了 `auto_load_builtin()` 自动发现 src/protocols/*/__init__.py 并 import，但 fuzz_loop_llm.py **没有调它** | 在 fuzz_loop_llm.py 顶部 import registry 后立即调 `auto_load_builtin()` |
| menu.py 单入口跑时正常（可能因为 menu 自己间接 import 了），直接 import fuzz_loop_llm 跑就崩 | 不同入口的 import 路径不同，谁触发了 auto_load_builtin 依赖偶然顺序 | **任何启动 fuzz 的入口（fuzz_loop_llm.py / menu.py / standalone script）都必须显式调 `auto_load_builtin()`**，不要假设"有人会先帮我 import" |

**防护**：
- 把 `auto_load_builtin()` 调用做成**任何 fuzz 入口的第 9 行**（import 之后、函数定义之前），形成固定模式
- 加 smoke test：`from src.protocols.registry import list_protocols; assert len(list_protocols()) >= 7`，在 CI 里跑

#### 反模式 M：llm_mutator.py 的 OpenAI client 不传 timeout → 云端调用无限等
| 症状 | 根因 | 修复 |
|------|------|------|
| fuzz 卡在 `[DNP3-LLM] 使用模型: xxx @ apihub.agnes-ai.com/v1` 那一行，永远不往下走 | 7 个 llm_mutator.py 里 `openai.OpenAI(...)` 没传 `timeout=` 参数 → openai 库用默认 600 秒超时或无限等 → 云端网络抖动/限流/地址不通时就挂住 | 每个 llm_mutator 的 OpenAI client 构造处加 `timeout=25`（25 秒足够 LLM 响应，又不会让用户等太久） |
| **modbus/s7comm 多行格式加 timeout 时容易搞坏语法**（`base_url=..., timeout=25` 可能被拼到 `base_url=...,timeout=25` 或出现双逗号） | 单行协议（dnp3/enip/iec104/iec61850/opcua）可以直接替换字符串，多行协议（modbus/s7comm）手动改时容易错位 | 多行格式的 OpenAI 构造：**timeout=25 独立成一行**（跟 api_key 对齐缩进），不要拼到某行末尾 |

**防护**：
- 新建 llm_mutator 模板时，**先写好 `timeout=25`** 再复制，而不是复制完再 patch
- patch 完必跑语法检查：`python -c "import ast; ast.parse(open('.../llm_mutator.py').read())"` → 7/7 全过才算
- 用户侧兜底：即使没 patch，**run_fuzz 整体有 120 秒超时熔断**（反模式 N），不会永远卡死

#### 反模式 N：fuzz_loop 没有整体超时熔断 + 没有 error_report
| 症状 | 根因 | 修复 |
|------|------|------|
| 协议 fuzz 卡住 → 手动 Ctrl+C → 什么都没有（没报告、没错误提示） | fuzz_loop_llm.py 直接调 `protocol_class().run_fuzz()` 没套 timeout → run_fuzz 内部如果某步卡住（LLM 调用或 socket connect），整个协议就永远不结束 | 用 `threading.Thread` 套 run_fuzz，`t.join(timeout=120)` 超时后检测 `t.is_alive()` → 强制终止，已有的 results 仍然生成报告 + 写 JSON error_report |
| 不知道 LLM 云端到底是 429 / 401 / 网络不通 / 超时 | 没做预连通性检查 → fuzz 开始后才在第 3 个功能码触发 LLM 调用失败，跑了一半才发现云端有问题 | **在 ">>> 开始协议" 之前跑 llm_precheck**：发 "ping" + `max_tokens=5` + `timeout=15`，精准分类 10 种错误并给出中文建议。失败不阻塞 fuzz（继续用本地 fallback），但会在控制台提示 |
| 不知道目标设备端口通不通 | 没做端口连通性检查 → fuzz 跑 90 个功能码全 CONN_CLOSED 才发现服务器没启动 | **在每个协议开始前用 socket 做 2 秒超时的 connect 测试**，不通就标 ⚠️ 提示用户 |

**防护**：
- llm_precheck + 端口连通性检查固定作为 fuzz_loop 的**步骤 0/0.5**，任何 fuzz 入口都不能跳过
- 整体协议超时固定 120 秒（代码常量 PROTOCOL_FUZZ_TIMEOUT=120，可在 config 里调），超时后自动写 `reports/error_report_<timestamp>.json`，含错误类型、当前 LLM 配置、针对性建议
- error_report 必须**即使超时也要生成**：已收集的 results 仍然走 generate_report，让用户看到已跑的那部分结果 + 警示

#### 反模式 O：写了代码但从未运行验证的假修复
| 症状 | 根因 | 修复 |
|------|------|------|
| modbus_server 启动即 TypeError（`handler=` 参数 pymodbus 3.15 不支持） | 改了代码但没跑过启动命令，以为"语法对=能跑" | 任何修复必须附实测命令与输出；server 改完必须 `python server/<name>_server.py --port <x>` 实测启动 |
| result_analyzer 分发表永不命中（protocol 字段缺失） | 只改了调用方没改数据结构，没跑过端到端 | 验证脚本不得只覆盖单协议；改数据结构必须跑全协议 fuzz 验证分发命中 |

**防护**：
- 修复后必须跑实测命令并贴输出，不接受"应该能跑"
- 涉及多协议的改动（如 result_analyzer 分发），验证脚本必须覆盖所有协议
- 改 server.py 必须实测启动 + 连接 + 收发，不只是 `compileall`

#### 反模式 P：验证依赖随机性（flaky test）
| 症状 | 根因 | 修复 |
|------|------|------|
| modbus verify ≈30% 通过率被当成 5/5 PASS | mutator 用 `random.choice` 选功能码，白名单全合法时偶发全 NORMAL | 随机路径须固定 seed（`random.seed(42)`）；关键验证连续跑 ≥5 次 |

**防护**：
- verify_fuzz_flow.py 必须 `random.seed(固定值)` 保证确定性
- 涉及随机逻辑的修复连续跑 ≥5 次，全绿才算通过
- 新增协议的 mutator 若用 random，测试时必须可复现

#### 反模式 Q：加密操作缺幂等保护
| 症状 | 根因 | 修复 |
|------|------|------|
| store_api_key 对密文二次加密 → 复用"上次选择"即 401 自毁 | 加密入口没判断是否已是密文，用户复用配置时重复加密 | 加密入口必须先 `is_encrypted()` 判断；"配置→保存→重启→复用配置→fuzz"全链路必须回归 |

**防护**：
- `security.encrypt_key()` 前先 `is_encrypted()` 检查
- 涉及 security/config 的改动必须跑：输入 key → 保存 → 重启程序 → 选"上次选择" → fuzz，无 401
- 新增协议不涉及 security，但改 report_generator 时注意不要碰 config 读写逻辑

#### 反模式 R：功能码集合多处手动维护必漂移
| 症状 | 根因 | 修复 |
|------|------|------|
| server 白名单 16 vs JSON 19（漏 0x08/0x0B/0x0C） | 白名单手抄时漏行，改 JSON 没同步改 server | 白名单从 func_codes JSON 单一来源生成，禁止手抄 |

**防护**：
- 新增协议时，server 的 `_KNOWN_FUNCS` / `_REQUEST_TYPES` 从 JSON 读取生成，不手动写死
- 改完跑断言：`assert set(json_codes) == set(server_request_types)`
- （详见十七章多位置一致性清单）

#### 反模式 S：仿真器校验面收窄导致检出能力退化
| 症状 | 根因 | 修复 |
|------|------|------|
| 弃 pymodbus 自实现 socket 后只校验功能码，数据区错误全 NORMAL | 重写从站时丢了旧实现的异常触发面（quantity>0x7D 等） | 重写从站时须比对旧实现的异常触发面；变异器与从站白名单需联合设计（功能码池须含非法码 0x5A/0xA5/0xFF） |

**防护**：
- 新增/重写 server 时，列出旧实现所有会触发异常的条件，逐一保留
- mutator 的 `_FUNC_CODE_POOL` 必须含非法码（如 0x5A/0xA5/0xFF），否则从站永远返回 NORMAL
- verify 时确认至少有 EXCEPTION 或 CONN_CLOSED 分类出现

#### 反模式 T：HTML 拼接点转义遗漏在新路径复发 → 存储型 XSS
| 症状 | 根因 | 修复 |
|------|------|------|
| `target`（用户自由输入的 host:port）可注入 `<script>` | 直接 `f"... {target} ..."` 拼 HTML，未 `html.escape` | 所有进入 HTML 的外部文本先过 `_esc()` 辅助函数（`html.escape(str, quote=True)`） |
| `protocol_errors` 的 `reason`/`error_msg` 含云端 API 返回内容（str(e)），可含 `<script>`/`<img onerror>` | str(e) 来源不可控，与 llm_status 的转义策略不一致（P2-007 同类问题在新整合路径复发） | 合并报告 zh/en 两版 + `generate_error_report` 共 3 处 reason 全部 `_esc()`，protocol 名也转义 |
| `skipped`/`build_failures` 的 `reason` 未转义 | reason 来自 client.py 的 `skip.append({"reason": "..."})` 或异常 str | 两处 reason 全部 `_esc()` |
| `gpu_summary` 未转义 | GPU 信息来自 subprocess 输出，理论上可控 | 提取后 `_esc()` 再拼 HTML |

**必须转义的文本清单**（新增协议/改报告时逐项核对）：
| 文本来源 | 变量示例 | 风险 |
|----------|----------|------|
| 用户输入 target | `target` / `host:port` | 存储型 XSS（本地报告） |
| 异常字符串 str(e) | `reason` / `error_msg` | 云端 API 返回内容注入 |
| skipped 原因 | `skipped[i]["reason"]` | client 侧自由文本 |
| build_failures 原因 | `build_failures[i]["reason"]` | 同上 |
| GPU 摘要 | `gpu_summary` | subprocess 输出 |

**防护**：
- report_generator.py 顶部定义 `_esc = lambda s: html.escape(str(s), quote=True)`，所有拼 HTML 的外部文本先过它
- `report_generator.py 不导入 color_output`（防止 ANSI 转义码泄漏进 HTML）
- 新增协议时，PROTOCOL_CONFIG 的 `slave_note` / `display_name` 虽然是开发者写的、通常可信，但仍然建议走 `_esc()` 形成统一习惯
- 复审时 grep 新增 f-string 拼接点核对转义覆盖
- 验证：构造含 `<script>alert(1)</script>` 的 target / reason 跑一次报告生成，`grep -c '<script>' reports/report_*.html` 必须 = 0

#### 反模式 U：llm_mutator prompt 承诺等长但不校验 → 变异长度失控
| 症状 | 根因 | 修复 |
|------|------|------|
| LLM 返回任意长度的 hex 都被发送给目标设备 | prompt 里写了 "Keep same total length" 但 `_clean_line` 只做格式清洗不校验长度 | 用 `base_payload_hex` 算 `base_len = len(base_payload_hex)`，长度超出 `[base_len//2, base_len*2]` 的变异丢弃并告警 |
| `base_payload_hex` 参数传入后闲置（死参数） | 函数签名有这个参数但函数体没用 | 启用它做长度校验的基准，参数不再是死参数 |

**防护**：
- llm_mutator_base.py 的 `generate_mutations()` 必须用 `base_payload_hex` 算长度区间
- 新协议的 llm_mutator 薄壳调用基类时必须传 `base_payload_hex=base_hex`
- 验证：mock 一个返回超长/超短 hex 的 LLM 响应，确认该条被丢弃且 `on_error` 被调用

#### 反模式 V：OpenAI SDK max_retries 未清零 → 重试叠加加剧限流
| 症状 | 根因 | 修复 |
|------|------|------|
| 429 场景下单个功能码最多发 9 次请求（SDK 默认 2 + 应用层 3） | `openai.OpenAI(...)` 构造器没显式设 `max_retries=0`，SDK 默认 2 次 | 构造器加 `max_retries=0`，仅保留应用层 `max_retries=3` 的重试逻辑 |

**防护**：
- llm_mutator_base.py 的 OpenAI client 构造处必须 `max_retries=0`
- grep 验证：`rg 'max_retries=0' src/protocols/llm_mutator_base.py` 必须命中
- 新协议 llm_mutator 走基类，不需要自己构造 OpenAI client（已统一）

#### 反模式 W：content None 被宽 except 吞 + 未分类异常不上报 on_error
| 症状 | 根因 | 修复 |
|------|------|------|
| LLM 返回 content=None 时 `response.choices[0].message.content.strip()` 抛 AttributeError | 未做 None 防护，直接 `.strip()` | `msg = response.choices[0].message; content = msg.content if msg and msg.content else ""` |
| AttributeError 被 `except Exception` 吞掉，白耗 3 次重试 | 宽 except 吃掉了空响应错误 | 空内容调 `on_error(fc, "EMPTY_RESP", "模型返回空内容")` 后 continue，不再进重试循环 |
| 未分类异常（`_parse_error` 返回空 code）只 print 不调 on_error → `with_error` 统计偏低 | 异常分支漏了 on_error 调用 | 未分类异常调 `on_error(fc, "UNKNOWN", err_str[:120])`，保证 LLMStatus 统计准确 |

**防护**：
- llm_mutator_base.py 取 content 必须做 None 三元防护
- 所有异常分支（429/401/403/404/5xx/TIMEOUT/CONN/EMPTY/UNKNOWN）都必须调 `on_error(func_code_str, error_code, detail)`
- 验证：mock content=None 的响应，确认 on_error("EMPTY_RESP") 被调用且不重试

#### 反模式 X：从站 CLI 参数接口不一致 → 部分从站缺 `--host`

| 症状 | 根因 | 修复 |
|------|------|------|
| modbus_server 用手工 `sys.argv` while 循环，只支持 `--port`/`--strict`，不支持 `--host`，`__main__` 硬编码 `DEFAULT_HOST` 传入 `run_server` | 首个从站（modbus）早于其余 6 个编写，未跟上后来统一的 argparse 三参数接口 | `_parse_args()` 改用 `argparse`，统一 `--host`/`--port`/`--strict`，返回 `(host, port, strict)`；`__main__` 传入解析后的 host |

**防护**：
- 所有从站 `server/<name>_server.py` 的 `_parse_args()` 必须使用 argparse，且三参数齐全（`--host` 默认 127.0.0.1、`--port`、`--strict`）
- 新增从站时复制现有从站模板（如 s7comm_server.py），不要手工重写参数解析
- 验证：`python server/<name>_server.py --help` 必须同时显示 `--host HOST --port PORT --strict`；`rg 'add_argument' server/<name>_server.py` 应命中 3 个

#### 反模式 Y：抽象基类签名与实现类不对齐 → 调用方传参时基类签名缺失

| 症状 | 根因 | 修复 |
|------|------|------|
| `base.py:ProtocolBase.run_fuzz` 签名缺 `llm_status=None, stop_event=None`，但 7 个实现类和 fuzz_loop 调用方都传这两个参数 | 基类抽象方法签名未跟随实现类/调用方的参数演进同步更新 | 基类 `run_fuzz` 签名补齐 `llm_status=None, stop_event=None`，与 7 个实现类完全一致 |

**防护**：
- 抽象基类（`base.py`）的方法签名必须与所有实现类保持一致；实现类新增参数时，基类必须同步
- 验证：`rg 'def run_fuzz' src/protocols/` 确认 base.py 与 7 个 client.py 签名完全相同

---

#### 反模式 Z：测试 mock 打错模块层级 → 被测路径绕过 mock（LLM 路径绕过 seed，flaky 复发）

**来源**：第 9-10 轮审计（2026-09-18，verify_fuzz_flow modbus EXCEPTION 断言间歇 FAIL）

| 症状 | 根因 | 修复 |
|------|------|------|
| `verify_fuzz_flow` 声称已禁用 LLM（patch 了 `<协议>.llm_mutator._load_model_config`），但在装有 openai 的环境下 LLM 路径仍然连通云端/ollama，seed=42 本地变异被绕过，`EXCEPTION分类出现` 断言间歇 FAIL（结果不可复现） | `generate_mutations()` 内部实际调用的是 `llm_mutator_base.py` 模块级的 `_load_model_config`，patch 协议级薄壳的同名函数不影响基类的真实引用——mock 覆盖的是"名字"而非"被测函数实际解析到的模块" | verify_fuzz_flow.py 补 patch 真实引用点：`importlib.import_module("src.protocols.llm_mutator_base")._load_model_config = lambda *a, **k: {}`，彻底切断 LLM 路径 |

**防护**：
- mock 前先确认被测函数的真实引用链：`rg "_load_model_config" src/protocols/` 找出**所有定义点与调用点**，patch 实际被调用的那一个（v1.7.0 基类化后为 `llm_mutator_base` 模块级函数，不是协议薄壳）
- 禁用 LLM 的测试必须在"装有 openai 的环境"（agentscope_env）下跑——未装 openai 时 LLM 路径天然不通，mock 打错也测不出来（假阴性）
- 确定性验证：seed 固定后连续跑 ≥5 次结果必须完全一致；出现间歇差异即怀疑 mock 未生效（与反模式 P 联合判断）

---

**关于 llm_mutator_base.py 基类（v1.7.0 重构）**：
7 个协议的 llm_mutator.py 已合并为 `src/protocols/llm_mutator_base.py` 基类 + 7 个薄壳（27-45 行）。薄壳只负责 `_build_prompt()`（协议特异 prompt）和 `LOG_PREFIX`，其他逻辑（模型配置加载、provider 解析、错误分类、重试、长度校验、None 防护）全部在基类。新增协议时：
- 复制一个现有薄壳（如 s7comm/llm_mutator.py），改 `LOG_PREFIX` 和 `_build_prompt()` 里的协议名
- 不要在薄壳里写 OpenAI client 构造、重试、错误分类——这些由基类统一处理
- 基类的 `generate_mutations()` 签名：`(base_payload_hex, count=5, status_collector=None, func_code_str=None, on_error=None)`

十七、多位置功能码一致性清单
**每次新增协议 / 修改功能码定义时，必须同步检查以下 5 个位置**。漏了任何一个，check_protocol.py 不会全部报警（它只查 JSON 和 report_generator 的条目，不查 client.py / mutator.py / server.py 里的硬编码）。

| # | 文件 | 位置 | 改什么 | 验证命令 |
|---|------|------|--------|----------|
| 1 | `src/protocols/func_codes/<name>_func_codes.json` | 顶层 `func_codes` 数组 | 协议请求功能码完整列表（不含响应码 0x81+） | `python -c "import json; d=json.load(open('...')); print(len(d['func_codes']))"` |
| 2 | `src/protocols/<name>/client.py` | `_FUNC_NAME_MAP` 字典 + `get_func_codes()` 方法 | 功能码→名字映射（含请求 + 响应码，响应码用于报告分类显示） | `python -c "from src.protocols.<name>.client import _FUNC_NAME_MAP; print(len(_FUNC_NAME_MAP))"` |
| 3 | `src/protocols/<name>/mutator.py` | `_FUNC_CODE_POOL` 列表 | 本地变异时随机挑选的请求功能码池 | `python -c "from src.protocols.<name>.mutator import _FUNC_CODE_POOL; print(len(_FUNC_CODE_POOL))"` |
| 4 | `server/<name>_server.py` | `_KNOWN_FUNCS` 集合 | strict 模式校验时认可的合法请求功能码 | `python -c "import ast; src=open('...').read(); tree=ast.parse(src); known=...; print(len(known))"` |
| 5 | `src/core/report_generator.py` | `PROTOCOL_CONFIG["<name>"]["func_name_map"]` + `write_funcs` + `critical_funcs` | 报告生成时用的功能码名字 + 分级 | `python -c "from src.core.report_generator import PROTOCOL_CONFIG; d=PROTOCOL_CONFIG['<name>']; print(len(d['func_name_map']), len(d['write_funcs']), len(d['critical_funcs']))"` |

**5 处数据之间的关系**：
- 位置 1 = 位置 3 = 位置 4 的数量（纯请求码数量）
- 位置 2 = 位置 5 func_name_map 的数量（请求码 + 响应码，响应码用于报告显示）
- 位置 5 write_funcs + critical_funcs ⊂ 请求码集合，必须是位置 3 的子集
- 如果 位置 1=31 个请求码，位置 2 和 5 应该是 33 个（31 请求 + 2 响应 0x81/0x82）

**DNP3 实例验证（31 请求 + 33 含响应）**：
```
位置 1 JSON:           31 codes (0x00-0x1E) ✅
位置 2 client.py:      33 entries (0x00-0x1E + 0x81/0x82) ✅
位置 3 mutator.py:     31 request codes (0x00-0x1E) ✅
位置 4 server:         31 known funcs (0x00-0x1E) ✅
位置 5 report_generator: 33 entries + 29 write + 6 critical ✅
```

十八、新增协议标准操作 Checklist
**严格按顺序执行，每步完成后 ✅ 才能进下一步**。AI 或人类开发者都必须遵循。

### 阶段 1：信息收集（动手前）
- [ ] **1.1** 查官方协议文档，得到完整功能码列表（请求码 + 响应码）、帧格式（固定头 + 字段偏移 + CRC 算法）、默认端口
- [ ] **1.2** 确认是否有现成 Python 库可用（如 pymodbus for Modbus），如果库是回调式 API（如 dnp3protocol），决定走 raw socket 方案
- [ ] **1.3** 确认 write_funcs（写操作、控制、重启、冻结等）和 critical_funcs（重启、停机、保存配置等高危）的分类
- [ ] **1.4** 探测现有 client.py 的循环变量名命名风格（是否全叫 `func_code`？有协议叫 `service_code` / `type_id` / `pdu_type` / `service_id` 的），决定新协议跟现有风格还是推动统一
- [ ] **1.5** 确认协议是否需要**握手**才能发变异报文（OPC UA 必须 Hello→ACK 才能发 MSG），如有则在 client.py 的 send 阶段先做握手

### 阶段 2：协议层代码（src/protocols/<name>/）
- [ ] **2.1** 创建目录 `src/protocols/<name>/`
- [ ] **2.2** 创建 `func_codes/<name>_func_codes.json` — 对照阶段 1.1 文档逐条核对
  - [ ] 跑完断言脚本：`python -c "import json; d=json.load(open('src/protocols/func_codes/<name>_func_codes.json')); assert len(d['func_codes']) == N"`
- [ ] **2.3** 创建 `client.py` — 所有 import 在文件顶部，继承 ProtocolBase 实现 6 个方法 + run_fuzz
  - [ ] `build_request(func_code=...)` 能生成有效基准报文
  - [ ] `run_fuzz()` 能正确遍历功能码、生成变异、发送、收集结果
  - [ ] **run_fuzz 内循环变量名**：统一叫 `func_code`（参考反模式 K），方便后续跨协议批量 patch
  - [ ] **需要握手的协议**：`send_payload()` 或独立函数里先做握手（Hello→ACK），再发变异报文（OPC UA 是唯一需要的）
  - [ ] `python -c "from src.protocols.<name>.client import <Name>Client, _FUNC_NAME_MAP; print(len(_FUNC_NAME_MAP))"` 不报错
- [ ] **2.4** 创建 `mutator.py` — `mutate_payload()` 函数，`_FUNC_CODE_POOL` 与 JSON 请求码数量一致
  - [ ] `python -c "from src.protocols.<name>.mutator import _FUNC_CODE_POOL; assert len(_FUNC_CODE_POOL) == M"`
- [ ] **2.5** 创建 `llm_mutator.py` — 薄壳，调用 `llm_mutator_base.py` 基类（参考"关于 llm_mutator_base.py 基类"说明）
  - [ ] 薄壳只写 `LOG_PREFIX` 和 `_build_prompt()`，不要自己写 OpenAI client 构造/重试/错误分类
  - [ ] 调用基类 `generate_mutations(base_payload_hex=base_hex, count=5, status_collector=status_collector, func_code_str=func_code_str, on_error=on_error)`
  - [ ] `python -c "import ast; ast.parse(open('.../llm_mutator.py').read())"` → 语法检查通过
  - [ ] `rg 'max_retries=0' src/protocols/llm_mutator_base.py` → 必须命中（反模式 V）
  - [ ] `rg 'base_len = len(base_payload_hex)' src/protocols/llm_mutator_base.py` → 必须命中（反模式 U）
  - [ ] `rg 'msg.content if msg and msg.content' src/protocols/llm_mutator_base.py` → 必须命中（反模式 W）
- [ ] **2.6** 创建 `__init__.py` — `register_protocol("<name>", <Name>Client)`
  - [ ] `python -c "from src.protocols.registry import auto_load_builtin, list_protocols; auto_load_builtin(); assert '<name>' in list_protocols(); print('注册成功')"`

### 阶段 3：模拟从站
- [ ] **3.1** 创建 `server/<name>_server.py` — 支持 `--port` 和 `--strict`
  - [ ] `_KNOWN_FUNCS` 与 JSON 请求码数量一致
  - [ ] 响应报文格式符合协议标准
  - [ ] strict 模式校验起始字节 + 功能码合法性

### 阶段 4：报告配置
- [ ] **4.1** 在 `src/core/report_generator.py` 的 `PROTOCOL_CONFIG` 里**整块替换**（不是追加）旧条目
  - [ ] `rg -c '"<name>": \{' src/core/report_generator.py` → 计数必须 = 1
  - [ ] func_name_map 数量 = client.py _FUNC_NAME_MAP 数量
  - [ ] write_funcs + critical_funcs ⊂ func_name_map keys
  - [ ] `python -c "from src.core.report_generator import PROTOCOL_CONFIG, _get_func_name; print(len(PROTOCOL_CONFIG)); print(_get_func_name(0x01, '<name>'))"` 不报错且名字正确
- [ ] **4.2** 报告 XSS 转义检查（反模式 T）
  - [ ] `rg 'def _esc' src/core/report_generator.py` → 必须存在 `_esc` 辅助函数
  - [ ] `rg '<script>' src/core/report_generator.py` → 不应出现在 HTML 拼接路径（模板里的字面 <script> 除外）
  - [ ] 构造含 `<script>alert(1)</script>` 的 target 跑一次单报告生成，`grep -c '<script>' reports/report_<name>_*.html` 必须 = 0
  - [ ] 构造含 `<img src=x onerror=alert(1)>` 的 build_failures reason 跑一次，确认被转义为 `&lt;img`

### 阶段 5：验证
- [ ] **5.1** `python tools/check_protocol.py <name>` — 必须 11/11 [OK]，如有 [FAIL] 或 [WARN] 必须修复或解释
- [ ] **5.2** 多位置一致性验证 — 跑一次完整断言脚本（参考十七章的验证命令）
- [ ] **5.3** registry + 完整 import 验证 — `auto_load_builtin()` 后 `<name>` 在 list_protocols() 里
- [ ] **5.4** 所有现有协议仍能通过 check_protocol — `python tools/check_protocol.py modbus; python tools/check_protocol.py s7comm`
- [ ] **5.5** LLMStatus 状态 patch 验证 — 跑真实 fuzz（可以用 LLM 或本地），检查：
  - [ ] `grep -n 'on_fallback_\|llm_generate_mutations.*func_code_str' src/protocols/*/client.py` → 7 个协议都命中（3 处）
  - [ ] 真实 fuzz 跑一遍，不出现 `NameError: name 'func_code' is not defined`
  - [ ] 如果出现变量名错误 → 用 grep 探测真实变量名（反模式 K 的探测脚本）然后修正
- [ ] **5.6** LLM precheck + timeout 熔断验证（参考反模式 M/N）：
  - [ ] `python -c "from src.core.llm_precheck import precheck_llm; ok,msg,e,d=precheck_llm({'provider':'ollama','name':'qwen'}); print(ok)"` → 应返回 True（ollama skip）
  - [ ] `grep -c 'timeout=25' src/protocols/*/llm_mutator.py` → 7 个协议都 >= 1
  - [ ] **真实 fuzz 启动时**应看到：`[预检查] LLM 连通性测试...` + `[预检查] 目标设备端口连通性...` 两个步骤的输出
  - [ ] **整体超时**：故意让 fuzz 卡住（比如 mock 一个 sleep 5s 的 run_fuzz），应在 120 秒后自动终止并写 `reports/error_report_<ts>.json`

### 阶段 6：清理
- [ ] **6.1** 删除临时断言脚本（不要留在项目里）
- [ ] **6.2** 更新 PRD 版本规划状态（如果这个协议是规划中的）
- [ ] **6.3** 如果发现了新反模式，追加到十六章
- [ ] **6.4** 删除"死代码"前必须全局 grep 引用（含 tests/ 目录）
  - [ ] 第 5 轮审计 R5-7：`_summarize_suggestions` 和 `generate_error_report` 被误判为死代码，但实际被 `tests/verify_error_report.py`、`verify_combined_report.py`、`verify_fixes.py` 引用
  - [ ] 规则：删函数前必须 `rg "函数名" --type py` 全项目搜，确认无引用才删；若被 tests/ 引用则保留并加注释说明 `# Used by tests/xxx.py; ...`

### 阶段 7：全面检查（新增协议后必跑，功能性 + 兼容性）
> 阶段 5 是"这个协议自己的 check_protocol 11/11"，阶段 7 是"加了这个协议之后，整个项目还能正常跑"。
> 安全基线回归已纳入 7.9（server 绑 127.0.0.1 / 无硬编码 Key / timeout+max_retries / 无危险调用 / 无 elif 膨胀 / Bandit 零 HIGH）；更全面的安全审计（OWASP Top 10 + LLM Top 10）见 docs/IndusFuzz 审计PRD.md。

- [ ] **7.1** 所有既有协议 check_protocol 仍然全过 — 新增协议不应破坏任何现有协议
  - [ ] `python tools/check_protocol.py modbus` → 11/11
  - [ ] `python tools/check_protocol.py s7comm` → 11/11
  - [ ] `python tools/check_protocol.py dnp3` → 11/11
  - [ ] `python tools/check_protocol.py iec104` → 11/11
  - [ ] `python tools/check_protocol.py iec61850` → 11/11
  - [ ] `python tools/check_protocol.py enip` → 11/11
  - [ ] `python tools/check_protocol.py opcua` → 11/11
- [ ] **7.2** fuzz_loop_llm.py 导入不崩 — `auto_load_builtin()` 后 registry 里有全部 8 个协议
  - [ ] `python -c "from src.protocols.registry import auto_load_builtin, list_protocols; auto_load_builtin(); print(list_protocols()); assert len(list_protocols()) >= 8"` → OK
- [ ] **7.3** menu.py 正常启动 — 不崩溃、新协议出现在列表
  - [ ] `python -c "import src.core.menu; print("menu import OK")"` → 无异常
- [ ] **7.4** slave_launcher.py 正常发现所有 8 个从站脚本
  - [ ] 扫 `server/` 目录 → 发现全部 *_server.py，无 404
- [ ] **7.5** report_generator.py PROTOCOL_CONFIG 条目数 = 8，无重复，无 KeyError
  - [ ] `python -c "from src.core.report_generator import PROTOCOL_CONFIG; print(len(PROTOCOL_CONFIG))"` → 8
- [ ] **7.6** 跑一个既有协议完整 fuzz 流程（比如 modbus），不崩溃，报告正常生成
  - [ ] 至少 3 个功能码测试，能正常发请求、收响应、分类、写报告
- [ ] **7.7** llm_mutator_base.py 有 timeout=25 — v1.7.1 重构后 timeout 统一在基类函数 generate_mutations，各协议 llm_mutator.py 导入调用
  - [ ] `rg "timeout=25" src/protocols/llm_mutator_base.py` → 命中（基类统一超时）
  - [ ] `rg "from src.protocols.llm_mutator_base import" src/protocols/*/llm_mutator.py` → 7 个都命中（确认走基类）
- [ ] **7.8** 无新引入的反模式（对照十六章 A-Z，共 26 条）
  - [ ] 没改 menu.py / fuzz_loop_llm.py 的 if-elif 分支（反模式 B）
  - [ ] 没硬编码协议名（反模式 C）
  - [ ] 没在 report_generator 出现重复条目（反模式 G）
  - [ ] report_generator.py 所有外部文本（target/reason/error_msg/gpu_summary）都走 `_esc()`（反模式 T）
  - [ ] llm_mutator_base.py 有 max_retries=0、base_len 长度校验、content None 防护（反模式 U/V/W）
  - [ ] run_fuzz 循环变量名统一叫 func_code（反模式 K）
  - [ ] 修复附实测输出，不靠"语法对=能跑"（反模式 O）
  - [ ] 随机路径固定 seed，验证连续跑 ≥5 次（反模式 P）
  - [ ] server 白名单从 JSON 生成，不手抄（反模式 R）
  - [ ] mutator 功能码池含非法码（反模式 S）
  - [ ] 所有从站 `_parse_args()` 用 argparse 且 `--host/--port/--strict` 三参数齐全（反模式 X）
  - [ ] `base.py` 抽象方法签名与所有实现类一致（`rg 'def run_fuzz' src/protocols/` 确认 base.py 与 7 个 client.py 签名相同，反模式 Y）
- [ ] **7.9 安全基线回归**（对应审计 PRD 5.12，新增协议后必做，不通过不能进主分支）
  - [ ] 新 server.py 默认监听 127.0.0.1（`rg "0.0.0.0" server/<new>_server.py` 不应命中）
  - [ ] client.py / llm_mutator.py 无硬编码 Key（`rg -i "sk-[a-z0-9]{10}" src/protocols/<new>/` 零命中）
  - [ ] llm_mutator 走基类，基类有 timeout=25 + max_retries=0（反模式 M + V）
  - [ ] 无 eval/exec/pickle.loads/os.system（`rg "\beval\(|\bexec\(|pickle\.loads|os\.system" src/protocols/<new>/` 零命中）
  - [ ] 新协议不出现在 menu/fuzz_loop 的 if-elif（`rg "elif.*<new>" src/core/` 不应命中，反模式 B）
  - [ ] Bandit 零 HIGH：`bandit -r src/protocols/<new>/ server/<new>_server.py -lll`
- [ ] **7.10 真实设备支持检查**（v2.0 新增，新增协议后必做）
  - [ ] client.py 实现 9 个方法（`rg "def (build_request|send_payload|parse_response|get_default_port|get_func_codes|run_fuzz|connect|disconnect|is_connected)" src/protocols/<new>/client.py` → 9 命中）
  - [ ] connect 实现协议握手（参照九章握手表）
  - [ ] send_payload 双模式（persistent + 无状态回退 + 失败熔断 >3 次放弃）
  - [ ] _recv_frame 按协议帧长循环接收（不一次性 recv(4096)）
  - [ ] menu.py PROTOCOL_CONNECT_PARAMS 含新协议（`rg '"<new>":' src/core/menu.py` 命中）
  - [ ] README.md + README.zh.md 的"真实设备测试指南"含新协议章节

**DNP3 接入 Checklist 完成情况**：
```
阶段 1：✅ 查完整功能码表（31 请求 + 2 响应），帧格式 0x0564 起始 + CRC16，端口 20000
阶段 2：✅ 2.1-2.6 全部完成，5.2 断言脚本验证 5 处一致
阶段 3：✅ dnp3_server.py 支持 --port --strict
阶段 4：✅ 先删旧 dnp3 条目再写新的，rg -c 确认只有 1 次
阶段 5：✅ check_protocol 11/11 OK + 三协议全过
阶段 6：✅ 临时脚本已删，PRD 已更新（v1.6.1 反模式 E-H + 十七十八章）

**IEC 60870-5-104 接入 Checklist 完成情况**：
```
阶段 1：✅ 查完整 ASDU 类型表（34 类型，TypeID 0x2D-0x7E），pyiec104 为回调式 DLL 不适合 fuzz → raw socket 方案
阶段 2：✅ 2.1-2.6 全部完成。build_iec104_request: 0x68 + len + ctrl(4) + ASDU(typeID+VSQ+COT+Origin+CommonAddr+IOA)
          func_codes JSON: 33 个请求码（排除 0x46 响应）
          client.py _FUNC_NAME_MAP: 66 个（33 请求 + 33 监视方向/响应，报告显示用）
阶段 3：✅ iec104_server.py 支持 --port --strict，_REQUEST_TYPES 33 个
阶段 4：✅ PROTOCOL_CONFIG 先确认无旧 iec104 条目再加，JSON → client → mutator → server → report_generator 数量全部一致
阶段 5：✅ check_protocol 11/11 OK + 四协议全过
          发现：JSON 最初 34 个，REQUEST_TYPES 33 个 → 0x46 M_EI_NA_1 是响应方向，从 JSON 删掉 → 33/33 一致
          build_iec104_request 长度字段计算一次就对了（APDU - 2，即 len(asdu) + 4）
阶段 6：✅ 临时脚本已删，PRD 已更新（v1.6.2 + 反模式 I）

**IEC 60870-5-104 接入 Checklist 完成情况**：
```
阶段 1：✅ 查完整 ASDU 类型表（34 类型，TypeID 0x2D-0x7E），pyiec104 为回调式 DLL 不适合 fuzz → raw socket 方案
阶段 2：✅ 2.1-2.6 全部完成。build_iec104_request: 0x68 + len + ctrl(4) + ASDU(typeID+VSQ+COT+Origin+CommonAddr+IOA)
          func_codes JSON: 33 个请求码（排除 0x46 响应）
          client.py _FUNC_NAME_MAP: 66 个（33 请求 + 33 监视方向/响应，报告显示用）
阶段 3：✅ iec104_server.py 支持 --port --strict，_REQUEST_TYPES 33 个
阶段 4：✅ PROTOCOL_CONFIG 先确认无旧 iec104 条目再加，JSON → client → mutator → server → report_generator 数量全部一致
阶段 5：✅ check_protocol 11/11 OK + 四协议全过
          发现：JSON 最初 34 个，REQUEST_TYPES 33 个 → 0x46 M_EI_NA_1 是响应方向，从 JSON 删掉 → 33/33 一致
          build_iec104_request 长度字段计算一次就对了（APDU - 2，即 len(asdu) + 4）
阶段 6：✅ 临时脚本已删，PRD 已更新（v1.6.2 + 反模式 I）
```

**IEC 61850 MMS 接入 Checklist 完成情况**：
```
阶段 1：✅ 查完整 ACSI 服务列表 + MMS PDU Type 映射，pyiec61850 为高层 ctypes 封装 → raw socket + 手动构造 TPKT/COTP/MMS PDU
          协议栈: TCP 102 → TPKT(4) → COTP(6+) → MMS PDU(ASN.1 BER)
阶段 2：✅ 2.1-2.6 全部完成
          func_codes JSON: 17 个请求方向 MMS PDU（0x81 initiate, 0xB0 read, 0xB2 write, etc.）
          client.py _PDU_TYPE_NAME_MAP: 37 个（17 请求 + 20 响应/错误方向，报告显示用）
          首次尝试犯了反模式 I——JSON 最初 37 个混了响应方向 → 立即修正为 17 个
          手动对齐 REQUEST_TYPES 时漏了 0x83 CONFIRMED_REQUEST → 反模式 J，断言脚本拦截
阶段 3：✅ iec61850_server.py 支持 --port --strict，_REQUEST_TYPES 17 个（修正后与 JSON 一致）
阶段 4：✅ PROTOCOL_CONFIG 37 个 func_name_map + 17 write_funcs + 6 critical_funcs
          关键：IEC61850 的 critical_funcs 选了 initiate/conclude/write/rename/setFile/deleteFile（关联控制 + 写操作 + 文件操作）
阶段 5：✅ check_protocol 11/11 OK + 五协议全过（端口 102 WARN 是预期行为，< 1024 需管理员）
阶段 6：✅ 临时脚本已删，PRD 已更新（v1.6.3 + 反模式 J）
```

**EtherNet/IP + OPC UA 接入 Checklist 完成情况**（v1.6.4 ~ v1.7.0）：
```
阶段 1：✅ EtherNet/IP: 查 CIP 服务码表（0x01-0x1C 常见 + 0x4C-0x54 对象特定），端口 TCP 44818 / UDP 2222
          OPC UA: 查 Service Node ID 表（446-791 共 28 个请求方向），端口 TCP 4840
          关键决策：asyncua 库暴露二进制编解码层但 API 形状不稳定 → 走手动构造二进制帧
          关键差异：OPC UA 是唯一需要 Hello→ACK 握手才能发 MSG 的协议 → 在 client.py send 里内置握手
阶段 2：✅ ENIP 27 个 CIP 服务 + OPC UA 28 个 Service Node ID
          client.py 循环变量名不一致！→ 反模式 K：
          modbus/s7comm/dnp3 → func_code
          enip → service_code（不同！）
          iec104 → type_id（不同！）
          iec61850 → pdu_type（不同！）
          opcua → service_id（不同！）
          新协议代码必须统一用 func_code（反模式 K 防护）
阶段 3：✅ enip_server.py + opcua_server.py 都支持 --port --strict
阶段 4：✅ PROTOCOL_CONFIG 7 协议条目（新增 ENIP 27 func + OPC UA 28 func）
          同时新增 PROTOCOL_NOTES（7 协议各 2-3 条协议专属注意事项）
阶段 5：✅ check_protocol 7/7 全 11/11 OK
          新增 LLMStatus 冒烟测试：模拟 429 + partial + fallback → 报告生成红色警示框
          发现反模式 L：fuzz_loop_llm.py 未调 auto_load_builtin() → 协议未注册
阶段 6：✅ 临时脚本已删，PRD 已更新（v1.6.4 + 反模式 K-L + Checklist 阶段 1.4/1.5 + 阶段 5.5）
```

**本次额外改动**（不在 Checklist 里，属于 v1.7.0 增强）：
- [src/core/llm_status.py](file:///d:/Application/AllToolsSet/AgnetPrograms/IndusFuzz/fuzz_agent/src/core/llm_status.py) 新建：LLM 调用状态收集器 + `build_warning_html()` 报告警示框（4 种严重程度 critical/high/medium/low）
- [src/core/security.py](file:///d:/Application/AllToolsSet/AgnetPrograms/IndusFuzz/fuzz_agent/src/core/security.py) 新建：DPAPI 加密 API Key + HTTPS 强制 + 打码显示
- 7 个 llm_mutator.py + 7 个 client.py 加 `status_collector` 状态回调
- report_generator.py 加 PROTOCOL_NOTES + Notes 分层渲染（协议专属 NOTE-Pxx 在通用 NOTE-xx 前）
- fuzz_loop_llm.py 加 auto_load_builtin() + LLMStatus 传递链路

**v1.7.0 第二轮修复（DNP3 fuzz 卡死问题）**：
- [src/core/llm_precheck.py](file:///d:/Application/AllToolsSet/AgnetPrograms/IndusFuzz/fuzz_agent/src/core/llm_precheck.py) 新建：LLM 预连通性检查（"ping" + max_tokens=5 + timeout=15，精准分类 10 种错误）
- 7× llm_mutator.py **OpenAI client 加 timeout=25**（反模式 M 的修复），解决云端调用无限等
- fuzz_loop_llm.py **整体重构**：加步骤 0（LLM 预检查）+ 步骤 0.5（端口连通性检查）+ threading 整体协议超时熔断（120 秒）+ 超时后自动写 JSON error_report
