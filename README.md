<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/English-Currently English-8A2BE2" alt="English"></a>
  <a href="./README.zh.md"><img src="https://img.shields.io/badge/简体中文-Read in Chinese-blue" alt="简体中文"></a>
</p>

<br/>

<pre>
 __  _  ___  ____   __   _ _____ ____ ___   ____  _  _ _____ _____
|  \| ||_  || |    / |  / \_   _| |  |   |_/  || ||_   _|  _  /  |
| ' \ | |_|| |    /  /  / -_\ | | |  |  |  ___ | | |   _| |  |  |
|-__|| ___||_|__/_ /_  \___\|_| |__||__|  /__/|_| |   |_| __| __|
                                                                  
</pre>

<pre>
╔══════════════════════════════════════════════════════════════╗
║  I N D U S F U Z Z  ·  Industrial Protocol Fuzzing Agent      ║
╚══════════════════════════════════════════════════════════════╝
</pre>

<p align="center">
  Place your project logo here (e.g. <code>docs/images/logo.png</code>).
  <br/>
  <em>placeholder, to be replaced</em>
</p>

---

**About the banner/Logo.** The banner above offers two sample styles (ASCII art + boxed title). Draw your own with any vector tool (Figma / Inkscape) and export to PNG/SVG to replace them; or commit the result to `docs/images/` and update the links below.

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Roadmap](#2-roadmap)
3. [Environment Requirements](#3-environment-requirements)
4. [System Compatibility](#4-system-compatibility)
5. [Installation](#5-installation)
6. [Dependencies](#6-dependencies)
7. [Model Configuration](#7-model-configuration)
8. [Supported Models](#8-supported-models)
9. [Quick Start](#9-quick-start)
10. [5-Second Quick Experience](#10-5-second-quick-experience)
11. [Supported Protocols](#11-supported-protocols)
12. [Known Limitations](#12-known-limitations)
13. [Usage Scenarios](#13-usage-scenarios)
14. [Reports](#14-reports)
15. [Project Structure](#15-project-structure)
16. [FAQ](#16-faq)
17. [Disclaimer](#17-disclaimer)
18. [License](#18-license)

---

## Tech Stack

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![Modbus](https://img.shields.io/badge/Modbus-TCP-brightgreen)
![OPC UA](https://img.shields.io/badge/OPC%20UA-4840-blue)
![Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-orange)

---

## 1. Introduction

**IndusFuzz** is an industrial protocol fuzzing agent. It drives protocol-level fuzzing with a local LLM and automatically falls back to local deterministic random mutation when the LLM is unavailable.

- LLM-driven mutation with automatic fallback to local deterministic random mutation
- Local-first: the model runs locally, so payloads never leave your machine
- Interactive command-line wizard, no coding required to run

Supported protocols: **Modbus TCP, S7Comm, DNP3, IEC 60870-5-104, IEC 61850 MMS, EtherNet/IP, OPC UA**; more are expected.

> Security notice: Only use this against systems you are explicitly authorized to test. This tool may cause production equipment to fail.

---

## 2. Roadmap

| Version | Major changes | Status |
|---------|---------------|--------|
| v1.8.0 | MCP integration | Planned |
| v1.9.0 | Desktop app, NVD/CNVD vulnerability comparison | Future |
| v2.0.0 | Cross-platform (macOS/Linux), desktop app, NVD/CNVD vulnerability comparison | Future |

---

## 3. Environment Requirements

| Item | Requirement |
|------|-------------|
| Python | 3.10 or later (64-bit) |
| OS | Windows 10 / 11 (64-bit) |
| Disk | ~1 GB for code and dependencies; pulling local models requires additional space |
| GPU (optional) | NVIDIA GPU + CUDA, only to accelerate local Ollama inference |

No GPU is required. Ollama runs on CPU by default; when using local Ollama, the wizard asks whether to enable GPU acceleration.

---

## 4. System Compatibility

| Feature | Windows 10/11 | macOS | Linux |
|---------|--------------|-------|-------|
| Main flow (fuzzing) | ✅ Tested | ⚠️ Untested | ⚠️ Untested |
| API key encryption | ✅ DPAPI | ❌ Not supported | ❌ Not supported |
| S7Comm | ✅ | ⚠️ libsnap7 needed | ⚠️ libsnap7 needed |
| Auto-open report | ✅ | ⚠️ Unknown | ⚠️ Unknown |
| Default ports 102/502 | ⚠️ Admin required | ⚠️ Needs sudo | ⚠️ Needs sudo |

**Official support:** Windows 10/11 (64-bit) only.

**Untested:** macOS and Linux. Theoretically feasible, but the following issues may occur:
- API key encryption is unavailable (DPAPI is Windows-only); use the "No LLM" mode instead.
- Some ports require administrator privileges.
- Auto-opening reports / directories may fail.

---

## 5. Installation

### Source installation (recommended for developers)

#### Installation by platform

**Windows users** (recommended, tested):
Follow the steps below.

**macOS users** (untested):
1. Install Python 3.10+.
2. Install Homebrew.
3. `brew install snap7` (required for S7Comm).
4. `pip install -r requirements.txt`.
5. Known issue: API key encryption is unavailable; use "No LLM" or a local LLM.

**Linux users** (untested):
1. Install Python 3.10+.
2. `sudo apt install libsnap7-dev` (required for S7Comm).
3. `pip install -r requirements.txt`.
4. Known issues: ports 102/502 require sudo; API key encryption is unavailable.

#### Virtual environment

A virtual environment isolates dependencies so they do not affect your system Python.

- `python -m venv agentscope_env` creates an isolated `agentscope_env/` directory with its own Python and pip.
- After activation, the terminal prompt becomes `(agentscope_env) PS C:\...>`.
- Exit the virtual environment with `deactivate`.
- Delete it by removing the `agentscope_env` directory.
- A virtual environment is preferred over system Python: per-project isolated installs, no version conflicts, and only one directory to delete.

```bash
# 1. Clone the repository
git clone https://github.com/IndusFuzz/indusfuzz.git
cd indusfuzz/fuzz_agent

# 2. Create and activate a virtual environment
python -m venv agentscope_env
.\agentscope_env\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure model source (see the next section)
python main.py
```

> On Windows use `.\agentscope_env\Scripts\activate` (PowerShell: `.ps1`, cmd: `.bat`). If you are a collaborator, replace the git URL with your fork.

### EXE installation (recommended for end users)

**Available from Releases.** Download `IndusFuzz.exe` from the GitHub [Releases](../../releases) page.

### Verify the installation

```bash
python main.py
```

The IndusFuzz banner and interactive wizard appearing means success. Press `q` to exit when prompted.

---

## 6. Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| openai | 3.13.0 | LLM API calls |
| scapy | 2.7.0 | Packet construction / capture |
| pywin32 | 311 | Windows DPAPI encryption |
| pymodbus | 3.15.0 | Modbus protocol |
| reportlab | 5.0.1 | PDF generation |
| asyncua | 2.0.1 | OPC UA protocol |
| python-snap7 | 3.1.2 | S7Comm protocol |
| xhtml2pdf | 0.2.19 | HTML to PDF |

---

## 7. Model Configuration

Only one model source is configured per run (applies globally to all protocols). There are 4 options:

| Option | Use case |
|--------|----------|
| Local Ollama | Recommended. Free and private, model runs locally. GPU can be enabled. |
| Cloud API | DeepSeek / OpenAI / custom cloud. Requires an API key. |
| Custom local model | OpenAI-compatible endpoint of vLLM / LM Studio / LocalAI on LAN. |
| No LLM | Local mutation only. Fully offline, no model needed. |

### Option 1: Local Ollama (recommended)

1. Install and run Ollama.
2. Pull a model, for example:
   ```bash
   ollama pull qwen2.5-coder:14b
   ollama serve
   ```
3. In the wizard choose **Local Ollama**; downloaded models are listed automatically.
4. GPU: when using Ollama, the wizard asks whether to enable GPU acceleration and enables it automatically if a compatible GPU is detected.

### Option 2: Cloud API (DeepSeek / OpenAI)

1. Obtain an API key from your provider.
2. In the wizard choose **Cloud API**, pick a preset (DeepSeek / OpenAI) or a custom endpoint.
3. Enter the API key and Base URL.
4. The API key is stored locally after encryption using Windows DPAPI.
**Cloud API requests are sent to a third party; do not use it in privacy-sensitive environments.**
### Option 3: Custom local model (vLLM / LM Studio / LocalAI)

1. Requires a local service exposing an OpenAI-compatible REST API.
2. In the wizard choose **Custom local model**.
3. Enter the Base URL of the local service, e.g. `http://localhost:1234/v1`.

### Option 4: No LLM

Choose **No LLM** to use local deterministic random mutation directly. No API key or model needed, fully offline.

---

## 8. Supported Models

### Models supported by local Ollama (recommended)

- `qwen2.5-coder:14b` (recommended)
- `qwen2.5-coder:7b` (lightweight)
- `deepseek-coder:6.7b`
- `llama3.1:8b`
- Any other official Ollama model

### Cloud API providers

- DeepSeek (`deepseek-chat`, `deepseek-coder`)
- OpenAI (`gpt-4o`, `gpt-4o-mini`)
- Other OpenAI-compatible endpoints (custom Base URL required)

### Frameworks supported as custom local models

- vLLM
- LM Studio
- LocalAI
- Other OpenAI-compatible services

---

## 9. Quick Start

1. **Start**: `python main.py` or `start_fuzz.bat` or `IndusFuzz.exe`
2. **Follow the wizard**: choose model source, scenario, protocols, function codes, targets, timeout.
3. **After the run**, open the reports in the `reports/` directory.

---

## 10. 5-Second Quick Experience

```bash
cd fuzz_agent
python main.py
```

Choose **local self-test (本机自测)**, pick any protocol and a few function codes, and keep the default target. At the confirmation step press `L` to switch the mock slave to **strict** mode (default), then enter `y` to start. The built-in slave auto-starts, and a HTML report is generated in `reports/` after the fuzzing run.

---

## 11. Supported Protocols

| Protocol | Default Port | Typical Devices | Built-in Mock Slave |
|----------|--------------|-----------------|---------------------|
| Modbus TCP | 5020 | PLC, RTU, VFD | Yes |
| S7Comm | 10102 | Siemens S7 PLC | Yes |
| DNP3 | 20000 | RTU, IED (power) | Yes |
| IEC 60870-5-104 | 2404 | Substation SCADA telecontrol | Yes |
| IEC 61850 MMS | 102 | Substation IED, bay controller | Yes |
| EtherNet/IP | 44818 | Rockwell / Allen-Bradley controllers | Yes |
| OPC UA | 4840 | Industrial gateway, HMI, server | Yes |

Typical use cases:

- **Modbus TCP** — the most common industrial transport protocol; prioritize PLC, RTU, VFD testing first.
- **S7Comm** — Siemens SIMATIC S7 controllers; a proprietary protocol over ISO/COTP.
- **DNP3** — RTUs and IEDs in power-industry SCADA.
- **IEC 60870-5-104** — TCP telecontrol for grid dispatch / SCADA.
- **IEC 61850 MMS** — IED communication in digital substations based on MMS/ASN.1.
- **EtherNet/IP / CIP** — Rockwell control systems and common industrial Ethernet devices.
- **OPC UA** — the interoperability layer between gateways, HMIs, historians and field servers.

---

## 12. Known Limitations

| ID | Protocol | Note |
|----|----------|------|
| P2-006 | OPC UA | The OPC UA implementation uses a **custom frame format** and may not be compatible with standard servers. |
| P2-011 | S7Comm | The S7Comm mock slave uses a **custom frame format** (non-standard port). |
| P2-016 | All (6 servers) | Servers assume a single `recv` returns a complete frame; TCP fragmentation/coalescing is not handled. |
| P2-017 | MCP integration | The 3 MCP integrations (`codeinspectus_mcp`, `codeguard_mcp`, `vulnclaw_mcp`) are still stubs, under development. |
| R5-7 | Error report | `_summarize_suggestions` and `generate_error_report` are currently only called by test scripts; main-flow integration is pending v1.8.0. |

---

## 13. Usage Scenarios

### Scenario 1: Local self-test

- Choose scenario **local self-test**. The built-in mock slave auto-starts in **strict** mode.
- At the confirmation step press `L` to switch between strict/loose modes, then view the report after the run.

### Scenario 2: LAN testing (LAN devices)

- Specify a LAN device as the target by `IP:port`.
- Make sure you have obtained testing authorization.

### Scenario 3: Real devices

- Requires explicit testing authorization. It is recommended to validate the tool in a local self-test environment before touching production devices.

---

## 14. Reports

Reports are saved in the `reports/` directory:

| File | Use |
|------|-----|
| `report_<timestamp>.html` | Open in a browser |
| `report_<timestamp>.pdf` | Print or share |
| `run.log` | Raw run log |

Reports contain: statistical summary, risk grading, anomaly distribution, function-code statistics. When a protocol's fuzzing is force-terminated due to the overall timeout, a corresponding notice banner is shown at the top of the report.

---

## 15. Project Structure

```
fuzz_agent/
├── main.py                      # Entry: banner, environment check, wizard, start slave, fuzzing
├── requirements.txt             # Python dependencies
├── src/
│   ├── core/
│   │   ├── version.py           # Single source of truth for the version number
│   │   ├── menu.py              # 6-step interactive wizard
│   │   ├── fuzz_loop_llm.py     # Fuzz orchestration, LLM precheck, timeout circuit breaker, error report
│   │   ├── llm_precheck.py      # LLM connectivity precheck + protocol timeout circuit breaker
│   │   ├── llm_status.py        # Per-protocol LLM call status collection
│   │   ├── report_generator.py  # HTML/PDF/LOG report generation
│   │   ├── result_analyzer.py   # Result statistics
│   │   ├── slave_launcher.py    # Start/stop mock slave in background
│   │   ├── diagnose.py          # Connectivity diagnosis
│   │   ├── security.py          # Windows DPAPI encrypted storage of API key
│   │   ├── runtime_config.py    # Global runtime switches (e.g. GPU)
│   │   └── gpu_detector.py      # GPU detection (nvidia-smi / torch)
│   ├── protocols/               # Protocol plugins
│   │   ├── registry.py          # Plugin registry
│   │   ├── base.py              # ProtocolBase abstract base class
│   │   ├── func_codes/*.json    # Function-code definitions per protocol
│   │   └── {modbus,s7comm,dnp3,iec104,iec61850,enip,opcua}/
│   │       ├── __init__.py      # register_protocol
│   │       ├── client.py        # Client, packet construction, classification, run_fuzz
│   │       ├── mutator.py       # Local deterministic mutation
│   │       └── llm_mutator.py   # LLM mutation (OpenAI-compatible)
│   └── integrations/            # MCP integrations (stub files under development)
├── server/                      # Mock slaves for all 7 protocols
├── tools/check_protocol.py      # Protocol integrity self-check
├── tests/verify_*.py            # Verification scripts
└── reports/                     # Generated reports
```

---

## 16. FAQ

**The server connection failed, what should I do?**
Check whether the target `IP:port` is reachable, whether the port is occupied (e.g. `netstat -ano | findstr port`), and whether the environment and dependencies are installed. The wizard shows troubleshooting hints on failure.

**Ollama is not installed / I do not want to use a cloud model, how do I configure it?**
Choose **No LLM** at the model step. IndusFuzz falls back to local deterministic mutation when no model is configured.

**What is the difference between a custom local model and a cloud API?**
A custom local model points to an OpenAI-compatible service on your machine/LAN (`http://localhost:1234/v1`); data does not leave the machine. A cloud API sends requests to a third party; do not use it in sensitive scenarios.

**Why is the report full of NORMAL results?**
When the mock slave is in **loose** mode (always returns a fixed response) or the target does not respond to malformed frames, a high NORMAL ratio is normal. In **strict** mode the slave validates frames and returns exceptions or drops connections for invalid frames.

**The port is occupied, how do I handle it?**
Change the port, or free the occupied port. In local mode, the wizard can auto-assign an available port if the default one is busy.

**Which model should I choose?**
For local self-test, local Ollama is recommended (privacy, offline). Use a cloud API only when you need stronger LLM capability and accept offloading payloads.

**Can I use it on macOS/Linux?**
v1.7.0 officially supports Windows 10/11 only. macOS/Linux are theoretically possible but not fully tested; the following issues may exist:
- API key encryption is unavailable
- some ports require administrator privileges
- auto-opening reports may fail
Use it on Windows, or wait for the v2.0 cross-platform version.

**Why is it Windows-only?**
Because v1.7.0 uses the Windows-specific DPAPI to encrypt the API key. v2.0 plans to replace it with the cross-platform `keyring` library, adding macOS and Linux support.

---

## 17. Disclaimer

- This tool is for **authorized security testing only**.
- **Do not** run it on unauthorized production devices.
- Users are solely responsible for all legal liability arising from unauthorized testing.
- Fuzzing sends malformed frames that may cause industrial equipment failure, production line shutdowns, or safety incidents.

---

## 18. License

Licensed under the **Apache License 2.0**. See the `LICENSE` file for the full text.