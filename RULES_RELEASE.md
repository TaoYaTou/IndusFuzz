# IndusFuzz 发布规则 v4（2026-09-21 固化，含 14 条经验教训）

## 🚨 经验教训速查表（红线，每条都踩过）

| # | 教训 | 来源 | 对应规则 |
|---|------|------|---------|
| **L1** | **误删当前版本产物** — 批量删除未区分新旧，把刚打好的 v1.8.5 也删了 | 本会话 2026-09-21 | R3 |
| **L2** | **遗漏 push 命令输出** — R10 只说不执行 push，没说必须输出，用户得追问才拿得到命令 | 本会话 2026-09-21 | R10 |
| **L3** | **审计迭代漏同步文档** — R11 只说更新脚本，忘了同步规则文档和外部 PRD，脚本口径与文档描述脱节 | 本会话 2026-09-21 | R11 |
| **L4** | **假成功反模式** — 4 协议 client.connect() 只做 TCP SYN/ACK 就算"已连接真实设备"，根本不校验协议层握手响应 | 本会话 2026-09-20 | R2 |
| **L5** | **版本号 fallback 过时** — build.ps1 fallback 卡 1.8.3，实际已经 1.8.4，git describe 拿到 tag 才正确，无 tag 环境版本倒退 | 本会话 2026-09-20 | R8 |
| **L6** | **PyInstaller 产物误提交** — dist/*.exe / *.zip 被 git add --all 纳入暂存区，二进制污染仓库 | 本会话 2026-09-20 | R7/R9 |
| **L7** | **审计只看源码不看 pytest 质量** — 只扫 src/ 安全，不扫 tests/ 空断言/绝对路径硬编码，测试本身就是坏的 | 本会话 2026-09-20 | R2 |
| **L8** | **不擅自 push** — 用户只说"提交版本"，Agent 额外执行 push 并承诺创建 Release（实际未创建），交付范围与事实不匹配 | ExperienceRecall 1715588 | R10 |
| **L9** | **PyInstaller 必须 --clean** — 不加 --clean 做增量打包，旧模块残留，产物时间戳不变，用户以为没更新 | ExperienceRecall 494575 | R4 |
| **L10** | **审计输出必须结构化 JSON** — 用全文搜索判断"是否过审计"会把报告标题当数据残留、把合法第三状态当异常 | ExperienceRecall 2238549 | R2 |
| **L11** | **规则体系联动必须同步** — 脚本进化了（audit_prd.py 加了新维度）但 RULES_RELEASE.md 和外部 PRD 没跟上，执行口径与文档描述不一致 | ExperienceRecall 2251019 | R11 |
| **L12** | **批量删除谨慎新旧混淆** — PowerShell `Get-ChildItem -Filter "IndusFuzz-v*-win64*"` 会把当前版本也扫进去，必须在流水线里固定"先全清再打新"顺序 | ExperienceRecall 920820 | R3 |
| **L13** | **connect 失败仍置 Connected 是反模式** — socket 超时/拒绝/协议不匹配都吞掉异常后仍打印"已连接真实设备"，Fuzz 流量发到空口 | ExperienceRecall 531960 | R2 |
| **L14** | **硬编码清单必须与实际同步** — PyInstaller hiddenimports 漏加新模块 → 运行时 ImportError；版本号 fallback 漏改 → 无 tag 环境版本号倒退 | ExperienceRecall 2112333 | R4/R8 |

---

## 触发条件
用户明确说"发布 v{version}"，Agent 启动完整流水线。

---

## 流水线（严格按序，不可跳步）

### R1 版本号锁定（防 L5/L14）
- `git describe --tags --always` → 锁定目标版本号 V
- 确认 `src/core/version.py` 的 `get_version()` = V
- 不一致 → 先执行版本号同步（R8）再继续

### R2 三检门禁（放行前必须全绿，防 L4/L7/L10/L13）
1. `git status --short` 为空（工作区干净）
2. `git describe --tags` 输出 V 存在（tag 已打）
3. `python audit_prd.py` → `audit_result.json` **结构化指标**（不是全文搜索）全绿：
   - pytest collected & 全部 passed
   - bandit HIGH = 0
   - 空断言 = 0（audit 5.14.3）
   - 绝对路径硬编码 = 0（audit 5.14.4）
   - 12 目录规范维度无 P0
4. **client.connect() 协议层握手校验** — 7 协议都必须做协议层响应检查（Modbus MBAP / OPC UA ACK / DNP3 0x0564 / IEC104 0x68 / S7comm 0xD0+0x32 / IEC61850 0xD0+0x82 / ENIP session_handle）

### R3 旧产物强制清除（防 L1/L12）
> 单向流水线关键节点：**打包步骤第一个动作，磁盘上永远只能有一个版本**。
> 顺序固定：先全清所有历史产物（不管新旧）→ 再 PyInstaller → 再组装 → 再 ZIP。
```powershell
# 删所有历史发布产物（不管版本号，不管新旧，全清）
Get-ChildItem -Filter "IndusFuzz-v*-win64*" | Remove-Item -Recurse -Force
# 删 PyInstaller 中间产物
Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
```
**禁止**：区分版本号选择性删除（L1 教训），或跳过此步直接打包。

### R4 PyInstaller 打包（防 L9/L14）
```powershell
python -m PyInstaller --clean IndusFuzz.spec
```
**必须加 --clean**（L9 教训），强制重建 build/，避免增量打包残留旧模块。
**打包后必须验证**：`dist/IndusFuzz.exe` 存在且大小 > 50 MB。

### R5 组装发布目录
- EXE：`dist/IndusFuzz.exe`
- 文档：README.md / README.zh.md / CHANGELOG.md / LICENSE / requirements.txt
- 脚本：`audit_prd.py` + `RULES_RELEASE.md`（随包发布，用户本地也能看到流程）
- 配置：`config/protocols.json` + `config/llm_config.example.json`
- 资源：`assets/fonts/simhei.ttf` + `assets/concept_a_hex/icon.ico`
- 工具：`tools/check_protocol.py`
- 空目录：`reports/`

### R6 ZIP 命名与打包（防 L6）
`IndusFuzz-v{V}-win64.zip`（V 来自 R1 锁定值）。完成后确认 ZIP 存在且大小 > 50 MB。

### R7 PyInstaller 中间产物清理（防 L6）
打包完成后立即删 `build/` + `dist/`（两者已被 .gitignore 屏蔽，但物理删除保险）。

### R8 版本号同步（防 L5/L14）
**升版本时必须同时改 5 处**：
1. `src/core/version.py` → `HARDCODED_VERSION`
2. `build.ps1` → fallback（**两个 catch 块都要改**）
3. `make_release.bat` → fallback
4. `start_fuzz.bat` → fallback
5. `git tag -a v{V}`（annotated tag）

PyInstaller `IndusFuzz.spec` 的 hiddenimports 清单每次升版本也要检查是否漏加新模块（L14 教训）。

### R9 .gitignore 屏蔽二进制产物（防 L6）
必须包含：`*.zip` / `IndusFuzz-v*-win64/` / `build/` / `dist/` / `agentscope_env/` / `reports/*.html` / `reports/*.pdf` / `.coverage` / `htmlcov/` / `.pytest_cache/` / `__pycache__/` / `*.pyc`。
**漏加任何一条 = L6 风险**。

### R10 交付 push 命令（**必须输出，Agent 不执行，防 L2/L8**）
Agent **禁止执行** `git push` / GitHub Release 创建 / 二进制上传（L8 教训）。
但每次发布完成后**必须输出以下命令块**（占位符 `{V}` 替换为当前版本号），由用户手动执行（L2 教训）：
```bash
git push origin main
git push origin v{V}
# GitHub Release 创建: https://github.com/{user}/{repo}/releases/new
# 上传 IndusFuzz-v{V}-win64.zip 作为 Release Asset
```
**遗漏输出 push 命令 = R10 违规**。发布流程闭环以用户执行 push 完成为标志。

### R11 审计迭代（**强制 4 处同步，防 L3/L11**）
每次审计发现新问题，**必须同时更新 4 处**（缺一处 = R11 违规，L3/L11 教训）：
1. **`audit_prd.py`** — 新增检查维度（让脚本能力持续增长）
2. **`audit_result.json`** — 重跑审计确认归零后更新输出
3. **`RULES_RELEASE.md`** — 错误案例表追加 + 教训表追加（如有新教训）
4. **外部触发审计的文档**（如 `IndusFuzz 审计PRD.md`）— 该文档本身也要同步更新，确保脚本口径与文档描述一致

---

## 错误案例记录（每次追加一行）

| 日期 | 错误 | 教训 | 修正规则 |
|------|------|------|---------|
| 2026-09-21 | "删除旧包"指令下未区分版本，把当前 v1.8.5 也删了 | L1 | R3 单向流水线 |
| 2026-09-21 | 遗漏输出 push 命令，用户追问才拿到 | L2 | R10 强制输出 |
| 2026-09-21 | R11 只说更新脚本，漏同步规则文档和外部 PRD | L3 | R11 改为 4 处同步 |
| 2026-09-20 | 4 协议 client.connect() 假成功 | L4 | R2 三检门禁加握手校验 |
| 2026-09-20 | build.ps1 fallback 卡 1.8.3 | L5 | R8 升版本 5 处同步 |
| 2026-09-20 | 审计只扫 src/ 不扫 tests/ | L7 | R2 audit_prd.py 全量 |
