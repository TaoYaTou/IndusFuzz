# Changelog

All notable changes to IndusFuzz are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [1.8.1] - 2026-09-20

### Added
- pytest test suite: 147 cases across registry / mutator / reporter / security modules
- run_all_tests.py 6-stage test orchestrator with Chinese HTML report generation
- CI workflow test.yml — push/PR trigger: pytest + coverage fail-under=16% + flake8 + black --check + bandit
- CI workflow release.yml — tag v* trigger: test → PyInstaller → portable ZIP → GitHub Release with CHANGELOG notes + auto prerelease detection
- .pre-commit-config.yaml — black / flake8 / bandit hooks (black scoped to tests/ tools/ due to no prior black history)
- src/core/version.py three-source version resolution: INDUSFUZZ_VERSION env → git describe --tags → HARDCODED_VERSION fallback
- tools/verify/ and tools/legacy/ — verification helpers relocated out of tests/

### Changed
- build.ps1 / make_release.bat / start_fuzz.bat all read version dynamically from version.py (single source of truth)
- CI flake8 args fully aligned with pre-commit: --max-line-length=120 --ignore=E501,W503 --select=E9,F63,F7,F82,E231,F401,W292
- black scope limited to tests/ tools/ (src/ has no prior black history; will be reformatted in a dedicated PR)

### Fixed
- start_fuzz.bat banner hardcoded v1.5.0 (3 releases behind) → dynamic
- release.yml prerelease regex \b boundary bug (v1.9.0-rc3 not detected) → removed \b
- CI missing pytest-timeout → added to install step
- CI missing black + black --check → added
- CI missing --cov-fail-under → added with threshold 16%

### Removed
- IndusFuzz/test/ build artifacts (bandit_report.json + pytest_coverage* HTML)

### Verified
- check_protocol.py all 7 built-in protocols PASS (modbus / s7comm / dnp3 / iec104 / iec61850 / enip / opcua)
- pytest 147 passed / 0 failed
- bandit -r src -lll → No issues identified
- flake8 CI params → 0 errors


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

