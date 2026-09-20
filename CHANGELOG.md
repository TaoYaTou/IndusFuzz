# Changelog

All notable changes to IndusFuzz are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.8.3] - 2026-09-20

### Fixed
- 修复了一些BUG
- 修复 build.ps1 / make_release.bat / start_fuzz.bat / version_info.txt 硬编码版本号与 version.py HARDCODED 不一致

### Changed
- README.md / README.zh.md / CONTRIBUTING.md 目录树同步为 v1.8.3 扁平结构
- 版本合规性审计脚本自动识别并修复所有 .py / .bat / .ps1 / .md / .yml 中的过时版本号

## [1.8.2] - 2026-09-20

### Added / 新增

- mcp>=1.0.0 to requirements.txt — CI Windows runner needs it for MCP integration tests
  — requirements.txt 加入 mcp>=1.0.0，CI Windows runner 需要它来跑 MCP 集成测试
- .gitignore: dist/, build/, IndusFuzz-v*/, *.zip, *.spec.bak — build artifacts excluded from git index, local files preserved
  — .gitignore 新增 dist/, build/, IndusFuzz-v*/, *.zip, *.spec.bak：构建产物不再入库，本地保留

### Changed / 变更

- test.yml: runs-on changed from ubuntu-latest to windows-latest — project is Windows-only (pywin32, DPAPI)
  — test.yml: runs-on 从 ubuntu-latest 改为 windows-latest，项目依赖 Windows 专属库（pywin32, DPAPI）
- test.yml: black pinned to 24.10.0, flake8 args aligned with pre-commit
  — test.yml: black 锁定 24.10.0 版本，flake8 参数与 pre-commit 完全对齐
- release.yml: body_path removed, generate_release_notes: true — GitHub auto-generates per-tag release notes, removed hand-written CHANGELOG extractor step
  — release.yml: 删除 body_path，改用 generate_release_notes: true，GitHub 自动按 tag 生成 release notes，同时移除了手写的 CHANGELOG 抽取步骤
- pywin32==311 marked as Windows-only with sys_platform env marker
  — pywin32 加入 sys_platform == "win32" 环境标记，跨平台安全

### Fixed / 修复

- 18 files in tests/ and tools/ formatted with black 24.10.0
  — tests/ 和 tools/ 下 18 个文件用 black 24.10.0 格式化

### Removed / 移除

- build/ dist/ IndusFuzz-v*-win64/ *.zip removed from git index (--cached), local files preserved
  — build/ dist/ IndusFuzz-v*-win64/ *.zip 从 git 索引移除（--cached），本地文件保留
## [1.8.1] - 2026-09-20

### Added / 新增

- pytest test suite: 147 cases across registry / mutator / reporter / security modules
  — pytest 测试套件：registry / mutator / reporter / security 四大模块共 147 个用例
- run_all_tests.py 6-stage test orchestrator with Chinese HTML report generation
  — run_all_tests.py 六阶段测试编排器，生成中文 HTML 报告
- CI workflow test.yml — push/PR trigger: pytest + coverage fail-under=16% + flake8 + black --check + bandit
  — CI workflow test.yml：push/PR 触发，跑 pytest + 覆盖率下限 16% + flake8 + black --check + bandit
- CI workflow release.yml — tag v* trigger: test → PyInstaller → portable ZIP → GitHub Release with CHANGELOG notes + auto prerelease detection
  — CI workflow release.yml：tag v* 触发，测试 → PyInstaller → 便携 ZIP → 自动发布 GitHub Release（读 CHANGELOG 说明 + 自动预发布检测）
- .pre-commit-config.yaml — black / flake8 / bandit hooks (black scoped to tests/ tools/ due to no prior black history)
  — .pre-commit-config.yaml：black / flake8 / bandit 三个钩子（black 范围限定 tests/ tools/，因 src/ 无历史 black 记录）
- src/core/version.py three-source version resolution: INDUSFUZZ_VERSION env → git describe --tags → HARDCODED_VERSION fallback
  — src/core/version.py 三来源版本解析：INDUSFUZZ_VERSION 环境变量 → git describe --tags → HARDCODED_VERSION 兜底
- tools/verify/ and tools/legacy/ — verification helpers relocated out of tests/
  — tools/verify/ 与 tools/legacy/：验证辅助脚本从 tests/ 迁出

### Changed / 变更

- build.ps1 / make_release.bat / start_fuzz.bat all read version dynamically from version.py (single source of truth)
  — build.ps1 / make_release.bat / start_fuzz.bat 均从 version.py 动态读取版本（单一来源）
- CI flake8 args fully aligned with pre-commit: --max-line-length=120 --ignore=E501,W503 --select=E9,F63,F7,F82,E231,F401,W292
  — CI 的 flake8 参数与 pre-commit 完全对齐：--max-line-length=120 --ignore=E501,W503 --select=E9,F63,F7,F82,E231,F401,W292
- black scope limited to tests/ tools/ (src/ has no prior black history; will be reformatted in a dedicated PR)
  — black 范围限定 tests/ tools/（src/ 无历史 black 记录，将在独立 PR 中统一格式化）
- README.md / README.zh.md — add "Testing" section (env setup / run tests / coverage ≥60% / bandit+flake8 / suite overview / contributor notes); EXE output path & roadmap bumped to v1.8.3
  — README.md / README.zh.md：新增「测试」章节（环境 / 运行测试 / 覆盖率 ≥60% / bandit+flake8 / 测试体系表 / 贡献者须知）；EXE 产物路径与路线图对齐 v1.8.3
- CONTRIBUTING.md — add pytest 147-case suite, run_all_tests.py 6-stage orchestrator, and pre-commit hooks; bump build artifact dir to v1.8.3-win64
  — CONTRIBUTING.md：新增 pytest 147 用例、run_all_tests.py 6 阶段编排器、pre-commit 钩子说明；构建产物目录对齐 v1.8.3-win64

### Fixed / 修复

- start_fuzz.bat banner hardcoded v1.8.3 (3 releases behind) → dynamic
  — start_fuzz.bat 横幅硬编码 v1.8.3（落后 3 个版本）→ 改为动态读取
- release.yml prerelease regex \b boundary bug (v1.9.0-rc3 not detected) → removed \b
  — release.yml 预发布正则 \b 边界 bug（无法识别 v1.9.0-rc3）→ 移除 \b
- CI missing pytest-timeout → added to install step
  — CI 缺少 pytest-timeout → 已加入安装步骤
- CI missing black + black --check → added
  — CI 缺少 black 及 black --check → 已补充
- CI missing --cov-fail-under → added with threshold 16%
  — CI 缺少 --cov-fail-under → 已补充，阈值 16%

### Removed / 移除

- IndusFuzz/test/ build artifacts (bandit_report.json + pytest_coverage* HTML)
  — 删除 IndusFuzz/test/ 构建产物（bandit_report.json + pytest_coverage* HTML）

### Verified / 已验证

- check_protocol.py all 7 built-in protocols PASS (modbus / s7comm / dnp3 / iec104 / iec61850 / enip / opcua)
  — check_protocol.py 内置 7 协议全部 PASS
- pytest 147 passed / 0 failed — pytest 147 通过 / 0 失败
- bandit -r src -lll → No issues identified — bandit -r src -lll 无发现问题
- flake8 CI params → 0 errors — flake8 CI 参数 0 报错


## [1.8.0] - 2026-09-19

### Added
- PyInstaller onefile EXE packaging toolchain (IndusFuzz.spec)
- One-click build scripts: build.bat, make_release.bat
- version_info.txt for Windows binary metadata
- verify_build.py for post-packaging validation
- config/connect_templates.yaml — real-device connection parameter templates (7 protocols)

### Changed
- main.py supports --run-slave parameter branch for self-invoking slave startup inside EXE
- slave_launcher.py rewired to Popen sys.executable with --run-slave instead of spawning python subprocess
- src/core/_resource.py added: resource_path() handles both dev and frozen (PyInstaller sys._MEIPASS) modes
- Font loading copies simhei.ttf from sys._MEIPASS to project assets/fonts/ at runtime when packaged

### Fixed
- Windows GBK console UnicodeEncodeError: main.py reconfigures sys.stdout to utf-8
- PyInstaller onefile EXE missing xhtml2pdf submodules causing PDF generation failure (collect_submodules for xhtml2pdf/html5lib/reportlab/six)
- Packaged EXE unable to access PDF Chinese font simhei.ttf due to xhtml2pdf resource policy blocking sys._MEIPASS paths

## [1.7.0] - 2026-09-18

### Added
- 7 industrial protocol support: Modbus TCP, S7Comm, DNP3, IEC 60870-5-104, IEC 61850 MMS, EtherNet/IP, OPC UA
- LLM-driven mutation with local deterministic fallback
- Windows DPAPI encrypted API key storage
- HTTPS enforcement for cloud API
- HTML + PDF report generation with Chinese font support
- Mock slave servers with strict mode for all 7 protocols
- PyInstaller onefile EXE packaging

### Security
- DPAPI encryption for API keys (binding to current Windows user)
- HTTPS-only cloud API URLs
- API key masking in all output
- No hardcoded credentials
- Bandit zero HIGH findings
- HTML escaping for all external text in reports (XSS prevention)

### Changed
- llm_mutator refactored to shared base class (timeout=25, max_retries=0, length validation, None guard)
- Slave launcher uses --run-slave self-invocation mode for EXE compatibility
- Resource path resolution supports both dev and frozen (PyInstaller) modes

## [1.6.0] - 2026-09-16

### Added
- Multi-protocol architecture with plugin registry
- Protocol auto-discovery via func_codes JSON scanning
- check_protocol self-check tool (11 items per protocol)

## [1.5.0] - 2026-09-15

### Added
- Initial Modbus TCP fuzzing support
- Local Ollama + cloud API integration
- Interactive CLI wizard
- HTML report generation

