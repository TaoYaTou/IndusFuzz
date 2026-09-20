# IndusFuzz 发布规则 v3（2026-09-21 固化）

## 触发条件
用户明确说"发布 v{version}"，Agent 启动完整流水线。

## 流水线（严格按序，不可跳步）

### R1 版本号锁定
- `git describe --tags --always` → 锁定目标版本号 V
- 确认 `src/core/version.py` 的 `get_version()` = V
- 不一致 → 先执行版本号同步（R8）

### R2 三检门禁（放行前必须全绿）
1. `git status --short` 为空（工作区干净）
2. `git describe --tags` 输出 V 存在（tag 已打）
3. `python audit_prd.py` → `audit_result.json` 全绿：
   - pytest collected = V 对应测试数 & 全部 passed
   - bandit HIGH = 0
   - 空断言 = 0（audit 5.14.3）
   - 绝对路径硬编码 = 0（audit 5.14.4）
   - 12 目录规范维度无 P0

### R3 旧产物强制清除（打包步骤 **第一个动作**）
> 磁盘上**永远只能有一个版本**的发布产物。
> 顺序：先扫再全删 → 再 PyInstaller → 再组装 → 再 ZIP。
```powershell
# 删所有历史发布产物（不管版本号，不管新旧，全清）
Get-ChildItem -Filter "IndusFuzz-v*-win64*" | Remove-Item -Recurse -Force
# 删 PyInstaller 中间产物
Remove-Item build, dist -Recurse -Force -ErrorAction SilentlyContinue
```

### R4 PyInstaller 打包
```powershell
python -m PyInstaller --clean IndusFuzz.spec
```

### R5 组装发布目录
- EXE：`dist/IndusFuzz.exe`
- 文档：README.md / README.zh.md / CHANGELOG.md / LICENSE / requirements.txt
- 脚本：`audit_prd.py`（随包发布，用户可本地审计）
- 配置：`config/protocols.json` + `config/llm_config.example.json`
- 资源：`assets/fonts/simhei.ttf` + `assets/concept_a_hex/icon.ico`
- 工具：`tools/check_protocol.py`
- 空目录：`reports/`

### R6 ZIP 命名与打包
`IndusFuzz-v{V}-win64.zip`（V 来自 R1 锁定值）

### R7 PyInstaller 中间产物清理
打包完成后立即删 `build/` + `dist/`。

### R8 版本号同步（升版本时必须同时改 5 处）
1. `src/core/version.py` → `HARDCODED_VERSION`
2. `build.ps1` → fallback（两个 catch 块）
3. `make_release.bat` → fallback
4. `start_fuzz.bat` → fallback
5. `git tag -a v{V}`（annotated tag）

### R9 .gitignore 屏蔽二进制产物
必须包含：`*.zip` / `IndusFuzz-v*-win64/` / `build/` / `dist/` / `agentscope_env/` / `reports/*.html` / `reports/*.pdf` / `.coverage` / `htmlcov/` / `.pytest_cache/` / `__pycache__/` / `*.pyc`

### R10 安全边界（禁止越权）
Agent 仅执行：本地 commit / tag / PyInstaller / ZIP。**git push / GitHub Release / 二进制上传由用户手动执行。**

### R11 审计迭代（**强制，发现即更新**）
- 每次审计发现新问题 → 同步更新 `audit_prd.py` 的检查维度
- 审计脚本维度覆盖越多越好，让审计能力持续增长
- 每轮审计产出 `audit_result.json` + 问题修复后立即重跑确认归零

## 错误案例记录
| 日期 | 错误 | 修正 |
|------|------|------|
| 2026-09-21 | "删除旧包"指令下未区分版本，把当前 v1.8.5 也删了 | 简化为单向流水线：**打包步骤固定先全删再打新**，磁盘永远只有一个版本 |
| 2026-09-21 | 审计发现空断言/硬编码路径，未同步进审计脚本 | 新增 R11，发现即更新 |
