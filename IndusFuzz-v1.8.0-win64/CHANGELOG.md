# Changelog

All notable changes to IndusFuzz are documented in this file.

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
