Fuzz Agent for Industrial Protocols · 审计 PRD v2.5
一、文档信息
项目	内容
产品名称	Fuzz Agent for Industrial Protocols（工业协议模糊测试智能体）
当前版本	v1.8.x（架构已重构至「LLM 驱动变异 + 本地确定性回退」，七协议接入完毕）
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

三、目录结构（v1.7.x 架构重构后）
```
fuzz_agent/
├── src/
│   ├── protocols/
│   │   ├── base.py                          # ProtocolBase 抽象基类
│   │   ├── registry.py                      # register_protocol() + auto_load_builtin()
│   │   ├── llm_mutator_base.py              # LLM 变异基类（timeout/retry/错误分类/长度校验/None 防护）
│   │   ├── func_codes/                      # *_func_codes.json（自动扫描，7 个协议）
│   │   ├── modbus/{client, modbus_tools, mutator, llm_mutator, __init__}.py
│   │   ├── s7comm/{client, mutator, llm_mutator, __init__}.py
│   │   ├── dnp3/{client, mutator, llm_mutator, __init__}.py
│   │   ├── iec104/{client, mutator, llm_mutator, __init__}.py
│   │   ├── iec61850/{client, mutator, llm_mutator, __init__}.py
│   │   ├── enip/{client, mutator, llm_mutator, __init__}.py
│   │   └── opcua/{client, mutator, llm_mutator, __init__}.py
│   ├── core/
│   │   ├── fuzz_loop_llm.py                 # run() 调度器（if-elif 已删除，超时熔断）
│   │   ├── report_generator.py              # PROTOCOL_CONFIG 集中配置，HTML/PDF/LOG 报告
│   │   ├── menu.py                          # 自动扫描 func_codes/*.json
│   │   ├── slave_launcher.py                # 按 server/<name>_server.py 约定路径自动查找
│   │   ├── security.py                      # DPAPI 加密 API Key + HTTPS 强制 + 打码
│   │   ├── llm_precheck.py                  # LLM 连通性预检 + 端口连通性检查
│   │   ├── llm_status.py                    # 每协议 LLM 调用状态收集
│   │   ├── result_analyzer.py               # 结果统计分析
│   │   ├── diagnose.py                      # 连通性诊断
│   │   ├── runtime_config.py                # 全局运行时开关（如 GPU）
│   │   ├── gpu_detector.py                  # GPU 检测
│   │   ├── color_output.py                  # ANSI 彩色输出（Windows VT 降级）
│   │   └── version.py                       # 版本号唯一来源
│   └── integrations/                        # MCP 工具链（桩文件：vulnclaw/codeguard/codeinspectus）
├── server/                                  # 7 个 *_server.py，支持 --port --strict
├── tools/
│   ├── check_protocol.py                    # 协议自检工具（11 项检查）
│   └── clean_before_release.py              # 发布前清理
├── tests/                                   # verify_*.py 验证脚本 + legacy/
├── reports/                                 # 生成的报告
├── config/                                  # config 包（运行配置在 core/runtime_config.py）
├── assets/
│   ├── fonts/simhei.ttf                    # PDF 中文字体
│   └── concept_a_hex/                      # 应用 Logo 图标
├── docs/                                    # PRD 文档（3 份）
├── main.py
├── start_fuzz.bat
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

> 功能/兼容性回归走「协议扩展 PRD v2.0.0」的**阶段 7：全面检查**（功能性 11 项，7.1~7.11），
> 本小节只管安全——加了新协议后，安全基线有没有被破坏。
> 不通过 → 不修完不能进主分支。

| # | 检查项 | 怎么查 | 不通过意味着 |
|---|--------|--------|-------------|
| 1 | **新 server.py 默认监听 127.0.0.1** | 在 `server/<new>_server.py` 里搜 `0.0.0.0` — 不应命中 | 暴露到公网，任何人都能连 |
| 2 | **client.py / llm_mutator.py 无硬编码 Key/密码** | `rg -i "sk-[a-z0-9]{10}" src/protocols/<new>/` | 凭据硬编码进仓库，git 历史泄露 |
| 3 | **llm_mutator 走基类，基类有 timeout=25 + max_retries=0** | 优先 `rg "class.*llm_mutator" src/protocols/<new>/llm_mutator.py` 确认是薄壳（只 import 基类 + 继承）；独立实现则 `rg "timeout=25" src/protocols/<new>/llm_mutator.py` + `rg "max_retries=0" ...` | 反模式 M：云端 LLM 调用无限等；反模式 V：薄壳膨胀成独立实现 |
| 4 | **无 eval/exec/pickle.loads/os.system** | `rg "\beval\(|\bexec\(|pickle\.loads|os\.system" src/protocols/<new>/` | 代码注入风险 |
| 5 | **新协议不出现在 menu/fuzz_loop 的 if-elif** | `rg "elif.*<new>" src/core/` — 不应命中 | 反模式 B：核心代码因新协议膨胀 |
| 6 | **Bandit 零 HIGH（全局 + 协议级双层扫描）** | ① `bandit -r src/server -lll` 零 HIGH；② `bandit -r src/protocols/<new>/ server/<new>_server.py -lll` 零 HIGH | 协议级安全漏洞直接入包；只扫全局会漏掉新协议引入的局部风险 |

### 5.13 贡献者测试运行 + EXE 发布检查（来自 CONTRIBUTING.md §测试运行 + 协议扩展 PRD 7.11）

> 5.12 只管安全基线，本小节管**贡献者提交前自检**和**绿色 EXE 打包发布**两条流程线，
> 覆盖 check_protocol/Bandit/Key 残留之外的遗漏环节。
> 同步自 `fuzz_agent/docs/IndusFuzz 协议扩展 PRD.md` 阶段 7.11。

| # | 检查项 | 怎么查 | 不通过意味着 |
|---|--------|--------|-------------|
| **5.13.1** | **模拟从站启动验证** | `python -m src.core.slave_launcher --protocol <new> --port <default_port> --strict` 能成功启动、日志显示监听 `127.0.0.1:<port>`、Ctrl+C 正常退出；或在 `python main.py` 菜单里选"启动模拟从站"能正常启动 | 从站脚本能 import 但启动即崩，fuzz 端到端全断 |
| **5.13.2** | **单协议完整 fuzz 端到端** | 跑一次交互向导（`python main.py`），选 `<new>` 协议，至少选 3 个功能码，验收链路：① 能发请求到从站 ② 能收响应 ③ 能分类（正常响应 / 超时 / 协议错误 / 连接断开） ④ 能写 HTML 报告到 reports/ 目录 ⑤ 报告中中文正常显示（无乱码、无方块） | 新协议能跑 check_protocol 但 fuzz 实际不通；或报告乱码（simhei.ttf 未正确打包） |
| **5.13.3** | **功能码五处数量一致（P0 阻断）** | func_codes JSON 条目数 = client.py 默认端口映射数 = mutator 变异覆盖数 = server `_REQUEST_TYPES` 或等效列表数 = report_generator `PROTOCOL_CONFIG` 条目数；任一不一致 → 禁止进主分支 | 报告显示的功能码和实际变异发的功能码对不上；或 mutator 变异 JSON 里不存在的功能码导致 IndexError |
| **5.13.4** | **CHANGELOG 已更新** | CHANGELOG.md 对应版本段的 Added / Changed / Fixed 下有本次改动条目 | 贡献者流程不合规，发版时变更追溯困难 |
| **5.13.5** | **依赖可控** | requirements.txt 无意外新增条目（每次打包前 `git diff` 确认）；如确需新增，必须在 PR 描述中说明必要性 | 隐式拉进了恶意包（PyPI 投毒风险）；或打包后 EXE 体积异常膨胀 |
| **5.13.6** | **EXE 打包后完整 fuzz 验证（绿色发布时追加）** | 用 `dist/IndusFuzz.exe` 而非源码跑一轮完整 fuzz，验收同 5.13.2，额外确认 EXE 退出后 reports/ 目录有新生成的报告文件 | EXE 能启动但 fuzz 逻辑有 `sys._MEIPASS` 相关 bug；或从站通过 subprocess 无法被 EXE 拉起 |

### 5.14 pytest 测试代码质量审计（tests/ 目录专项）

> 5.12/5.13 管"生产代码能不能安全跑、fuzz 能不能端到端通"，
> 5.14 管"用来验证这些的测试代码本身是不是合格"。
> **信任边界**：不能因为 pytest 通过 94/97 就断言项目没问题 — 要先确认"覆盖了关键路径、fixture 没竞态、没假阳性"。

#### 5.14.1 目录结构与命名

| 规则 | 检查方法 | 不通过意味着 |
|------|----------|-------------|
| **pytest 测试文件使用 `test_*.py` 命名** | `ls tests/test_*.py` 列出所有 pytest 收集的文件；同时跑 `pytest tests/ --collect-only -q` 确认被收集的测试文件全部以 `test_` 开头 | verify_*.py / debug_*.py 等临时脚本混在 tests/ 里被误收集，或真正的测试文件没被 pytest 收集 |
| **非 pytest 脚本不混入 tests/** | verify_*.py / 临时调试脚本统一放项目根 `tools/verify/` 或 `scripts/`；tests/ 下只留 test_*.py + conftest.py + __init__.py + 必要的 helpers（命名前缀 `_`） | 贡献者看到目录混乱，误判哪些是正式测试 |
| **helpers 目录/文件命名清晰** | fixtures/mocks/helpers 统一放 `tests/_helpers/`（或 `tests/conftest.py`），禁止直接叫 `fuzz_loop.py` / `modbus_client.py`（与 src/ 重名易混淆） | `import tests.fuzz_loop` 和 `import src.core.fuzz_loop_llm` 两条 import 路径并存，贡献者写新测试时容易写错 |
| **禁止硬编码绝对路径** | `rg "D:\\|C:\\" tests/` 零命中（用 `tempfile.mkdtemp()` 或项目相对路径） | 测试只能在作者机器上跑，CI 一跑就崩 |

#### 5.14.2 测试基础设施

| 规则 | 检查方法 | 不通过意味着 |
|------|----------|-------------|
| **有 pytest 配置文件** | 项目根存在 `pytest.ini` 或 `pyproject.toml` 含 `[tool.pytest.ini_options]`，至少配 `testpaths = tests` + `addopts = --tb=short --strict-markers` | 贡献者本地跑 pytest 输出和 CI 不一致（CI 加了 `--cov` 但本地没，或反之） |
| **pytest-cov 已装 + 覆盖率门禁** | `pip show pytest-cov` 存在；`pytest tests/ --cov=src --cov-fail-under=XX` 作为 CI 门禁 | 不知道自己测了多少；覆盖率 16% 以下就放行等于没测 |
| **核心模块覆盖率不低于 30%** | `pytest tests/ --cov=src --cov-report=term-missing` 后看 fuzz_loop_llm / client.py / llm_mutator_base / slave_launcher 四个关键模块 | 如果 fuzz_loop_llm.py 是 0%，那 fuzz 主循环有没有 bug 全靠运气 |
| **pytest-timeout 可选装 + CI 默认启用** | `pip show pytest-timeout`；CI 用 `--timeout=60` 防止 fixture 死锁或 socket 测试 hang 住 | 某个 mock 写错导致 recv 永远阻塞，测试跑半小时没人发现 |
| **flake8 可用（或等效 lint）** | `pip show flake8` 或 CONTRIBUTING.md 声明用 ruff/pylint | CONTRIBUTING.md 第 3.3 行说"flake8"但实际没装，贡献者 lint 命令跑不通 |
| **conftest.py 与生产代码耦合度低** | conftest.py 不 import 生产逻辑（只 import fixture 依赖）；不做真实 socket 连接 | 测试启动依赖 Ollama 或从站，CI 没装就崩 |

#### 5.14.3 Fixture 隔离与反模式

| 规则 | 检查方法 | 不通过意味着 |
|------|----------|-------------|
| **autouse fixture 不覆盖业务 fixture 的初始化** | 如 `_isolate_registry` 这种 fixture，`setup` 时保存的快照不能在测试执行期间被其他代码修改后、teardown 又恢复回旧快照（典型竞态） | 测试看起来跑通/failed，但实际验证的是 fixture 生命周期 bug，不是业务代码 bug |
| **fixture 作用域显式声明** | `@pytest.fixture(scope="function")` / `scope="module"`，避免默认 scope 导致跨测试污染 | 一个测试改了 registry，下一个测试继承了脏状态，间歇性 flaky |
| **mock 不打错模块层级（反模式 Z）** | mock 前 `rg` 确认被测模块真实 import 路径（如 `from src.protocols.modbus import mutator` vs `from . import mutator`）；禁 LLM 测试必须在装 openai 的 venv 下跑 | mock 打在了没人用的路径上，被测路径绕过 mock 直接走真逻辑（测 LLM 时自动发真实 API 调用） |
| **fixture teardown 幂等 + 无副作用** | 多次跑同一个 fixture 不报错；`shutil.rmtree(path, ignore_errors=True)` | teardown 失败抛异常导致后续 5 个测试 skip，看不到真正的 bug |
| **临时文件/目录用 `tempfile.mkdtemp()` + teardown 清理** | 禁止在 `reports/` 目录写真实报告文件（测试会留垃圾） | 跑了 20 轮测试后 reports/ 目录堆了 200 个垃圾 HTML |

#### 5.14.4 断言质量

| 规则 | 检查方法 | 不通过意味着 |
|------|----------|-------------|
| **禁止 `assert True` / `or True` 形式的空断言** | `rg 'assert True| or True' tests/` 零命中 | 断言永远通过，相当于没测 |
| **断言有实际业务含义** | 例如测试 mutator：不仅断言返回 bytes，还要断言长度不变 / 不是全零 / 至少一个字节被变异 | 能通过类型检查但变异逻辑坏了（比如把 payload 原封不动返回），测试照样 PASS |
| **parametrize 覆盖全 7 协议** | `rg parametrize tests/test_mutator.py` 确认有 `proto` 参数覆盖全部 `_PROTO_NAMES` | 只测 modbus，s7comm/dnp3 等 6 个协议 mutator 有 bug 发现不了 |
| **异常路径也有断言** | 不仅测 happy path（`assert encrypt_key(x) == x`），还要测空输入、超长输入、非法字符等边界 | 生产代码异常处理逻辑有 bug，只有走真实 fuzz 才会触发，但 fuzz 测试又不覆盖 |
| **安全类测试覆盖 XSS / HTTPS / Key 打码** | 已测但要确认：`_esc('<img src=x onerror=alert(1)>')` 真的被转义；`validate_cloud_url('http://api.openai.com', 'openai')` 真的拒绝 HTTP | 报告生成器有存储型 XSS 但测试只断言了 plain text；或 HTTPS 强制逻辑被绕过但测试只测了 ollama 本地 |

#### 5.14.5 运行时验证（审计必须亲自执行）

| 步骤 | 命令 | 通过标准 |
|------|------|----------|
| 1. 收集测试 | `pytest tests/ --collect-only -q` | 全部被收集，无 import error |
| 2. 全量执行 | `pytest tests/ -v --tb=short` | **failed=0, xfailed=0**（xfail 需显式标记 `pytest.mark.xfail`） |
| 3. 覆盖报告 | `pytest tests/ --cov=src --cov-report=term-missing` | fuzz_loop_llm / client / llm_mutator_base / slave_launcher 四个关键模块覆盖率 ≥ 30% |
| 4. Bandit 扫测试代码 | `bandit -r tests/ -lll` | 零 HIGH（禁止 eval/exec/subprocess.Popen 未等待） |
| 5. flake8 检查（如已装） | `flake8 tests/ --max-line-length=120` | 零 error / warning（flake8 E/F 前缀） |
| 6. verify_*.py 不是 pytest | `pytest tests/ -k verify_ --collect-only -q` | 收集数为 0（临时脚本没被 pytest 当成测试） |

**当前实测值（2026-09-19）**：

| 指标 | 实测值 | 门禁 | 状态 |
|------|--------|------|------|
| pytest collected | 97 | — | ✅ |
| pytest PASSED | 94 | failed=0 | ❌ 3 failed |
| pytest FAILED | 3 | 必须 0 | ❌ |
| 总覆盖率 | 16% | — | ⚠️ |
| fuzz_loop_llm.py | 0% | ≥ 30% | ❌ |
| client.py (7 协议) | 9-11% | ≥ 30% | ❌ |
| llm_mutator.py (7 协议) | 0% | ≥ 30% | ❌ |
| slave_launcher.py | 0% | ≥ 30% | ❌ |
| flake8 / pytest-timeout | 未装 | — | ⚠️ |
| pytest.ini / pyproject.toml | 无 | 必须有 | ❌ |
| verify_*.py 混入 tests/ | 8 个 | 0 | ❌ |

#### 放行判定矩阵

| 条件 | 全部满足才放行 |
|------|----------------|
| ① | pytest 全过（failed=0） |
| ② | 四个关键模块（fuzz_loop_llm / client / llm_mutator_base / slave_launcher）覆盖率 ≥ 30% |
| ③ | 有 pytest 配置文件 |
| ④ | tests/ 下无 verify_*.py / 临时脚本 |
| ⑤ | conftest.py 无 fixture 竞态（单独跑 + parametrize 跑结果一致） |
| ⑥ | 无 `assert True` / `or True` 空断言 |
| ⑦ | Bandit 扫 tests/ 零 HIGH |

**当前判定**：❌ **不放行** — 条件 ① ② ③ ④ ⑤ ⑥ 全部未满足

---

### 审计 PRD 与协议扩展 PRD 阶段 7 的对应关系

| 审计 PRD 节 | 对应阶段 7 | 侧重 |
|---|---|---|
| 5.12 安全基线回归 | 7.1 / 7.7 / 7.8 / 7.9 | 安全维度（bandit / key / timeout / 反模式） |
| 5.13 贡献者测试 + EXE 发布 | 7.11 | 流程维度（从站启动 / fuzz 端到端 / 功能码五处一致 / CHANGELOG / 依赖 / EXE 打包后 fuzz） |
| 5.14 pytest 测试代码质量 | —（项目级，非协议级） | 测试代码本身质量（目录结构 / fixture 隔离 / 断言质量 / 覆盖率 / flake8） |
| 5.15 目录规范体检 | —（项目级，每发布前执行） | 项目目录结构合规性（12 维度全量扫描） |
| — | 7.2 / 7.3 / 7.4 / 7.5 / 7.6 / 7.10 | 协议数量 / menu / slave 存在 / 真实设备握手（由审计专家在每轮审计收尾统一执行） |

---

### 5.15 目录规范体检（每发布前 / 每加新协议后执行）

> 5.12-5.14 管"代码能不能安全跑"，5.15 管"项目目录长得对不对"。
> **执行原则**：只检查不修改；不信任声明只信任 `Test-Path` / `git check-ignore` / pytest 实测。

#### 5.15.1 检查维度（12 项）

| # | 维度 | 核心检查点 | P0 触发条件 |
|---|------|-----------|------------|
| 1 | 顶层目录结构 | main.py / requirements.txt / README* / CHANGELOG / CONTRIBUTING / LICENSE / .gitignore / src / server / tools / tests / docs / assets / reports | 缺少 main.py 或 src/ → P0 |
| 2 | src/ 结构 | __init__.py + core / protocols / integrations 三目录 + 全 snake_case 命名 | 缺 protocols/ → P0 |
| 3 | src/core/ 内容 | version / menu / fuzz_loop_llm / report_generator / slave_launcher / security / llm_precheck / llm_status / runtime_config / diagnose / gpu_detector / color_output / result_analyzer 共 13 个 | 缺 menu.py 或 fuzz_loop_llm.py → P0 |
| 4 | src/protocols/ 结构 | base.py + registry.py + llm_mutator_base.py + func_codes/ + 每个协议独立子目录 | 缺 registry.py → P0 |
| 5 | func_codes/ 完整性 | 7 协议 × JSON 存在 + 每个 JSON 含 protocol / default_port / func_codes 数组非空 | 任一 JSON 缺字段 → P0 |
| 6 | server/ 从站脚本 | 7 个 *_server.py 存在 + 支持 --port / --strict + 默认绑定 127.0.0.1 | 任一从站脚本缺 --port 或绑定 0.0.0.0 → P0 |
| 7 | tests/ 目录 | conftest.py + 4 个 test_*.py + 无 verify_*.py 混入 + 无 legacy/（legacy 应移 tools/legacy/） | verify_*.py 在 tests/ 里 → P2；legacy/ 在 tests/ → P2 |
| 8 | tools/ 目录 | check_protocol.py + clean_before_release.py + verify/ + legacy/ | 缺 check_protocol.py → P1 |
| 9 | .github/ 配置 | workflows/test.yml + workflows/release.yml + ISSUE_TEMPLATE 3 个 + PULL_REQUEST_TEMPLATE.md | 全缺 → P2；缺 CI workflow → P1 |
| 10 | assets/ 资源 | fonts/simhei.ttf（PDF 中文） + icons/（icon.ico 或等效多尺寸 PNG） | 缺 simhei.ttf → P0（PDF 中文变方块） |
| 11 | 临时文件 | __pycache__ / *.pyc / .pytest_cache / .coverage / htmlcov / build/ / dist/ / *.log / *.tmp / reports/*.html / *.pdf 必须 .gitignore 且未提交 | 已提交的报告文件或 __pycache__ → P0（敏感信息泄露） |
| 12 | .gitignore 完整性 | Python 缓存 / 虚拟环境 / 测试缓存 / 打包产物 / 报告输出 / 敏感文件 / 操作系统文件 / IDE 共 8 类 | 缺 agentscope_env/ 或 reports/ → P1 |

#### 5.15.2 执行命令清单（审计必须亲自执行）

```powershell
# Step 1 — 完整目录树
cd fuzz_agent
Get-ChildItem -Recurse -File | Where-Object {
    $_.FullName -notmatch '\\\.git\\|agentscope_env|__pycache__|\.pytest_cache|htmlcov|build|dist'
} | Select-Object FullName | Sort-Object

# Step 2 — 顶层必存在文件
@(
  'main.py','requirements.txt','README.md','CHANGELOG.md',
  'CONTRIBUTING.md','LICENSE','.gitignore','IndusFuzz.spec'
) | ForEach-Object { "$_ : $(Test-Path $_)" }

# Step 3 — src/core 必存在 13 个
$core = @(
  'version.py','menu.py','fuzz_loop_llm.py','report_generator.py',
  'slave_launcher.py','security.py','llm_precheck.py','llm_status.py',
  'runtime_config.py','diagnose.py','gpu_detector.py','color_output.py',
  'result_analyzer.py'
)
$core | ForEach-Object { "$_ : $(Test-Path src/core/$_)" }

# Step 4 — func_codes 字段完整性（含非空断言）
python -c "
import json, os
for f in os.listdir('src/protocols/func_codes'):
    if f.endswith('.json'):
        d = json.load(open(f'src/protocols/func_codes/{f}', encoding='utf-8'))
        has_p = 'protocol' in d; has_port = 'default_port' in d
        codes_ok = isinstance(d.get('func_codes'), list) and len(d['func_codes']) > 0
        print(f'{f}: protocol={has_p} port={has_port} codes={codes_ok} n={len(d.get(\"func_codes\",[]))}')
"

# Step 5 — 7 协议 check_protocol 自检
foreach ($p in modbus,s7comm,dnp3,iec104,iec61850,enip,opcua) {
  python tools/check_protocol.py $p
}

# Step 6 — pytest 收集
pytest tests/ --collect-only -q

# Step 7 — git status + .gitignore 检查
git status --short
git check-ignore -v __pycache__ .pytest_cache reports/ agentscope_env 2>&1

# Step 8 — .gitignore 关键模式
Select-String .gitignore -Pattern '__pycache__','agentscope_env','reports/','dist/','build/','*.spec.bak','htmlcov'
```

#### 5.15.3 放行判定（7 条，全部满足才放行）

| # | 条件 |
|---|------|
| ① | 维度 1-4 / 5（func_codes 字段） / 6（server 绑定 127.0.0.1） / 10（simhei.ttf）零 P0 |
| ② | 维度 11 零**已提交**的临时文件（git ls-files 无 __pycache__ / *.pyc / reports/*.html 等） |
| ③ | 维度 12 .gitignore 覆盖 8 类关键模式 |
| ④ | 7 协议 check_protocol.py 全 PASS |
| ⑤ | pytest collect-only 97 items（与代码现状一致） |
| ⑥ | git status 无意外未跟踪文件（非 __pycache__ / .pytest_cache / coverage_html / 预期报告） |
| ⑦ | 无 verify_*.py / legacy/ 留在 tests/ 里 |

#### 当前已知遗留项（2026-09-19 实测）

| 维度 | 已知问题 | 级别 |
|------|----------|------|
| 7 tests/ | tests/legacy/ 仍存在（两个 scapy helper），verify_*.py 已移至 tools/verify/ | P2 |
| 9 .github/ | 全缺（无 CI workflow / issue template / PR template） | P2 |
| 11 临时文件 | coverage_html/ 生成在项目根 + .pytest_cache/ + __pycache__/ 散落在各目录 | 需 .gitignore 验证 |
| 12 .gitignore | 需查是否覆盖 htmlcov / coverage_html 等新增模式 | 待验证 |

---

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