# IndusFuzz 审计与修复总结 PRD

| 文档信息 | 内容 |
|----------|------|
| 版本 | v2.0.0 |
| 日期 | 2026-09-17 |
| 周期 | 2026-09-17 单日完成 6 轮审计 + 5 轮返工闭环（含一次大规模重构审计） |
| 依据 | 《IndusFuzz 审计PRD v2.5》《IndusFuzz 协议扩展 PRD v1.7.0》 |
| 对象 | IndusFuzz v1.7.x（7 协议：Modbus / S7comm / DNP3 / IEC104 / IEC61850 / ENIP / OPC UA） |
| 结论 | **审计 PRD 5.10 发布判定：放行** |

---

## 1. 项目概述

### 1.1 背景

项目达到预成熟阶段后，按审计 PRD 执行全面安全审计，经历 4 轮审计 + 3 轮返工达成发布条件；随后项目实施技术债重构（llm_mutator 基类化等），又经第 5、6 轮审计与返工闭环。本 PRD 总结全过程：发现统计、修复轨迹、假修复教训、重构审计、最终验证证据、遗留 backlog，并固化后续维护的回归规则。

### 1.2 审计方法

- 逐文件通读（src/core、src/protocols 7×4、server×7、integrations、main.py）+ 跨调用链追踪
- 并行子代理分摊协议层/从站层审计，重大结论由主审计亲自实锤复核
- 实测验证：check_protocol、Bandit、verify_fuzz_flow、registry/menu 导入、timeout 基线 grep
- 每轮审计结束后执行阶段 7 全面检查 8 项（强制项）

---

## 2. 六轮审计时间线与发现统计

| 轮次 | 性质 | 发现 | 关键问题 |
|------|------|------|----------|
| 第 1 轮 | 全面审计 | 39 项（1 P0 / 6 P1 / 18 P2 / 14 P3） | security.py 整模块死代码（API Key 明文落盘）、6 协议 mutator 偏移错位、6 server 无 recv 超时、requirements.txt 为空 |
| 第 2 轮 | 修复复审 | 24/26 项落地；揭出 2 假修复 + 1 自毁链 | modbus_server 启动即 TypeError（handler= 参数 pymodbus 3.15 不支持）、API Key 双重加密自毁链（复用"上次选择"→401）、result_analyzer 分发表永不命中 |
| 第 3 轮 | 返工复审 | N2 完全修复；N1 代码正确但暴露 2 设计缺陷 | Modbus EXCEPTION 检出退化（功能码池全合法 + server 只校验白名单 → verify 间歇 FAIL ≈30%）、白名单 16 vs JSON 19 漏对齐 |
| 第 4 轮 | 终审 | 全部清零，零 HIGH 遗留 | 无。首次放行 |
| 第 5 轮 | 重构审计 | 7 项（2 P2 / 3 P3 / 1 信息 / 1 误报）；**安全基线零回退** | llm_mutator 基类化重构质量优（7 份复制 → 1 基类 + 7 薄壳，-80%）；新发现：protocol_errors/target 未转义（XSS 面）、LLM 变异长度不校验、SDK 重试叠加 |
| 第 6 轮 | 快速复审 | 7 项全部修复验证，无新问题 | 转义 16 处全覆盖（冒烟实测实体输出）、长度校验 [0.5×, 2×] 区间、max_retries=0、None 防护；发布状态维持放行 |

### 2.1 修复轨迹总表

| 批次 | 内容 | 状态 |
|------|------|------|
| 第 1 批（P0+P1） | security 接线（store/get/migrate/validate/mask 五函数）、modbus strict、6 server settimeout(30)、s7comm/dnp3 mutator 偏移、s7comm JSON 15 码、requirements 补全 | ✅（modbus strict 第 2 轮被打回重做） |
| 第 2 批（P2） | diagnose shell 注入、4 协议 mutator 偏移、llm_status 转义、result_analyzer 分发表、dnp3 响应码过滤/CRC、max_retries=3、线程宽限 join、traceback 写日志 | ✅（result_analyzer 第 2 轮假修复，第 3 轮打回） |
| 第 3 批（返工） | modbus_server 自实现 socket（弃 pymodbus）、store_api_key 幂等保护、protocol 字段+偏移语义+report_generator 同步、verify_fuzz_flow --protocol 协议轮换 | ✅（暴露 M1/M2 设计缺陷） |
| 第 4 批（终局） | mutator 掺非法码（+0x5A/0xA5/0xFF）+ seed 确定性、server quantity>0x7D→0x03、白名单补 3 码、enip 偏移 (16,24)、classify_severity 分发、xhtml2pdf==0.2.19、main.py 复用日志锁 | ✅ 全部验证通过 |
| 第 5 批（重构） | llm_mutator_base.py 基类提取（timeout=25/max_retries=3/错误分类/fallback 全收敛）、color_output 色彩模块（VT+降级）、stop_event 协作退出、哑调用清理、协议错误整合进主报告 | ✅ 基线零回退（第 5 轮审计确认） |
| 第 6 批（收尾） | _esc() 统一转义 16 处（target/reason/protocol/skipped/gpu）、LLM 变异长度校验 [base_len//2, base_len*2]、OpenAI max_retries=0、content None 防护 + EMPTY_RESP/UNKNOWN 上报、R5-7 保留标注 | ✅ 第 6 轮复审全部通过 |

---

## 3. 最终验证证据（2026-09-17 第 6 轮复核实测）

### 3.1 回归实测

| 检查 | 结果 |
|------|------|
| check_protocol 7 协议 | ✅ 7×11/11 |
| Bandit（src/ server/ main.py） | ✅ 零 HIGH |
| verify_fuzz_flow modbus | ✅ 2/2 PASS（seed=42 确定性，flaky 消除） |
| verify_fuzz_flow s7comm | ✅ PASS |
| registry / menu 导入 / PROTOCOL_CONFIG | ✅ 7 / OK / 7 条无重复 |
| timeout=25 | ✅ 统一收敛至 llm_mutator_base.py:139（重构后单点设置） |
| HTML 转义冒烟 | ✅ `<script>` → `&lt;script&gt;` 实体输出（_esc 16 处覆盖） |

### 3.2 阶段 7 全面检查（8/8 全绿）

| 项 | 结果 |
|----|------|
| 7.1 既有协议 check_protocol | ✅ |
| 7.2 fuzz_loop 导入 + registry | ✅ |
| 7.3 menu 启动 | ✅ |
| 7.4 slave 脚本发现 | ✅ 7 个，modbus 实测可启动 |
| 7.5 PROTOCOL_CONFIG 条目 | ✅ |
| 7.6 完整 fuzz 流程 + 报告 | ✅ modbus + s7comm |
| 7.7 timeout=25 | ✅ |
| 7.8 无新反模式 | ✅ |

### 3.3 最低要求 9 条（全部达成）

✅ 主流程跑通 / 无明文 Key 落盘（DPAPI）/ 云端强制 HTTPS / 无 eval·exec·pickle·os.system / Bandit 零 HIGH / requirements 固定版本 / s7comm 15 码 / server recv 超时 6/6 / modbus strict 生效

---

## 4. 六维度评分变化

| 维度 | 审计前 | 第 4 轮 | 第 6 轮（当前） | 主要提升 |
|------|--------|---------|-----------------|----------|
| 正确性 | 6 | 9 | 9 | 6 协议 mutator 偏移全修正、result_analyzer 分发、白名单对齐、LLM 变异长度校验 |
| 安全性 | 5 | 9 | 9 | security 五函数接线闭环、shell 注入消除、HTML 全量转义（16 处）、日志双锁 |
| 健壮性 | 7 | 8 | 9 | server 超时、stop_event 协作退出、None 防护、异常分级上报 |
| 性能 | 7 | 7 | 8 | timeout=25 单点收敛、SDK max_retries=0 消除重试风暴 |
| 可维护性 | 7 | 8 | 9 | llm_mutator 基类化（-80% 复制粘贴）、死代码清理、签名统一 |
| 一致性 | 6 | 8 | 9 | 转义策略统一 _esc、max_retries/JSON/requirements 对齐、verify 确定性 |

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

**建议**：将 O-T 六条正式并入《IndusFuzz 协议扩展 PRD》反模式清单（现有 A-N 之后）。

---

## 6. 发布后 Backlog（不阻塞，按优先级迭代）

| 优先级 | 项 | 说明 |
|--------|-----|------|
| ~~P3~~ | ~~fuzz_loop_llm.py 冗余哑调用~~ | ✅ 第 5 批重构已清理（真实调用移至 report_generator:696） |
| ~~P3~~ | ~~残留线程协作停止~~ | ✅ 第 5 批已落地 stop_event 协作退出（fuzz_loop_llm.py:228） |
| ~~技术~~ | ~~7 份 llm_mutator 复制粘贴~~ | ✅ 第 5 批基类化完成（llm_mutator_base.py + 7 薄壳，-80%） |
| P3 | 反模式 K 收尾 | iec104/iec61850/enip/opcua 循环变量统一 func_code（下个协议扩展前完成） |
| P3 | 待人工确认 4 项写入 README | opcua 帧构造口径（P2-006）、s7comm 10102 仿真器口径（P2-011）、TCP 分片拼包（P2-016）、MCP 桩状态（P2-017）——R5-7 主流程集成已记 README（v1.8.0） |
| P3 | llm_mutator_base 残留小项 | 死参数分支（modbus target_func_code prompt 分支）、错误码子串匹配可误判（"1429"）——均为提示级 |
| 里程碑 | P1-M5 EXE 打包 | requirements 已就绪，可启动 |
| 里程碑 | P0-M3 MCP 集成 | VulnClaw/CodeGuard/CodeInspectus 仍为桩 |

---

## 7. 后续维护回归规则（强制）

任何代码变更（新协议扩展、bug 修复、依赖升级）合入前必须通过：

1. **阶段 7 全面检查 8 项**（协议扩展 PRD）：check_protocol 全过 / registry / menu / slave 脚本 / PROTOCOL_CONFIG / 完整 fuzz（`verify_fuzz_flow --protocol <改动协议>` + s7comm 基线）/ timeout=25 / 反模式扫描
2. **安全基线回归 5 项**（审计 PRD 5.12）：server 绑 127.0.0.1、无硬编码 Key、llm_mutator timeout=25、无危险调用、menu/fuzz_loop 无 elif 膨胀
3. **Bandit**：`bandit -r src/ server/ main.py -lll -q` 零输出
4. **随机路径验证**：涉及随机逻辑的修复连续跑 ≥5 次（反模式 P）
5. **加密链路回归**（涉及 security/config 时）：配置→保存→重启→复用"上次选择"→fuzz 全链路无 401（反模式 Q）
6. **测试环境**：统一使用 agentscope_env venv（系统 Python 缺 scapy 会误报 modbus FAIL）

---

## 8. 结论

- 6 轮审计共发现 **57+ 项问题**（首轮 39 项 + 复审新增 11 项 + 重构审计 7 项），全部闭环
- 5 次返工揭出 **2 次假修复、1 次自毁链、1 次 flaky 验证、1 次转义遗漏复发**——均由"审计方亲自实测"拦截，验证了审计 PRD"不信任声明、只信任证据"的流程价值
- 第 5 批重构（基类化 + 色彩输出 + stop_event）在消除三项技术债的同时保持安全基线零回退，重构审计流程（定向审计 + 阶段 7 回归）验证有效
- 最终状态：**零 P0/P1/P2 遗留，最低要求 9/9，阶段 7 连续 3 轮全绿，Bandit 零 HIGH → 放行发布（第 6 轮复核后维持）**
