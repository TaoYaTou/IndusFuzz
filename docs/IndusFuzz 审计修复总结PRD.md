# IndusFuzz 审计与修复总结 PRD

| 文档信息 | 内容 |
|----------|------|
| 版本 | v2.2.0 |
| 日期 | 2026-09-18 |
| 周期 | 2026-09-17~18，6 轮审计 + 5 轮返工闭环 + 第 7 轮六层全面审计 + L1/L2 一致性修复 + 真实 PLC 设备适配（第 8-10 轮审计闭环） |
| 依据 | 《IndusFuzz 审计PRD v2.5》《IndusFuzz 协议扩展 PRD v1.8.3》 |
| 对象 | IndusFuzz v1.8.3（7 协议：Modbus / S7comm / DNP3 / IEC104 / IEC61850 / ENIP / OPC UA，支持真实 PLC 设备） |
| 结论 | **审计 PRD 5.10 发布判定：放行（第 10 轮复审后维持）** |

---

## 1. 项目概述

### 1.1 背景

项目达到预成熟阶段后，按审计 PRD 执行全面安全审计，经历 4 轮审计 + 3 轮返工达成发布条件；随后项目实施技术债重构（llm_mutator 基类化等），又经第 5、6 轮审计与返工闭环；第 7 轮六层全面审计后，项目适配真实 PLC 设备（连接生命周期、persistent 长连接、帧循环接收），经第 8-10 轮审计与 P1 回归修复闭环。本 PRD 总结全过程：发现统计、修复轨迹、假修复教训、重构审计、真实设备适配审计、最终验证证据、遗留 backlog，并固化后续维护的回归规则。

### 1.2 审计方法

- 逐文件通读（src/core、src/protocols 7×4、server×7、integrations、main.py）+ 跨调用链追踪
- 并行子代理分摊协议层/从站层审计，重大结论由主审计亲自实锤复核
- 实测验证：check_protocol、Bandit、verify_fuzz_flow、registry/menu 导入、timeout 基线 grep
- 每轮审计结束后执行阶段 7 全面检查 9 项（强制项，v1.8.3 起含 7.9 安全基线回归）

---

## 2. 十轮审计时间线与发现统计

| 轮次 | 性质 | 发现 | 关键问题 |
|------|------|------|----------|
| 第 1 轮 | 全面审计 | 39 项（1 P0 / 6 P1 / 18 P2 / 14 P3） | security.py 整模块死代码（API Key 明文落盘）、6 协议 mutator 偏移错位、6 server 无 recv 超时、requirements.txt 为空 |
| 第 2 轮 | 修复复审 | 24/26 项落地；揭出 2 假修复 + 1 自毁链 | modbus_server 启动即 TypeError（handler= 参数 pymodbus 3.15 不支持）、API Key 双重加密自毁链（复用"上次选择"→401）、result_analyzer 分发表永不命中 |
| 第 3 轮 | 返工复审 | N2 完全修复；N1 代码正确但暴露 2 设计缺陷 | Modbus EXCEPTION 检出退化（功能码池全合法 + server 只校验白名单 → verify 间歇 FAIL ≈30%）、白名单 16 vs JSON 19 漏对齐 |
| 第 4 轮 | 终审 | 全部清零，零 HIGH 遗留 | 无。首次放行 |
| 第 5 轮 | 重构审计 | 7 项（2 P2 / 3 P3 / 1 信息 / 1 误报）；**安全基线零回退** | llm_mutator 基类化重构质量优（7 份复制 → 1 基类 + 7 薄壳，-80%）；新发现：protocol_errors/target 未转义（XSS 面）、LLM 变异长度不校验、SDK 重试叠加 |
| 第 6 轮 | 快速复审 | 7 项全部修复验证，无新问题 | 转义 16 处全覆盖（冒烟实测实体输出）、长度校验 [0.5×, 2×] 区间、max_retries=0、None 防护；发布状态维持放行 |
| 第 7 轮 | 六层全面审计 | 2 项（均为 P3 一致性） | 六层审计（功能 BUG/协议正确性/安全/LLM 风险/AI 代码风险/文本编码）+ 阶段 7 八项校验全绿；仅发现 L1 modbus_server 缺 `--host`、L2 base.py `run_fuzz` 签名缺 `llm_status/stop_event`；修复后阶段 7 再次全绿 |
| 第 8 轮 | 真实 PLC 适配全面审计 | 13 项（1 P1 / 12 P2-P3，四批次） | 批次 A 协议帧与握手：OPC UA HEL 帧 4 字节错位（P1，MessageSize 偏移错误）、s7comm 缺 COTP/Setup 握手；批次 B 帧接收与资源：recv 一次性读不处理分片（截断帧）、FD 泄漏；批次 C 连接状态机：无 connect/disconnect/is_connected 生命周期、断线不重连；批次 D 交互与配置：kwargs 不贯穿（unit_id/timeout/endpoint 丢失）、无真实设备连接提示 |
| 第 9 轮 | 第 8 批修复复审 | 揭出 P1 回归（反模式 O/S 复发 + 新反模式 Z） | 修复方声明 verify_fuzz_flow FAIL 仅因"run.log 复用断言过严"，实测 FAIL 项为 EXCEPTION 分类断言（10 条全 NORMAL）；实锤根因：①verify 的 mock patch 打错模块层级（patch 协议薄壳 `llm_mutator._load_model_config`，真实调用点在 `llm_mutator_base` 模块级）→ LLM 路径未切断、seed=42 被绕过；②modbus mutator 功能码池回归为全合法码（反模式 S 复发）；③mutator API 变动致 `local_mutate` ImportError。修复方承认"只看了汇总行没看失败断言名" |
| 第 10 轮 | P1 回归修复复审（快速） | 三重修复全绿，反模式 Z 固化 | ①verify_fuzz_flow 补 patch 真实引用点（`importlib.import_module("src.protocols.llm_mutator_base")._load_model_config = lambda: {}`）；②modbus mutator 拆合法/非法功能码池（`_ILLEGAL_FUNC_CODES=[0x5A,0xA5,0xFF]` 独立池）；③client `_generate_local_fallback` 强制 fc=0xFF 保底；阶段 7 九项全绿（含 7.9），发布状态恢复 |

### 2.1 修复轨迹总表

| 批次 | 内容 | 状态 |
|------|------|------|
| 第 1 批（P0+P1） | security 接线（store/get/migrate/validate/mask 五函数）、modbus strict、6 server settimeout(30)、s7comm/dnp3 mutator 偏移、s7comm JSON 15 码、requirements 补全 | ✅（modbus strict 第 2 轮被打回重做） |
| 第 2 批（P2） | diagnose shell 注入、4 协议 mutator 偏移、llm_status 转义、result_analyzer 分发表、dnp3 响应码过滤/CRC、max_retries=3、线程宽限 join、traceback 写日志 | ✅（result_analyzer 第 2 轮假修复，第 3 轮打回） |
| 第 3 批（返工） | modbus_server 自实现 socket（弃 pymodbus）、store_api_key 幂等保护、protocol 字段+偏移语义+report_generator 同步、verify_fuzz_flow --protocol 协议轮换 | ✅（暴露 M1/M2 设计缺陷） |
| 第 4 批（终局） | mutator 掺非法码（+0x5A/0xA5/0xFF）+ seed 确定性、server quantity>0x7D→0x03、白名单补 3 码、enip 偏移 (16,24)、classify_severity 分发、xhtml2pdf==0.2.19、main.py 复用日志锁 | ✅ 全部验证通过 |
| 第 5 批（重构） | llm_mutator_base.py 基类提取（timeout=25/max_retries=3/错误分类/fallback 全收敛）、color_output 色彩模块（VT+降级）、stop_event 协作退出、哑调用清理、协议错误整合进主报告 | ✅ 基线零回退（第 5 轮审计确认） |
| 第 6 批（收尾） | _esc() 统一转义 16 处（target/reason/protocol/skipped/gpu）、LLM 变异长度校验 [base_len//2, base_len*2]、OpenAI max_retries=0、content None 防护 + EMPTY_RESP/UNKNOWN 上报、R5-7 保留标注 | ✅ 第 6 轮复审全部通过 |
| 第 7 批（一致性） | modbus_server `_parse_args()` 改 argparse 补齐 `--host`（与 6 从站对齐）、base.py `run_fuzz` 签名补齐 `llm_status=None, stop_event=None`（与 7 实现类对齐） | ✅ 第 7 轮六层审计 + 阶段 7 全绿 |
| 第 8 批（真实 PLC 适配） | 7 协议 connect/disconnect/is_connected 连接生命周期、persistent 长连接 + 失败熔断（连续 >3 次断开重连放弃）、`_recv_frame` 按协议帧长循环接收（MBAP length / OPC UA MessageSize）、OPC UA HEL 帧 4 字节错位修正、s7comm COTP/Setup 握手、kwargs 贯穿（unit_id/timeout/endpoint）、FD 泄漏修复、run_fuzz 循环变量统一 func_code（反模式 K 收尾） | ✅ 第 9 轮复审揭出验证侧 P1 回归 |
| 第 9 批（P1 回归修复） | verify_fuzz_flow 经 importlib patch `llm_mutator_base._load_model_config` 真实引用点（切断 LLM 路径）、modbus mutator 拆合法/非法功能码池、`_generate_local_fallback` 强制非法功能码保底（无非法码时替换末条为 fc=0xFF） | ✅ 第 10 轮复审全绿，反模式 Z 并入协议扩展 PRD v1.8.3 |

---

## 3. 最终验证证据（2026-09-18 第 10 轮复审实测）

### 3.1 回归实测

| 检查 | 结果 |
|------|------|
| check_protocol 7 协议 | ✅ 7×11/11 |
| Bandit（src/ server/ main.py） | ✅ 零 HIGH |
| verify_fuzz_flow modbus | ✅ 9/9 PASS（patch `llm_mutator_base` 真实引用点后，LLM 路径真正切断，seed=42 确定性恢复） |
| verify_fuzz_flow s7comm | ✅ PASS（第 6-7 轮基线维持） |
| registry / menu 导入 / PROTOCOL_CONFIG | ✅ 7 / OK / 7 条无重复 |
| timeout=25 | ✅ 统一收敛至 llm_mutator_base.py:139（单点设置 + max_retries=0） |
| mock 真实引用点核验（反模式 Z 防护） | ✅ rg 确认 `_load_model_config` 全部定义点/调用点，verify patch 的是实际被调用的基类模块级函数 |
| HTML 转义冒烟 | ✅ `<script>` → `&lt;script&gt;` 实体输出（_esc 16 处覆盖） |

### 3.2 阶段 7 全面检查（9/9 全绿，v1.8.3 起含 7.9）

| 项 | 结果 |
|----|------|
| 7.1 既有协议 check_protocol | ✅ |
| 7.2 fuzz_loop 导入 + registry | ✅ |
| 7.3 menu 启动 | ✅ |
| 7.4 slave 脚本发现 | ✅ 7 个，modbus 实测可启动 |
| 7.5 PROTOCOL_CONFIG 条目 | ✅ |
| 7.6 完整 fuzz 流程 + 报告 | ✅ modbus + s7comm |
| 7.7 timeout=25 | ✅ |
| 7.8 无新反模式 | ✅（A-Z 26 条对照） |
| 7.9 安全基线回归 | ✅ server 127.0.0.1 / 无硬编码 Key / 基类 timeout=25+max_retries=0 / 无危险调用 / 无 if-elif 膨胀 / Bandit 零 HIGH |

### 3.3 最低要求 9 条（全部达成）

✅ 主流程跑通 / 无明文 Key 落盘（DPAPI）/ 云端强制 HTTPS / 无 eval·exec·pickle·os.system / Bandit 零 HIGH / requirements 固定版本 / s7comm 15 码 / server recv 超时 6/6 / modbus strict 生效

### 3.4 第 8-10 轮真实 PLC 适配 + P1 回归修复验证

| 检查 | 结果 | 证据 |
|------|------|------|
| 连接生命周期（第 8 批） | ✅ | 7 协议 connect/disconnect/is_connected 齐全，persistent 分支 + `_reconnect` 失败熔断（`_conn_failures > 3` 放弃），连接成功打印"已连接真实设备 host:port" |
| 帧边界接收（第 8 批） | ✅ | `_recv_frame` 按 MBAP length / OPC UA MessageSize 循环读满整帧，分片/截断处理正确 |
| mock 层级修复（第 9 批） | ✅ | verify_fuzz_flow 经 `importlib.import_module("src.protocols.llm_mutator_base")` patch 模块级 `_load_model_config`；agentscope_env（装 openai）下 LLM 路径确认切断 |
| 非法功能码保底（第 9 批） | ✅ | modbus mutator `_ILLEGAL_FUNC_CODES=[0x5A, 0xA5, 0xFF]` 独立池 + `available_types` 含 `illegal_func_code`；client `_generate_local_fallback` 检测 `h[14:16]` 无非法码时强制末条 `forced[7]=0xFF` |
| EXCEPTION 检出恢复 | ✅ | verify_fuzz_flow modbus EXCEPTION 断言由间歇 FAIL 转稳定 PASS（9/9） |
| 确定性（反模式 P/Z 联合判定） | ✅ | seed=42 固定后连续多次结果完全一致 |
| 反模式 K 收尾（第 8 批顺带） | ✅ | iec104/iec61850/enip/opcua `run_fuzz` 循环变量 grep 确认统一为 `fc_str`/`func_code` |
| 阶段 7 九项（第 9 批修复后重跑） | ✅ 9/9 全绿 | 含 7.9 安全基线回归，发布状态恢复 |

---

## 4. 六维度评分变化

| 维度 | 审计前 | 第 4 轮 | 第 6 轮 | 第 10 轮（当前） | 主要提升 |
|------|--------|---------|---------|------------------|----------|
| 正确性 | 6 | 9 | 9 | 9 | 6 协议 mutator 偏移全修正、result_analyzer 分发、白名单对齐、LLM 变异长度校验、OPC UA HEL 帧错位/s7comm Setup 握手修正（PLC 适配） |
| 安全性 | 5 | 9 | 9 | 9 | security 五函数接线闭环、shell 注入消除、HTML 全量转义（16 处）、日志双锁 |
| 健壮性 | 7 | 8 | 9 | 9 | server 超时、stop_event 协作退出、None 防护、异常分级上报、连接生命周期 + 失败熔断 + 帧循环接收 + FD 泄漏修复（PLC 适配） |
| 性能 | 7 | 7 | 8 | 8 | timeout=25 单点收敛、SDK max_retries=0 消除重试风暴、persistent 长连接省去逐报文建连 |
| 可维护性 | 7 | 8 | 9 | 9 | llm_mutator 基类化（-80% 复制粘贴）、死代码清理、签名统一、7 协议循环变量统一 func_code（反模式 K 收尾） |
| 一致性 | 6 | 8 | 9 | 9 | 转义策略统一 _esc、max_retries/JSON/requirements 对齐、verify 确定性、mock 真实引用点核验（反模式 Z 防护） |

---

## 5. 经验教训（已验证的反模式，供后续协议扩展引用）

| 编号 | 反模式 | 本周期实例 | 防护规则 |
|------|--------|-----------|----------|
| O | **写了代码但从未运行验证的假修复** | 第 2 轮 modbus handler= 参数（一行实测即崩溃）、result_analyzer 分发表（protocol 字段缺失永不命中） | 任何修复必须附实测命令与输出；验证脚本不得只覆盖单协议 |
| P | **验证依赖随机性（flaky test）** | 第 3 轮 modbus verify ≈30% 通过率被当成 5/5 PASS | 随机路径须固定 seed；关键验证连续跑 ≥5 次 |
| Q | **加密操作缺幂等保护** | store_api_key 对密文二次加密 → 复用配置即 401 自毁 | 加密入口必须先 is_encrypted 判断；"配置→退出→复用配置"全链路必须回归 |
| R | **功能码集合多处手动维护必漂移** | server 白名单 16 vs JSON 19（漏 0x08/0x0B/0x0C） | 白名单从 func_codes JSON 单一来源生成，禁止手抄 |
| S | **仿真器校验面收窄导致检出能力退化** | 弃 pymodbus 后只校验功能码，数据区错误全 NORMAL | 重写从站时须比对旧实现的异常触发面；变异器与从站白名单需联合设计（功能码池须含非法码） |
| T | **HTML 拼接点转义遗漏在新路径复发** | 第 5 轮 protocol_errors reason/error_msg 未转义（P2-007 同类问题在新整合路径复发）、target 遗留面 | 任何新增 HTML 拼接必须走统一 _esc() 辅助函数；复审时 grep 新增 f-string 拼接点核对转义覆盖 |
| Z | **测试 mock 打错模块层级 → 被测路径绕过 mock** | 第 9 轮 verify_fuzz_flow patch 协议薄壳 `llm_mutator._load_model_config`，而真实调用点是 `llm_mutator_base` 模块级函数 → LLM 路径未切断，seed=42 被绕过，EXCEPTION 断言间歇 FAIL；未装 openai 的环境下为假阴性测不出 | mock 前先 rg 确认真实引用链（所有定义点/调用点）；禁用 LLM 的测试必须在装 openai 的 venv（agentscope_env）下跑；seed 固定后连续 ≥5 次结果一致 |

**状态**：O-W 已并入《IndusFuzz 协议扩展 PRD》（v1.8.3），X-Y 已于第 7 轮并入（v1.8.3），Z 已于第 10 轮并入（v1.8.3）。十六章反模式清单现覆盖 A-Z 共 26 条。

---

## 6. 发布后 Backlog（不阻塞，按优先级迭代）

| 优先级 | 项 | 说明 |
|--------|-----|------|
| ~~P3~~ | ~~fuzz_loop_llm.py 冗余哑调用~~ | ✅ 第 5 批重构已清理（真实调用移至 report_generator:696） |
| ~~P3~~ | ~~残留线程协作停止~~ | ✅ 第 5 批已落地 stop_event 协作退出（fuzz_loop_llm.py:228） |
| ~~P3~~ | ~~7 份 llm_mutator 复制粘贴~~ | ✅ 第 5 批基类化完成（llm_mutator_base.py + 7 薄壳，-80%） |
| ~~P3~~ | ~~modbus_server 缺 --host 参数（L1）~~ | ✅ 第 7 批已补齐 argparse `--host`，与 6 从站对齐 |
| ~~P3~~ | ~~base.py run_fuzz 签名缺 llm_status/stop_event（L2）~~ | ✅ 第 7 批已补齐，与 7 实现类对齐 |
| ~~P3~~ | ~~反模式 K 收尾：4 协议循环变量统一 func_code~~ | ✅ 第 8 批 PLC 适配已顺带完成（grep 确认 iec104/iec61850/enip/opcua 均为 `fc_str`/`func_code`） |
| P3 | 待人工确认 4 项写入 README | opcua 帧构造口径（P2-006）、s7comm 10102 仿真器口径（P2-011）、TCP 分片拼包（P2-016）、MCP 桩状态（P2-017）——R5-7 主流程集成已记 README（v1.8.3） |
| P3 | llm_mutator_base 残留小项 | 死参数分支（modbus target_func_code prompt 分支）、错误码子串匹配可误判（"1429"）——均为提示级 |
| 里程碑 | P1-M5 EXE 打包 | requirements 已就绪，可启动 |
| 里程碑 | P0-M3 MCP 集成 | VulnClaw/CodeGuard/CodeInspectus 仍为桩 |

---

## 7. 后续维护回归规则（强制）

任何代码变更（新协议扩展、bug 修复、依赖升级）合入前必须通过：

1. **阶段 7 全面检查 9 项**（协议扩展 PRD）：check_protocol 全过 / registry / menu / slave 脚本 / PROTOCOL_CONFIG / 完整 fuzz（`verify_fuzz_flow --protocol <改动协议>` + s7comm 基线）/ timeout=25 / 反模式扫描（A-Z 26 条）/ 安全基线回归（7.9）
2. **安全基线回归 5 项**（审计 PRD 5.12）：server 绑 127.0.0.1、无硬编码 Key、llm_mutator timeout=25、无危险调用、menu/fuzz_loop 无 elif 膨胀
3. **Bandit**：`bandit -r src/ server/ main.py -lll -q` 零输出
4. **随机路径验证**：涉及随机逻辑的修复连续跑 ≥5 次（反模式 P）
5. **加密链路回归**（涉及 security/config 时）：配置→保存→重启→复用"上次选择"→fuzz 全链路无 401（反模式 Q）
6. **测试环境**：统一使用 agentscope_env venv（系统 Python 缺 scapy 会误报 modbus FAIL）

---

## 8. 结论

- 10 轮审计共发现 **75 项问题**（前 7 轮 59 项 + 第 8 轮真实 PLC 适配审计 13 项 + 第 9 轮 P1 回归 3 项根因），全部闭环
- 历次返工揭出 **2 次假修复、1 次自毁链、1 次 flaky 验证、1 次转义遗漏复发、1 次误归因（反模式 O 复发：只看汇总行未看失败断言名）、1 次 mock 层级假阴性（反模式 Z）**——均由"审计方亲自实测"拦截，验证了审计 PRD"不信任声明、只信任证据"的流程价值
- 第 5 批重构（基类化 + 色彩输出 + stop_event）在消除三项技术债的同时保持安全基线零回退，重构审计流程（定向审计 + 阶段 7 回归）验证有效
- 第 7 轮六层审计（功能 BUG/协议正确性/安全/LLM 风险/AI 代码风险/文本编码）确认无中高危遗留，仅 2 项 P3 一致性问题（L1/L2）已修复，阶段 7 修复后再次全绿
- 第 8 批真实 PLC 适配（连接生命周期 + persistent 长连接 + 帧循环接收 + kwargs 贯穿）使工具具备真机测试能力；第 9 轮复审揭出的验证侧 P1 回归（mock 层级 + 掺码无保证）经第 9 批三重修复后清零，反模式 Z 固化入协议扩展 PRD v1.8.3
- 最终状态：**零 P0/P1/P2 遗留，最低要求 9/9，阶段 7 九项全绿（含 7.9 安全基线），Bandit 零 HIGH → 放行发布（第 10 轮复审后维持）**
