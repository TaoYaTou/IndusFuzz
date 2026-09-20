# IndusFuzz 全生命周期规则 v5（2026-09-21 固化，含 20 条经验教训）

## 🚨 经验教训速查表（红线，每条都踩过或验证过）

| # | 教训 | 来源 | 对应规则 |
|---|------|------|---------|
| **L1** | **误删当前版本产物** — 批量删除未区分新旧，把刚打好的 v1.8.5 也删了 | 本会话 2026-09-21 | P3-1 |
| **L2** | **遗漏 push 命令输出** — R10 只说不执行 push，没说必须输出，用户得追问 | 本会话 2026-09-21 | P3-10 |
| **L3** | **审计迭代漏同步文档** — 只更新脚本，忘了同步规则文档和外部 PRD | 本会话 2026-09-21 | P2-4 |
| **L4** | **假成功反模式** — 4 协议 client.connect() 只做 TCP SYN/ACK 就算"已连接真实设备" | 本会话 2026-09-20 | P2-1 |
| **L5** | **版本号 fallback 过时** — build.ps1 卡 1.8.3，无 tag 环境版本倒退 | 本会话 2026-09-20 | P3-4 |
| **L6** | **PyInstaller 产物误提交** — dist/*.exe / *.zip 被 git add --all 纳入暂存区 | 本会话 2026-09-20 | P3-6/P3-8 |
| **L7** | **审计只看源码不看 pytest 质量** — 只扫 src/ 不扫 tests/ 空断言/硬编码路径 | 本会话 2026-09-20 | P2-1 |
| **L8** | **不擅自 push** — 只说"提交版本"，Agent 额外执行 push 并承诺创建 Release（实际未创建） | ExperienceRecall 1715588 | P3-10 |
| **L9** | **PyInstaller 必须 --clean** — 不加 --clean 做增量打包，旧模块残留，时间戳不变 | ExperienceRecall 494575 | P3-2 |
| **L10** | **审计输出必须结构化 JSON** — 全文搜索会把标题当数据残留、把合法第三状态当异常 | ExperienceRecall 2238549 | P2-1 |
| **L11** | **规则体系联动必须同步** — 脚本进化了但 RULES_RELEASE.md 和外部 PRD 没跟上 | ExperienceRecall 2251019 | P1-3/P2-4 |
| **L12** | **批量删除谨慎新旧混淆** — Filter 通配符会把当前版本也扫进去，必须固定"先全清再打新" | ExperienceRecall 920820 | P3-1 |
| **L13** | **connect 失败仍置 Connected** — 吞掉异常后仍打印"已连接真实设备" | ExperienceRecall 531960 | P2-1 |
| **L14** | **硬编码清单必须与实际同步** — PyInstaller hiddenimports 漏加新模块 → ImportError | ExperienceRecall 2112333 | P3-2/P3-4 |
| **L15** | **文档宣称核对完毕但 grep 被清空** — Agent 声称更新了 MD 但实际内容没改，交付不可追溯 | ExperienceRecall 2366236 | P1-3 |
| **L16** | **规则注入无备份无结构化合并** — 直接覆写 config 文件导致丢失 | ExperienceRecall 1076559 | P1-3 |
| **L17** | **新增协议跳过业务层** — 只搭 COTP 握手层，没写 S7 Setup / MMS Initiate 响应骨架 | 本会话 2026-09-20 | P1-1 |
| **L18** | **新增协议 client.connect 无协议层校验** — 只做 TCP 连接就算成功 | 本会话 2026-09-20 | P1-1/P2-1 |
| **L19** | **spec hiddenimports 漏新模块** — PyInstaller 运行时 ImportError | 本会话 2026-09-20 | P3-2 |
| **L20** | **func_codes JSON 漏新协议** — audit 5.15 dim5 发现 JSON 字段不全 | 本会话 2026-09-20 | P1-2 |

---

## 三阶段全生命周期流水线

```
  阶段 1: 开发（加协议 / 改代码 / 修 bug）
      ↓
  阶段 2: 审计（跑 audit_prd.py + 文档同步）
      ↓
  阶段 3: 发布（打包 / ZIP / push 命令）
```

---

# 阶段 1：开发规则（新增协议 / 改代码 / 修 bug）

### P1-1 新增协议骨架（防 L17/L18）
新增协议 `X` 必须创建以下文件，**每个都要有业务层实现**（不能只搭连接层）：
```
src/protocols/X/__init__.py
src/protocols/X/client.py          ← 必须含协议层握手响应校验（防 L18）
src/protocols/X/mutator.py
src/protocols/X/llm_mutator.py
src/protocols/X/modbus_tools.py    ← 可选，仅 Modbus 有
src/protocols/func_codes/X_func_codes.json  ← 必须有 protocol + default_port + func_codes 非空（防 L20）
server/X_server.py                 ← 必须含完整状态机（防 L17）
tests/test_*.py 相关扩展           ← 不能只有 assert True
```
**server 强制要求**（防 L17）：
- 带 `--port` / `--strict` 命令行参数
- 绑定 `127.0.0.1`（严格模式）+ `0.0.0.0`（宽松模式）
- 有完整业务层状态机（COTP Setup / S7 Setup / MMS Initiate 等）
- 真实 client 能通过 connect() + send_payload() 收到业务层响应

**client.connect() 强制要求**（防 L18）：
- TCP 连接后必须发送协议层握手请求
- 必须校验协议层握手响应（不是只看 recv 超时）
- Modbus → MBAP protocol_id=0x0000 校验
- OPC UA → b"ACK" / b"ERR" 校验
- DNP3 → 帧头 0x0564 校验
- IEC104 → 帧头 0x68 校验
- S7comm → 0xD0 Ack + 0x32 Ack 校验
- IEC61850 → 0xD0 Ack + 0x82 Ack 校验
- ENIP → session_handle 非零校验

### P1-2 func_codes JSON 规范（防 L20）
每个 `func_codes/X_func_codes.json` 必须包含：
```json
{
    "protocol": "X",
    "default_port": 1234,
    "func_codes": [
        {"code": "0x01", "name": "描述", "rw": "R", "risk": "LOW"},
        ...
    ]
}
```
字段不全或 func_codes 空数组 = L20 违规。

### P1-3 开发执行依据 + MD 文件同步（**强制，防 L11/L15/L16**）

**先读 PRD 再动手**：新增协议必须按 `docs/IndusFuzz 协议扩展 PRD.md` 的章节模板逐条执行（文件结构 / 基类签名 / func_codes JSON / server 状态机 / client 握手校验）。
PRD 本身也是**活文档**，每次跑完流程后必须同步更新。

每次开发完成（含新协议、改业务逻辑、修 bug），**必须按以下优先级同步文档**（缺一份 = L11 违规）：

| 优先级 | MD 文件 | 更新触发 | 更新内容 |
|--------|---------|---------|---------|
| **1 (执行依据)** | `docs/IndusFuzz 协议扩展 PRD.md` | 新增协议 / 改协议骨架 | 协议模板实例化、踩坑反模式追加、教训 L17/L18/L20 写入 |
| **2 (执行依据)** | `docs/IndusFuzz 审计PRD.md` | 审计发现新问题 / 改审计维度 | 追加新章节或补充维度描述（防 L11） |
| **3 (执行依据)** | `docs/IndusFuzz 审计修复总结PRD.md` | 本轮审计修复 | 追加修复案例（问题 → 根因 → 修复 → 验证） |
| **4 (规则)** | `RULES_RELEASE.md` | 踩到新坑 | 教训表追加 L{n} + 错误案例表追加 |
| **5 (项目记录)** | `CHANGELOG.md` | 每次有功能/bugfix | 新增版本条目 |
| **6 (用户可见)** | `README.md` / `README.zh.md` | **每次代码更新（含小更新，不限发布）** | 目录树（P1-3a）+ 版本号（P1-3b）+ 内容核实（P1-3c） — 三项全要，不能只更目录丢其他 |

**禁止**：Agent 宣称"已同步 MD 文件"但未实际读取/写入文件（L15 教训）。
**禁止**：直接覆写 config/rules 文件而不做结构化合并或备份（L16 教训）。
**禁止**：不读 PRD 就新增协议（会重复踩 L17/L18/L20 的坑）。
**禁止**：更新 README 时只改目录树，版本号或内容核实不动（违反 P1-3 整体约束）。

#### P1-3a README 项目目录树强制同步（**每次代码变更后立即执行**）
`README.md` 的 `## 16. Project Structure` 和 `README.zh.md` 的 `## 16. 项目结构` 包含完整目录树。
**任何代码变更**（新增文件 / 删除文件 / 重命名 / 移动位置 / 修改文件注释功能）后，**必须同步更新两个 README 的目录树**。
不发布包不代表可以跳过——目录树是用户和开发者理解项目结构的唯一权威来源。

**验证命令**：
```python
python tools/verify_readme_structure.py
# 输出: README vs 磁盘差异清单（缺文件 / 多文件 / 注释过时）
```

#### P1-3b README 版本号同步 + 版本号进位规则（**每次代码更新必做**）
README.md / README.zh.md 头部和简介区引用的版本号必须同步更新。
**版本号格式**：`v.A.B.C`
| 位 | 含义 | 何时递增 |
|----|------|---------|
| **C**（第 4 位） | 小更新 | bugfix、小优化、注释修正、仿真器微调 |
| **B**（第 3 位） | 大更新 | 新增协议、重大功能重构、架构变更；**C 满（≥9）自然进位 B** 也算大更新 |
| **A**（第 2 位） | 重大更新 | 跨协议架构变更、核心模块重写；**B 满（≥9）自然进位 A** 也算重大更新 |

**进位示例**：`v1.8.4` → 3 次 bugfix → `v1.8.7`；再 3 次 bugfix → C 进位 B → `v1.9.0`；B 满 9 次 → A 进位 → `v2.0.0`。
**README 版本号**：`README.md` 和 `README.zh.md` 头部、快速开始、协议列表里出现的版本号必须全部改成当前 `get_version()` 的值，不能有一处遗漏。

#### P1-3c README 内容核实真实文件（**禁止凭空写**，防 L15）
更新 README 时**必须对照真实文件**：
- 功能描述 → 读对应模块 docstring 或源码
- 命令示例 → 实际跑一遍确认无错
- 文件列表 → `ls` / `glob` 确认存在
- **禁止**：Agent 凭空编造功能描述、命令参数或文件列表（L15 教训：宣称核对完毕但 grep 被清空）。

**验证手段**：对 README 里的每个代码块或文件路径，至少 `RunCommand` 执行一次或 `Glob` / `LS` 确认存在。

### P1-4 开发自检命令（必须跑）
```bash
# 1. 新增协议后验证 server 能启动 + client 能 connect + send
python server/X_server.py --port {port} --strict &
python -c "
from src.protocols.X.client import XClient
c = XClient()
assert c.connect('127.0.0.1', {port}, timeout=2), 'connect 握手失败'
print('✅ X connect OK')
"

# 2. pytest 全量
python -m pytest tests/ -q --tb=short
```

---

# 阶段 2：审计规则（放行前必须全绿）

### P2-1 三检门禁（防 L4/L7/L10/L13）
1. `git status --short` 为空（工作区干净）
2. `python audit_prd.py` → `audit_result.json` **结构化指标**全绿（防 L10）：
   - pytest collected & 全部 passed
   - bandit HIGH = 0
   - 空断言 = 0
   - 绝对路径硬编码 = 0
   - 12 目录规范维度无 P0
3. **新增协议 client.connect() 握手校验**（防 L4/L13）：
   用假 TCP server（只回 SYN/ACK，不回协议帧）验证 client.connect() **正确返回 False**

### P2-2 audit_prd.py 本身的完整性 + 审计必须全量（**强制，防 L11/L10**）
**审计必须完整跑一次 `python audit_prd.py`，不能挑选章节或维度**（防 L11/L10）：
- ❌ 禁止 `python audit_prd.py --dim 5.15` 只跑目录规范
- ❌ 禁止 `python audit_prd.py -k "pytest"` 只跑 pytest
- ❌ 禁止 Agent 跳过某些维度口头宣称"没问题"
- ✅ 正确：`python audit_prd.py`（无参数）→ 完整 20 维度 → `audit_result.json`

`audit_prd.py` 必须覆盖 20 维度（PRD 5.15 目录规范 12 + 5.14 pytest 质量 5 + 5.12 安全基线 3）。
**发现脚本有盲区** → 立即补充维度（防 L11）。
**发现 Agent 想挑章节跑** → 判定为 P2-2 违规，必须重跑全量。

**补充 P2-2a README 目录树验证**：如果 `tools/verify_readme_structure.py` 已实现，P2-2 阶段必须同时跑它，确认 README.md / README.zh.md 目录树与实际磁盘一致（防 P1-3a 规则被跳过）。

### P2-3 审计输出可追溯（防 L15）
`audit_result.json` 是放行凭证，必须包含每项检查的 `status: pass/fail` 和 `evidence` 字段。
**禁止** Agent 口头宣称"全绿"但拿不出 `audit_result.json` 内容（L15 教训）。

### P2-4 审计迭代 4 处同步（防 L3/L11，强制）
每次审计发现新问题，**必须同时更新 4 处**（缺一处 = L3 违规）：
1. **`audit_prd.py`** — 新增检查维度
2. **`audit_result.json`** — 重跑确认归零
3. **`RULES_RELEASE.md`** — 教训表追加 L{n} + 错误案例表追加
4. **外部触发审计的文档**（`docs/IndusFuzz 审计PRD.md` + `docs/IndusFuzz 审计修复总结PRD.md`）— 审计 PRD 追加新章节/维度描述；修复总结 PRD 追加"问题→根因→修复→验证"案例

**审计执行顺序**：按 `docs/IndusFuzz 审计PRD.md` **所有章节全面跑**，不能只跑 5.12/5.14/5.15 三个核心章节。`python audit_prd.py` 无参数 → 完整 20 维度全部执行 → 产出 `audit_result.json` → 发现问题后查 `docs/IndusFuzz 审计修复总结PRD.md` 是否已有同类修复记录（防重复踩坑） → 按上述 4 处同步。

**新增协议审计**：除上述三份审计文档外，还需对照 `docs/IndusFuzz 协议扩展 PRD.md` 检查是否按模板实现（防 L17/L18/L20）。

### P2-5 pytest 质量红线（防 L7）
- **空断言**：`assert True` / `or True` → 零命中
- **绝对路径硬编码**：`C:\Windows\...` / `/home/...` → 零命中
- **测试覆盖**：核心模块（base.py / registry.py / version.py / report_generator.py）覆盖率 ≥ 30%
- **测试能独立跑通**：`python -m pytest tests/ -q` 不能有跳过或 xfail（除非有明确注释）

---

# 阶段 3：发布规则（单向流水线，固定顺序）

### P3-1 旧产物强制清除（防 L1/L12）
> 打包步骤**第一个动作**。磁盘上**永远只能有一个版本**。
```powershell
Get-ChildItem -Filter "IndusFuzz-v*-win64*" | Remove-Item -Recurse -Force
Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
```
**禁止**：区分版本号选择性删除（L1/L12 教训），或跳过此步直接打包。

### P3-2 PyInstaller 打包（防 L9/L14/L19）
```powershell
python -m PyInstaller --clean IndusFuzz.spec
```
- **必须 --clean**（L9 教训）
- 打包后验证：`dist/IndusFuzz.exe` 存在且大小 > 50 MB
- `IndusFuzz.spec` hiddenimports 每次检查是否漏加新模块（L14/L19 教训）

### P3-3 组装发布目录
- EXE：`dist/IndusFuzz.exe`
- 文档：README.md / README.zh.md / CHANGELOG.md / LICENSE / requirements.txt
- 脚本：`audit_prd.py` + `RULES_RELEASE.md`（随包发布）
- 配置：`config/protocols.json` + `config/llm_config.example.json`
- 资源：`assets/fonts/simhei.ttf` + `assets/concept_a_hex/icon.ico`
- 工具：`tools/check_protocol.py`
- 空目录：`reports/`

### P3-4 版本号同步（防 L5/L14，升版本时必须改 5 处）
1. `src/core/version.py` → `HARDCODED_VERSION`
2. `build.ps1` → fallback（**两个 catch 块都要改**）
3. `make_release.bat` → fallback
4. `start_fuzz.bat` → fallback
5. `git tag -a v{V}`（annotated tag）

### P3-5 ZIP 命名
`IndusFuzz-v{V}-win64.zip`。完成后确认 ZIP 存在且大小 > 50 MB。

### P3-6 PyInstaller 中间产物清理（防 L6）
打包完成后立即删 `build/` + `dist/`。

### P3-7 .gitignore 检查（防 L6）
必须包含：`*.zip` / `IndusFuzz-v*-win64/` / `build/` / `dist/` / `agentscope_env/` / `reports/*.html` / `reports/*.pdf` / `.coverage` / `htmlcov/` / `.pytest_cache/` / `__pycache__/` / `*.pyc`。

### P3-8 发布目录完整性验证
ZIP 解压后所有必须文件都存在（P3-3 清单），不能缺。

### P3-9 版本号再次锁定
`git describe --tags --always` = `src/core/version.py` 的 `get_version()`。

### P3-10 交付 push 命令（**必须输出，Agent 不执行，防 L2/L8**）
Agent **禁止执行** `git push` / GitHub Release / 二进制上传（L8 教训）。
但每次发布完成后**必须输出以下命令块**（L2 教训）：
```bash
git push origin main
git push origin v{V}
# GitHub Release 创建: https://github.com/{user}/{repo}/releases/new
# 上传 IndusFuzz-v{V}-win64.zip 作为 Release Asset
```
**遗漏输出 = P3-10 违规**。发布闭环以用户执行为标志。

---

## 项目 MD 文件清单（RULES_RELEASE.md 管它们的同步）

| 文件 | 路径 | 谁负责同步 |
|------|------|-----------|
| RULES_RELEASE.md | 顶层 | Agent（本文件） |
| README.md / README.zh.md | 顶层 | P1-3 触发时同步 |
| CHANGELOG.md | 顶层 | P1-3 / P3-4 触发时同步 |
| CONTRIBUTING.md | 顶层 | P1-3 触发时同步 |
| docs/IndusFuzz 审计PRD.md | docs/ | P2-4 触发时同步 |
| docs/IndusFuzz 协议扩展 PRD.md | docs/ | P1-1 / P1-3 触发时同步 |
| docs/IndusFuzz 审计修复总结PRD.md | docs/ | P2-4 触发时同步 |
| .github/ISSUE_TEMPLATE/*.md | .github/ | 人工维护，Agent 不改 |
| .github/PULL_REQUEST_TEMPLATE.md | .github/ | 人工维护，Agent 不改 |

---

## 项目目录规范（P2-1 audit 5.15 覆盖）

```
IndusFuzz/                              ← 项目根
├── src/                                ← 源码
│   ├── core/                           ← 15 个核心模块
│   ├── protocols/                      ← 7 协议 + 3 基类 + func_codes/
│   │   ├── base.py / llm_mutator_base.py / registry.py
│   │   └── {protocol}/ (client.py + mutator.py + llm_mutator.py) × 7
│   └── integrations/                   ← 外部 MCP 集成
├── server/                             ← 7 协议仿真器
├── tests/                              ← pytest 测试（无 verify_*.py 混入）
├── tools/                              ← check_protocol.py + verify/ + legacy/
├── config/                             ← YAML 配置
├── assets/                             ← 字体 + 图标
├── docs/                               ← 3 份 PRD 文档
├── .github/workflows/                  ← release.yml + test.yml
├── IndusFuzz.spec                      ← PyInstaller 配置
├── audit_prd.py + audit_result.json    ← PRD 审计脚本 + 产物
├── RULES_RELEASE.md                    ← 本文件
├── README* / CHANGELOG.md / LICENSE    ← 项目文档
└── .gitignore                          ← 屏蔽 *.zip / 打包产物 / agentscope_env/
```

---

## 错误案例记录（每次追加一行）

| 日期 | 错误 | 教训 | 修正规则 |
|------|------|------|---------|
| 2026-09-21 | "删除旧包"指令下未区分版本，把当前 v1.8.5 也删了 | L1 | P3-1 单向流水线 |
| 2026-09-21 | 遗漏输出 push 命令，用户追问才拿到 | L2 | P3-10 强制输出 |
| 2026-09-21 | R11 只说更新脚本，漏同步规则文档和外部 PRD | L3 | P2-4 改为 4 处同步 |
| 2026-09-20 | 4 协议 client.connect() 假成功 | L4 | P2-1 加握手校验 |
| 2026-09-20 | build.ps1 fallback 卡 1.8.3 | L5 | P3-4 5 处同步 |
| 2026-09-20 | 审计只扫 src/ 不扫 tests/ | L7 | P2-1 audit 全量 |
| 2026-09-20 | S7comm/IEC61850 server 半成品缺 COTP/S7 Setup 响应 | L17 | P1-1 业务层状态机 |
| 2026-09-20 | PyInstaller spec hiddenimports 漏 modbus_tools.py | L19 | P3-2 spec 检查 |
