Fuzz Agent for Industrial Protocols · 审计 PRD v2.5
一、文档信息
项目	内容
产品名称	Fuzz Agent for Industrial Protocols（工业协议模糊测试智能体）
当前版本	v1.0（架构已重构至 v1.6.x，五协议接入完毕）
目标版本	v1.5（EXE + 真实 PLC + 全面审计 + MCP 工具链）→ v2.0（开源）
文档状态	整合稿，漏洞矩阵已完整覆盖，上线门禁已整合
更新日期	2026-09-16（v2.5 整合上线 8 大门禁 + 最终检查流程 + 不通过处理）


---

### 审计检查维度（每个模块都要过一遍）

| 维度 | 关注点 | 关联最低要求 |
|------|--------|-------------|
| 正确性 | 逻辑是否符合预期、边界条件是否处理 | 能跑通 |
| 安全性 | 是否引入攻击面、是否泄露敏感信息 | 无明文 Key / HTTPS 强制 |
| 健壮性 | 异常是否被捕获、是否会崩溃 | 最低要求 1 |
| 性能 | 是否有明显瓶颈（阻塞、重复请求） | 预期要求 8 |
| 可维护性 | 是否容易扩展新协议/新模型 | 协议可扩展 |
| 一致性 | 命名、日志前缀、错误提示是否统一 | 预期要求 1 |


## 审计角色

你是一名资深工业控制系统安全专家 + Python 代码审计专家，同时具备 ICS/SCADA 协议实现经验（Modbus、S7Comm、DNP3、IEC 104/61850、EtherNet/IP、OPC UA）和云端 API 集成经验。

**审计时的行为守则**：
- 逐文件通读，不依赖 IDE 提示
- 逐函数验证签名、参数、返回值、异常处理
- 跨文件追踪关键调用链（main → menu → slave_launcher → fuzz_loop → protocol.run_fuzz → report）
- 模拟运行路径，找出未处理的边界
- 不确定的地方明确标注「需人工确认」，不要猜测

战略定位	学术验证后的工程化开源实现
二、背景与战略定位
2.1 学术背景
2026 年 5 月，MALF 框架在《Sensors》期刊发表，验证了“多智能体 LLM 驱动工业协议模糊测试”的可行性，在 Modbus/TCP 上实现 88.3% 的测试用例通过率。

2.2 AI 生成代码的安全背景
本项目 95% 以上的代码由 AI 辅助生成。根据 Veracode 2026 年报告，45% 的 AI 生成代码会引入 OWASP Top 10 级别的漏洞。Georgia Tech 的 Vibe Security Radar 确认了 74 个 AI 关联 CVE，其中 14 个严重、25 个高危，包括命令注入、认证绕过、SSRF。

关键发现：约 19.7% 的 AI 建议依赖项（Python 和 JavaScript）是不存在的名称，攻击者可将其注册为恶意包。75% 以上的开发者错误地认为 AI 生成代码比人类写的更安全，但 56% 承认它经常引入安全问题。

2.3 外部工具链集成背景
当前项目缺少两类能力：自动化安全审计（依赖手动运行 Bandit/Semgrep）和真实渗透测试（缺少信息收集、漏洞利用、PoC 生成链路）。

解决方案：通过 MCP 协议集成 VulnClaw、CodeGuard、CodeInspectus，形成“编码 → 审计 → 渗透 → 报告”闭环。

三、目录结构（v1.6.x 架构重构后）
```
fuzz_agent/
├── src/
│   ├── protocols/
│   │   ├── base.py                          # ProtocolBase 抽象基类
│   │   ├── registry.py                     # register_protocol() + auto_load_builtin()
│   │   ├── modbus/{client, mutator, llm_mutator, __init__}.py
│   │   ├── s7comm/{client, mutator, llm_mutator, __init__}.py
│   │   ├── dnp3/{client, mutator, llm_mutator, __init__}.py
│   │   ├── iec104/{client, mutator, llm_mutator, __init__}.py
│   │   ├── iec61850/{client, mutator, llm_mutator, __init__}.py
│   │   └── func_codes/                      # *_func_codes.json（自动扫描）
│   ├── core/
│   │   ├── fuzz_loop_llm.py                 # run() 调度器（if-elif 已删除，用 get_protocol().run_fuzz()）
│   │   ├── report_generator.py              # PROTOCOL_CONFIG 集中配置
│   │   ├── menu.py                          # 自动扫描 func_codes/*.json
│   │   └── slave_launcher.py                # 按 server/<name>_server.py 约定路径自动查找
│   └── integrations/                        # MCP 工具链（待集成）
├── server/                                  # *_server.py 支持 --port --strict
├── tools/
│   └── check_protocol.py                    # 协议自检工具（11 项检查）
├── reports/
├── config/
├── docs/
├── main.py
└── requirements.txt
```
四、功能需求
4.1 P0-M1：目录结构重构（第1周）
Agent 任务： 将现有文件迁移到新目录结构，更新所有导入路径。

原文件	新位置
modbus_client.py	src/protocols/modbus/client.py
modbus_tools.py	src/protocols/modbus/tools.py
mutator.py	src/protocols/modbus/mutator.py
llm_mutator.py	src/protocols/modbus/llm_mutator.py
result_analyzer.py	src/core/analyzer.py
report_generator.py	src/core/reporter.py
fuzz_loop_llm.py	src/core/runner.py
modbus_server.py	server/modbus_server.py
验收标准：

□ 运行 python main.py 可跑通完整流程
□ 无 ModuleNotFoundError
□ 边界条件满足安全
4.2 P0-M2：代码安全审计（第1-2周）
本项目代码 95% 由 AI 生成，审计必须覆盖以下完整漏洞矩阵。

4.2.1 完整漏洞矩阵
Agent 请逐项检查以下所有漏洞类型：

A01:2025 — 访问控制失效（Broken Access Control） 

编号	检查项	检查方法	通过标准
AC-01	SSRF（服务端请求伪造）	Semgrep + 人工	零发现
AC-02	IDOR（不安全的直接对象引用）	人工审计	零发现
AC-03	权限提升（水平/垂直）	人工审计	零发现
AC-04	强制浏览（forced browsing）	人工审计	零发现
AC-05	认证绕过	Semgrep + 人工	零发现
AC-06	授权缺失（登录做了但未检查权限）	人工审计	零发现
AC-07	信任客户端提供的权限参数	Semgrep	零发现
AC-08	默认权限过于宽泛	人工审计	零发现
SSRF 专项检查要点（参考 OWASP A10 SSRF Cheat Sheet）：

□ 所有接受 URL 参数的函数是否限制了请求范围（白名单）？
□ 是否限制了请求协议（仅允许 http/https，禁止 file://、gopher://、ftp://）？
□ 是否屏蔽了内网 IP 和云元数据端点（169.254.169.254）？
□ 所有 requests.get()、urlopen()、socket.connect() 的 URL 参数是否用户可控？
□ 项目中的 VulnClaw/CodeGuard 集成是否对目标地址做了白名单校验？
本项目特有风险：src/integrations/vulnclaw_mcp.py 中 run_vulnclaw_scan(target) 的 target 参数如果来自用户输入，存在 SSRF 风险。必须限制目标为授权范围内的地址。

A02:2025 — 安全配置错误

编号	检查项	检查方法	通过标准
CF-01	硬编码密钥/密码/API Key	Bandit + Gitleaks	零发现
CF-02	开放 CORS 配置	Semgrep	零发现
CF-03	调试模式未关闭	人工审计	零发现
CF-04	默认凭证	人工审计	零发现
CF-05	客户端密钥暴露（API Key 出现在前端代码中）	Semgrep	零发现
AI 生成代码特有：14% 的 AI 生成项目存在硬编码凭证。

A03:2025 — 软件供应链失效 

编号	检查项	检查方法	通过标准
SC-01	Slopsquatting（幻觉包名）	pip-audit + PyPI 核实	零幻觉包名
SC-02	依赖版本未固定	人工检查	100% 固定
SC-03	依赖混淆（私有包名与公共包冲突）	人工审计	零发现
SC-04	依赖存在已知 CVE	pip-audit	零 HIGH
关键数据：约 19.7% 的 AI 建议依赖项是不存在的名称。

A04:2025 — 加密机制失效

编号	检查项	检查方法	通过标准
CR-01	弱加密算法（MD5/SHA1）	Semgrep	零发现
CR-02	硬编码 IV/密钥	Semgrep	零发现
CR-03	明文传输敏感数据	人工审计	零发现
CR-04	不安全的随机数生成	Semgrep	零发现
A05:2025 — 注入 

编号	检查项	检查方法	通过标准
IN-01	SQL 注入	Semgrep + Bandit	零发现
IN-02	命令注入	Semgrep + Bandit	零发现
IN-03	XSS（跨站脚本）	Semgrep	零发现
IN-04	URL 注入 / GET 参数注入	Semgrep + 人工	零发现
IN-05	POST 参数注入	Semgrep + 人工	零发现
IN-06	HTTP 头注入（UA/Referer/XFF）	人工审计	零发现
IN-07	日志注入	Semgrep	零发现
IN-08	路径遍历	Semgrep	零发现
IN-09	模板注入	Semgrep	零发现
IN-10	XML/XXE 注入	Semgrep	零发现
URL 参数注入专项检查（参考 VulnClaw 注入检测指南）：

□ 所有从 URL 获取的参数（request.args）是否做了类型和长度校验？
□ 是否存在动态拼接 SQL 的代码路径？
□ 搜索框、排序参数、分页参数是否做了白名单限制？
高频参数名：id, sort_id, username, password, type, action, page, name。

A06:2025 — 不安全设计

编号	检查项	检查方法	通过标准
DS-01	缺少速率限制	人工审计	确认
DS-02	无限重试逻辑	人工审计	零发现
DS-03	业务逻辑漏洞	人工审计	零发现
A07:2025 — 认证失败

编号	检查项	检查方法	通过标准
AU-01	弱密码策略	人工审计	确认
AU-02	会话固定	人工审计	零发现
AU-03	缺少多因素认证	人工审计	记录
AU-04	认证逻辑错误（如 fail-open）	人工审计	零发现
本项目特有风险：AI 生成代码中最常见的严重类是 API 授权逻辑失败。

A08:2025 — 数据完整性失败

编号	检查项	检查方法	通过标准
DI-01	不安全反序列化	Bandit	零发现
DI-02	未验证的软件更新	人工审计	确认
DI-03	CI/CD 管道注入	人工审计	零发现
A09:2025 — 日志与告警失败

编号	检查项	检查方法	通过标准
LG-01	敏感信息写入日志	Semgrep	零发现
LG-02	关键事件未记录	人工审计	确认
LG-03	日志注入	Semgrep	零发现
A10:2025 — 异常条件处理不当

编号	检查项	检查方法	通过标准
EX-01	未捕获异常泄露堆栈	Semgrep + 人工	零发现
EX-02	静默吞掉授权失败	人工审计	零发现
EX-03	错误信息泄露内部路径	人工审计	零发现
EX-04	异步操作无错误处理	Semgrep	零发现
AI 生成代码特有：79% 的 AI 生成项目存在“异步操作无错误处理”的高危发现。

4.2.2 LLM/智能体特有风险（OWASP LLM Top 10 2026）
编号	风险	检查项	检查方法
LLM-01	提示注入	LLM 输出是否直接执行而未清洗	检查 llm_mutator.py
LLM-02	敏感信息泄露	日志中是否输出完整报文或凭证	检查 runner.py
LLM-03	过度代理权	智能体是否拥有文件系统/网络全部权限	检查 Ollama 调用
LLM-04	供应链	LLM 相关依赖是否存在已知 CVE	pip-audit
LLM-05	数据与模型投毒	训练数据是否可被篡改	人工审计
LLM-06	无界消耗	是否有 token 数限制、超时、重试上限	检查 llm_mutator.py
LLM-07	错误信息	LLM 是否返回虚假漏洞信息	人工审计
LLM-08	隐藏上下文暴露	系统提示词是否可被读取	人工审计
LLM-09	向量与嵌入弱点	向量数据库是否安全	人工审计
LLM-10	不当输出处理	bytes.fromhex() 前是否有校验	检查代码
关键变化：过度代理权从第 6 位升至第 3 位，无界消耗从第 10 位升至第 6 位，反映了智能体部署中风险的实际落地。

4.2.3 审计工具组合
bash
pip install bandit semgrep pip-audit

# 1. Bandit（Python 专用 SAST）
bandit -r src/ core/ -f json -o reports/bandit_report.json

# 2. Semgrep（自定义规则）
semgrep --config=auto src/ core/

# 3. pip-audit（依赖 CVE 检查）
pip-audit -r requirements.txt

# 4. Gitleaks（密钥检测）
gitleaks detect --source . --report-path reports/gitleaks_report.json
审计检查清单（最终版）：

□ SSRF 检查完成，零发现
□ 授权缺失检查完成，零发现
□ URL 参数注入检查完成，零发现
□ XSS 检查完成，零发现
□ 客户端密钥暴露检查完成，零发现
□ 路径遍历检查完成，零发现
□ 覆盖 OWASP Top 10 2025 全部 10 个类别
□ 覆盖 OWASP LLM Top 10 2026 全部 10 个风险
□ Bandit 无 HIGH 级别问题
□ pip-audit 无 HIGH 级别 CVE
□ 无硬编码密钥/IP/端口
□ requirements.txt 中所有包名真实存在
□ 所有网络输入有边界检查
□ 无 eval() / exec() / pickle.loads()
□ LLM 输出做了正则清洗和长度校验
4.3 P0-M3：MCP 工具链集成（第2周）
4.3.1 集成 VulnClaw
bash
pip install vulnclaw
vulnclaw config provider ollama
新增 src/integrations/vulnclaw_mcp.py：

python
import subprocess

AUTHORIZED_TARGETS = ["127.0.0.1", "localhost", "192.168.1.0/24"]

def _validate_target(target: str) -> bool:
    """白名单校验，防止 SSRF"""
    import ipaddress
    try:
        ip = ipaddress.ip_address(target.split(":")[0])
        return any(ip in ipaddress.ip_network(net) for net in AUTHORIZED_TARGETS if "/" in net)
    except ValueError:
        return target in ["127.0.0.1", "localhost"]

def run_vulnclaw_scan(target: str) -> str:
    if not _validate_target(target):
        raise ValueError(f"目标 {target} 不在授权范围内，禁止扫描")
    result = subprocess.run(
        ["vulnclaw", "solve", f"对 {target} 进行渗透测试"],
        capture_output=True, text=True, timeout=600
    )
    return result.stdout
4.3.2 集成 CodeGuard MCP
bash
npx -y @mlawsonking/code-guard-mcp
4.3.3 集成 CodeInspectus MCP
bash
npx codeinspectus install-engines
npx -y codeinspectus
验收标准：

□ VulnClaw 能对授权目标执行渗透测试
□ CodeGuard 能扫描项目代码
□ CodeInspectus 能执行深度审计
□ 所有 MCP 工具调用有超时和错误处理
4.4 P1-M4：真实 PLC 支持（第2周）
python
import snap7

class S7CommClient:
    def __init__(self, ip, rack=0, slot=1):
        self.client = snap7.client.Client()
        self.ip = ip
        self.rack = rack
        self.slot = slot

    def connect(self):
        self.client.connect(self.ip, self.rack, self.slot)

    def disconnect(self):
        self.client.disconnect()
4.5 P0-M5：EXE 打包（第2周）
bash
pyinstaller --onefile --name ModbusFuzzer modbus_fuzzer.spec
4.6 P1-M6：多协议扩展（第3-4周）
S7Comm + DNP3 完整模糊测试支持。

4.7 P2-M7：MCP Server 接口（第5周）
让 Cursor/Trae 能调用本工具。

4.8 P2-M8：开源发布（第6周）
README + 演示视频 + GitHub + 技术文章。


---

### 6.x 代码质量与优化（功能性 + 可维护性，归审计 PRD 是因为质量差本身就是安全温床）

| # | 检查项 | 怎么查 | 关联反模式 |
|---|--------|--------|-----------|
| 1 | 重复代码（多个 `_run_xxx` 相同逻辑） | diff 7 个 mutator / llm_mutator 的结构 | — |
| 2 | 死代码（未引用 import、未调用函数） | IDE 静态分析 + rg 引用链 | — |
| 3 | 函数过长（>100 行） | `awk '/^def /{fn=$0} {c[fn]+=1} END{for(k in c) print c[k],k}' src/**/*.py` | — |
| 4 | 嵌套过深（>4 层） | 看最复杂函数缩进 | — |
| 5 | Magic number（硬编码端口/超时/长度） | 检查是否有 `DEFAULT_PORT` / `DEFAULT_TIMEOUT` 常量 | — |
| 6 | 重库未延迟导入（scapy、torch、asyncua） | 函数内 import 还是文件顶部 | — |
| 7 | 未使用变量 | IDE 静态分析 | — |

五、上线前最低协议
本章节定义 IndusFuzz 上线发布前必须通过的 8 大门禁，覆盖功能完整性、安全性、AI 生成代码特有风险、LLM/智能体风险、ICS 合规、工程化易用性、开源发布、文档支持。所有门禁必须全通过方可发布。

### 5.1 功能完整性门禁（必须全通过）
编号	检查项	通过标准
FUNC-01	多协议覆盖	至少支持 Modbus TCP + S7comm + DNP3 + IEC104 + IEC61850 五种协议
FUNC-02	功能码完整	每个协议的功能码定义与协议规范一致，无遗漏（DNP3 31 个请求码、IEC104 33 个 TypeID、IEC61850 17 个 MMS PDU 等）
FUNC-03	LLM 变异可用	本地 Ollama 和云端 API 两条路径都能正常生成变异（超时/限流/网络不通时有降级）
FUNC-04	报告生成完整	HTML 报告正常输出，风险分级正确（CRITICAL/HIGH/MEDIUM/LOW）
FUNC-05	交互菜单正常	协议选择、功能码选择、目标地址输入全流程可用
FUNC-06	模拟从站可用	每个协议的模拟从站能正常启动，--strict 模式能产生异常响应
FUNC-07	自检工具通过	python tools/check_protocol.py <name> 对所有已支持协议全部 [OK]
FUNC-08	协议扩展架构稳定	新增协议无需修改任何核心文件（fuzz_loop_llm.py / menu.py / slave_launcher.py / report_generator.py 配置以外）

### 5.2 安全性门禁（必须全通过）
参考 OWASP ASVS 5.0 Level 1 和 OWASP Top 10 2025。模糊测试工具自身的安全性至关重要，根据 GitHub 2024 年报告，采用持续模糊测试的项目漏洞密度降低达 67%，但前提是工具本身没有漏洞。

编号	检查项	检查方法	通过标准
SEC-01	无硬编码密钥/密码/IP/API Key	Bandit + Gitleaks	零发现
SEC-02	API Key 使用 DPAPI 加密存储	检查 config.json api_key 是否为 base64(DpAPI加密值)	零明文 api_key
SEC-03	API Key 只绑定当前 Windows 用户账户	验证 win32crypt.CryptProtectData 使用了当前用户上下文	确认
SEC-04	所有云端 API URL 强制 HTTPS	menu.py _validate_cloud_url() + 人工审计	零 http:// 云端 URL
SEC-05	日志/终端中 API Key 打码显示	menu.py + llm_mutator.py 检查 mask_key() 调用	零完整 key 输出
SEC-06	无 eval() / exec() / pickle.loads()	Bandit	零发现
SEC-07	所有 socket 使用 with 或 try/finally	Semgrep + 人工	100% 覆盖
SEC-08	所有网络输入有边界检查	Semgrep + 人工	100% 覆盖
SEC-09	SSRF 防护	检查 VulnClaw 集成的目标白名单	零发现
SEC-10	授权缺失检查	人工审计所有 API 端点	零发现
SEC-11	URL 参数注入检查	Semgrep + 人工	零发现
SEC-12	异常处理不泄露堆栈/路径	Semgrep + 人工	零发现
SEC-13	日志中不输出敏感信息	人工审计	零发现
SEC-14	Bandit 无 HIGH 级别问题	报告确认	零 HIGH
SEC-15	pip-audit 无 HIGH 级别 CVE	报告确认	零 HIGH

### 5.3 AI 生成代码特有门禁（必须全通过）
参考 Veracode 2026 报告和 vibe-check 清单。本项目代码 95% 由 AI 生成，已知 45% 的 AI 生成代码会引入 OWASP Top 10 级别的漏洞。

编号	检查项	检查方法	通过标准
AI-01	requirements.txt 所有包名真实存在	pip-audit + PyPI 核实	零幻觉包名
AI-02	所有依赖版本已固定	人工检查	100% 固定
AI-03	无开放 CORS 配置	Semgrep	零发现
AI-04	无客户端密钥暴露	Semgrep	零发现
AI-05	无异步操作无错误处理	Semgrep	零发现

### 5.4 LLM/智能体特有门禁（必须全通过）
参考 OWASP LLM Top 10 2026。2026 版排名中，提示注入保持第 1 位，过度代理权从第 6 位升至第 3 位，无界消耗从第 10 位升至第 6 位。

编号	检查项	检查方法	通过标准
LLM-01	LLM 输出做了正则清洗和长度校验	检查 llm_mutator.py 中 _clean_line() 函数	100% 覆盖
LLM-02	Ollama 调用有超时和重试上限	检查 llm_mutator.py 中 max_retries 参数	确认
LLM-03	重试次数有限制（默认 3 次）	检查 llm_generate_mutations 的 max_retries=3	确认
LLM-04	bytes.fromhex() 前有格式校验	检查 client.py run_fuzz 中 try/except ValueError	100% 覆盖
LLM-05	日志中不输出完整报文或凭证	人工审计 print/logger 语句	零发现

### 5.5 工业协议测试工具合规门禁（必须全通过）
参考 GB/T 25919.3-2026 和 IEC 62443。S7comm 测试有明确的授权要求：切勿在未授权的生产 PLC 上扫描，否则可能导致控制器崩溃。DNP3 协议在设计时优先考虑可靠性而非安全性，通过 IP 网络暴露的攻击面远大于串行链路。

编号	检查项	检查方法	通过标准
ICS-01	测试工具不影响被测设备正常运行	文档说明 + 模拟环境测试确认	确认
ICS-02	工具自身安全加固（socket 超时、异常处理）	代码审计	确认
ICS-03	提供未授权测试的法律声明	README + 启动时免责声明	确认
ICS-04	支持 Modbus TCP 安全协议一致性测试	功能验证	确认
ICS-05	通信健壮性验证（重试、超时、连接关闭处理）	测试覆盖	确认
ICS-06	DNP3 / IEC104 / IEC61850 支持多层报文变异测试	功能验证	确认

### 5.6 工程化与易用性门禁（必须全通过）
编号	检查项	通过标准
ENG-01	EXE 在 Windows 10/11 可运行	双击启动，无需装 Python
ENG-02	EXE 体积 ≤ 100 MB	确认
ENG-03	冷启动 ≤ 10 秒	确认
ENG-04	一键启动脚本可用	start_fuzz.bat 测试确认
ENG-05	首次运行配置向导正常	模型选择、目标地址输入全流程可用
ENG-06	断网环境下能正常启动（本地 Ollama 路径）	测试确认
ENG-07	普通用户身份运行无越权（端口 ≥ 1024 默认）	测试确认

### 5.7 开源发布门禁（必须全通过）
参考 OpenSSF OSPS Baseline Level 1。

编号	检查项	通过标准
OSS-01	README 完整（中英双语）	人工检查
OSS-02	无提交的密钥/凭证	Gitleaks 扫描零发现
OSS-03	主分支有保护机制	GitHub 配置确认
OSS-04	敏感资源需 MFA 认证	GitHub 配置确认
OSS-05	项目已完成安全评估	审计报告确认

### 5.8 文档与支持门禁（必须全通过）
编号	检查项	通过标准
DOC-01	用户手册完整	安装、配置、使用步骤清晰
DOC-02	协议扩展指南完整	新增协议 11 步流程文档齐全（见协议扩展 PRD 十八章）
DOC-03	常见问题解答	覆盖菜单不显示、端口占用、报告功能码 Unknown 等（见协议扩展 PRD Q1-Q8）
DOC-04	漏洞数据库比对说明	明确 CNVD/CVE 暂不支持的原因和替代方案
DOC-05	免责声明	README 和使用须知中包含未授权测试的法律声明

### 5.9 上线前最终检查流程
```
第一步：运行自动化扫描（Bandit + Semgrep + pip-audit + Gitleaks）
        → 所有 HIGH 级别问题必须修复
        ↓
第二步：运行协议自检（tools/check_protocol.py 对所有已支持协议）
        → 全部 [OK]，无 [FAIL]
        ↓
第三步：运行 AI 深度审计（本地 Qwen）
        → 重点检查 SSRF、授权缺失、URL 注入
        ↓
第四步：人工复核
        → 重点复核与真实 PLC 交互的代码路径
        → 重点复核 VulnClaw 集成的目标白名单
        ↓
第五步：专项测试
        → 断网启动、普通用户运行、模拟环境全流程
        ↓
第六步：填写门禁清单
        → 所有项打勾，签字确认
        ↓
第七步：发布
```

### 5.10 门禁不通过的处理
情况	处理方式
发现 HIGH 级别漏洞	必须修复后重新审计
发现 MEDIUM 级别漏洞	可接受但需记录，下个版本修复
发现 LOW 级别漏洞	记录即可
无法修复的高危项	需写正式的接受理由文档，并经复核确认

### 5.11 API Key 加密存储与传输最低要求
IndusFuzz 是 Windows 桌面 EXE，支持云端 API。API Key 一旦泄露，攻击者可直接消耗配额、冒充身份调用 API。以下为按优先级排序的最低安全要求。

**🔴 必须做到的（最低要求）**

1. **禁止硬编码在源码里**
   - 用户首次运行程序时，通过菜单输入 API Key
   - 程序只保存在用户本地配置里（见第 2 条）
   - 源码里永远不出现任何真实 key
   - 反编译风险：PyInstaller 打的 EXE 用 pyinstxtractor 可轻松解出 .pyc，.pyc 再用 uncompyle6 还原大部分源码。如果源码里写了 `default_api_key = "sk-xxx"`，反编译后直接可见

2. **存储时加密，使用 Windows DPAPI**
   - **当前状态**：config.json 里 api_key **明文存储**，任何人打开文件即可看到
   - 最低要求：用 Windows 自带的 DPAPI 加密（不需要额外依赖）
   - 代码位置：src/core/menu.py 写入配置时调用 encrypt_key()，src/protocols/*/llm_mutator.py 读取时调用 decrypt_key()

   ```python
   # src/core/security.py（新增模块）
   import win32crypt, base64
   
   def encrypt_key(plaintext: str) -> str:
       encrypted = win32crypt.CryptProtectData(
           plaintext.encode("utf-8"), "IndusFuzz API Key",
           None, None, None, 0)
       return base64.b64encode(encrypted).decode("ascii")
   
   def decrypt_key(ciphertext: str) -> str:
       encrypted = base64.b64decode(ciphertext)
       _, decrypted = win32crypt.CryptUnprotectData(
           encrypted, None, None, None, 0)
       return decrypted.decode("utf-8")
   
   def mask_key(key: str) -> str:
       if not key or len(key) < 8:
           return "***"
       return key[:4] + "*" * (len(key) - 8) + key[-4:]
   
   def is_encrypted(candidate: str) -> bool:
       try:
           base64.b64decode(candidate)
           win32crypt.CryptUnprotectData(base64.b64decode(candidate), None, None, None, 0)
           return True
       except Exception:
           return False
   
   def _store_api_key(cfg: dict, api_key: str) -> dict:
       if api_key.startswith("ollama") or api_key.startswith("local"):
           cfg["api_key"] = api_key  # 本地 provider 不需要 DPAPI
       else:
           cfg["api_key"] = encrypt_key(api_key)
       return cfg
   
   def _get_api_key(cfg: dict) -> str:
       raw = cfg.get("api_key", "")
       if not raw:
           return ""
       if raw in ("ollama", "local"):
           return raw
       if is_encrypted(raw):
           return decrypt_key(raw)
       return raw  # 明文兼容（首次启动时自动升级）
   ```
   
   - DPAPI 特点：加密密钥绑定当前 Windows 用户账户；即使别人拷贝 config.json 到另一台电脑也解不开
   - 依赖：`pip install pywin32`（Windows 自带底层实现，当前环境已安装）
   - 跨平台备选：如果将来支持 Linux/Mac，用 `keyring` 库存系统凭据管理器

3. **日志和终端输出必须打码**
   - 当前状态：menu.py L351/L414 已做 `'*' * min(len(api_key), 8)`，但实现不够标准
   - 最低要求：任何地方要显示 key 都必须经过 `security.mask_key()` 函数
   - 额外检查：openai 库开 debug 模式会打印完整 Authorization 请求头——必须关闭；异常信息里的完整 URL 不能原样打印

4. **EXE 打包时不带 .env 或测试 key**
   - 打包前用 grep 搜索 sk-、api_key =、Bearer，确认没有真实 key
   - .env 文件不要打包进 EXE
   - .gitignore 里加上 .env、config.json、*.key

5. **传输必须 HTTPS**
   - 最低要求：所有云端 API 地址必须以 `https://` 开头
   - 在 menu.py 里加校验：

   ```python
   # src/core/security.py
   def validate_cloud_url(url: str) -> tuple[bool, str]:
       if not url.startswith("https://"):
           return False, "API 地址必须使用 HTTPS，否则 API Key 会在网络上明文传输"
       return True, None
   ```
   
   - 强制 HTTPS：cloud / custom 类型必须校验，ollama 本地可例外（http://localhost:11434）

6. **最小权限原则**
   - 创建专用 key，只用于 IndusFuzz，不要和其他项目共用
   - 限制 key 的调用额度（比如每天 1000 次），防止被盗后无限消耗
   - 限制 IP 白名单（如果云服务商支持）

7. **定期轮换**
   - 在配置菜单里加"更换 API Key"入口，建议用户每 3 个月更换一次

8. **隐私模式下不写入磁盘**
   - 增加选项：`[5] 云端 API（本次运行有效，不保存 Key）`
   - 选了之后 key 只在内存里存活，程序退出就丢失。适合公共电脑或客户现场

9. **首次使用时的安全提示**
   - 用户第一次选择云端 API 时弹说明：

   ```
   ⚠️  安全提示
   - 你的 API Key 将使用 Windows DPAPI 加密后保存在本机
   - 加密绑定当前 Windows 用户，其他用户/电脑无法解密
   - 请勿在截图或录屏中暴露 API Key
   - 如怀疑 Key 泄露，请立即到云端控制台吊销
   ```

**🔴 绝对不能做的事（红色禁区）**

禁止行为	后果
把 API Key 硬编码在 Python 源码里	EXE 反编译后直接暴露
把 API Key 提交到 Git 仓库	GitHub 上有公开爬虫，几秒内扫到
把 API Key 明文保存在 config.json	任何能读文件的人都能拿走
用 http:// 而非 https:// 调用云端 API	中间人可截获 key
在日志/终端打印完整 key	日志文件被分享时泄露
在截图/录屏中暴露 key	客户群里传开后追不回
云端账号用主账号的 key	泄露后整个账号沦陷

**最核心的两条**：DPAPI 加密存储（防止本地文件泄露）+ 强制 HTTPS（防止网络截获）。做好这两条，99% 场景就安全了。

### 5.12 协议扩展后的安全基线回归（每次加新协议后必做）

> 功能/兼容性回归走「协议扩展 PRD」的**阶段 7：全面检查**（功能性 8 项），
> 本小节只管安全——加了新协议后，安全基线有没有被破坏。
> 不通过 → 不修完不能进主分支。

| # | 检查项 | 怎么查 | 不通过意味着 |
|---|--------|--------|-------------|
| 1 | **新 server.py 默认监听 127.0.0.1** | 在 `server/<new>_server.py` 里搜 `0.0.0.0` — 不应命中 | 暴露到公网，任何人都能连 |
| 2 | **client.py / llm_mutator.py 无硬编码 Key/密码** | `rg -i "sk-[a-z0-9]{10}" src/protocols/<new>/` | 凭据硬编码进仓库，git 历史泄露 |
| 3 | **llm_mutator.py 有 timeout=25** | `grep -c "timeout=25" src/protocols/<new>/llm_mutator.py` → >= 1 | 反模式 M：云端 LLM 调用无限等 |
| 4 | **无 eval/exec/pickle.loads/os.system** | `rg "\beval\(|\bexec\(|pickle\.loads|os\.system" src/protocols/<new>/` | 代码注入风险 |
| 5 | **新协议不出现在 menu/fuzz_loop 的 if-elif** | `rg "elif.*<new>" src/core/` — 不应命中 | 反模式 B：核心代码因新协议膨胀 |

---


---

#
### 审计检查方法（必须全部执行）

1. **逐文件通读**：不依赖 IDE 提示，直接读源码
2. **逐函数验证**：每个函数签名、参数、返回值、异常处理都过一遍
3. **跨文件追踪**：追踪关键调用链（main → menu → slave_launcher → fuzz_loop → protocol.run_fuzz → report）
4. **动态思考**：模拟运行路径，找出未处理的边界
5. **不要猜测**：不确定的地方明确标注「需人工确认」


### 审计约束

1. 只报告真实存在的问题，不要脑补
2. 每个问题必须给出**文件路径 + 行号 + 复现条件**
3. 不要修改代码，只输出审计报告
4. 如果信息不足，明确列出「需要补充的信息」
5. 用中文输出，专业术语保留英文
6. 报告要能直接作为 TODO List 使用



## 审计输出模板

审计报告必须按以下结构输出（可直接作为 TODO List）：

```
## 一、总体评分（6 维度 × 1-10 分）

| 维度 | 得分 | 说明 |
|------|------|------|
| 正确性 | | |
| 安全性 | | |
| 健壮性 | | |
| 性能 | | |
| 可维护性 | | |
| 一致性 | | |

## 二、必须修复（P0 + P1）

| 编号 | 文件 | 行号 | 问题 | 严重程度 | 复现条件 | 修复建议 |
|------|------|------|------|----------|----------|----------|
| P0-001 | | | | | | |

## 三、建议改进（P2）  —  四、优化建议（P3）
（同上表格式）

## 五、最低要求达成情况（7 条全满足？）

| 要求 | 是否满足 | 证据 |
|------|----------|------|
| 能跑通 | | |
| 无明文 Key | | |
| ... | | |

## 六、预期要求达成情况（9 条）
（同上表）

## 七、优先修复顺序
1. 第一周：P0 全部 + P1 全部
2. 第二周：P2 高频项
3. 后续迭代：P3

## 八、附录：逐协议审计结果
对 Modbus TCP / S7Comm / DNP3 / IEC 104 / IEC 61850 / EtherNet/IP / OPC UA 各输出：
| 检查项 | 结果 | 备注 |
|--------|------|------|
| client.py 完整 | | |
| build_request 正确 | | |
| run_fuzz 签名一致 | | |
| mutator 无越界 | | |
| llm_mutator 处理异常 | | |
| llm_mutator timeout=25 | | |
| server --port --strict | | |
| server bind 127.0.0.1 | | |
```

六、非功能需求
类别	要求
性能	单轮 90 次测试 ≤ 5 分钟
兼容性	Windows 10/11 64 位
安全性	审计覆盖 OWASP Top 10 + LLM Top 10，无高危漏洞
隐私	全程本地 LLM，数据不出本机
可交付性	EXE 单文件
七、里程碑计划（v1.6.x 实际进度）
阶段	时间	内容	交付物
P0-M1	已完成	目录结构重构 + 架构重构（if-elif → registry + run_fuzz）	重构后代码库
P0-M2	进行中	安全审计（Bandit/Semgrep/pip-audit/Gitleaks）	审计报告
P0-M3	待开始	MCP 工具链集成（VulnClaw / CodeGuard / CodeInspectus）	integrations/
P1-M4	已完成	多协议扩展（Modbus + S7comm + DNP3 + IEC104 + IEC61850 + EtherNet/IP + OPC UA）	7 协议完整支持
P1-M5	待开始	PyInstaller 打包	IndusFuzz.exe
P1-M6	已完成	协议扩展 PRD 编写 + 反模式 10 个 + 自检工具	docs/IndusFuzz 协议扩展 PRD.md + tools/check_protocol.py
P1-M7	已完成	API Key 安全加固：DPAPI 加密 + HTTPS 强制 + 打码 + 明文自动迁移	src/core/security.py + menu.py 集成 + SEC-02/04/05 落地
P2-M8	待开始	MCP Server 接口	mcp_server.py
P2-M9	待开始	开源发布（OpenSSF OSPS Baseline Level 1）	GitHub + README + 文章
八、风险与对策
风险	影响	对策
AI 生成代码引入 SSRF/授权漏洞	高	专项审计 + MCP 工具自动扫描
Slopsquatting 幻觉包名	高	pip-audit + PyPI 核实
VulnClaw 被恶意利用	高	目标白名单校验
被抢先开源	高	第2周末发布 MVP
九、附录
9.1 已支持协议（7 个，v1.7.x）
协议	端口	请求功能码数	响应码数	默认是否启用
Modbus TCP	502	8	4	是
S7comm	102	15	—	是
DNP3	20000	31	2	是
IEC 60870-5-104	2404	33	0	是
IEC 61850 MMS	102	17	20	是
EtherNet/IP	44818	27	—	是
OPC UA	4840	28	—	是

9.2 各协议功能码数量 vs func_name_map 数量
协议	func_codes JSON（请求）	client.py func_name_map（请求+响应）	report_generator func_name_map
Modbus TCP	8	8	8
S7comm	15	15	15
DNP3	31	33	33
IEC 60870-5-104	33	66	66
IEC 61850 MMS	17	37	37
EtherNet/IP	27	27	27
OPC UA	28	28	28

9.3 技术栈
语言：Python 3.12

网络：Scapy、socket、python-snap7

LLM：Ollama + qwen2.5-coder:14b

报告：HTML + 内联 CSS

打包：PyInstaller

MCP 工具：VulnClaw、CodeGuard、CodeInspectus

9.3 参考标准
OWASP Top 10 2025

OWASP LLM Top 10 2026

OWASP ASVS 5.0

OpenSSF OSPS Baseline

GB/T 25919.3-2026

Veracode 2026 GenAI 代码安全报告

Georgia Tech Vibe Security Radar