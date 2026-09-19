<p align="center">
  <a href="./README.md"><img src="https://img.shields.io/badge/English-Read in English-8A2BE2" alt="English"></a>
  <a href="./README.zh.md"><img src="https://img.shields.io/badge/简体中文-当前为中文版-blue" alt="简体中文"></a>
</p>

<br />

<pre>
 __  _  ___  ____   __   _ _____ ____ ___   ____  _  _ _____ _____
|  \| ||_  || |    / |  / \_   _| |  |   |_/  || ||_   _|  _  /  |
| ' \ | |_|| |    /  /  / -_\ | | |  |  |  ___ | | |   _| |  |  |
|-__|| ___||_|__/_ /_  \___\|_| |__||__|  /__/|_| |   |_| __| __|
                                                                  
</pre>

<pre>
╔══════════════════════════════════════════════════════════════╗
║  I N D U S F U Z Z  ·  工业协议模糊测试智能体                  ║
╚══════════════════════════════════════════════════════════════╝
</pre>

<p align="center">
  <img src="assets/concept_a_hex/icon_512.png" alt="IndusFuzz Logo" width="128" height="128">
</p>

***

## 目录

1. [项目简介](#1-项目简介)
2. [背景与设计](#2-背景与设计)
3. [路线图](#3-路线图)
4. [环境要求](#4-环境要求)
5. [系统兼容性](#5-系统兼容性)
6. [如何安装](#6-安装)
7. [依赖清单](#7-依赖清单)
8. [模型配置](#8-模型配置)
9. [支持的模型](#9-支持的模型)
10. [快速开始](#10-快速开始)
11. [支持的协议](#11-支持的协议)
12. [已知限制](#12-已知限制)
13. [使用说明](#13-使用说明)
14. [真实设备测试指南](#14-真实设备测试指南)
15. [报告说明](#15-报告说明)
16. [项目结构](#16-项目结构)
17. [常见问题](#17-常见问题)
18. [免责声明](#18-免责声明)
19. [开源协议](#19-开源协议)

***

## 1. 项目简介

**IndusFuzz** 是一个工业协议模糊测试智能体。它用本地 LLM 驱动协议级模糊测试，当 LLM 不可用时自动回退到本地确定性随机变异。

- LLM 驱动变异，自动回退到本地确定性随机变异

- 本地优先：模型在本地运行，报文不离开本机

- 交互式命令行向导，无需编写代码即可运行

支持的协议：**Modbus TCP、S7Comm、DNP3、IEC 60870-5-104、IEC 61850 MMS、EtherNet/IP、OPC UA**，预期继续增加

> 安全提示：仅可在你明确获授权测试的系统中使用。本工具可能导致生产设备故障。

***

## 2. 背景与设计

### 2.1 为什么要做工业协议模糊测试

工业控制系统（ICS）协议（如 Modbus、S7Comm、IEC 61850）在设计之初几乎不考虑安全性，只追求功能性与实时性，因而产生了大量真实世界漏洞：

- **CVE-2026-44107**：攻击者可借 Modbus TCP 在无认证情况下触发充电控制器重启，造成拒绝服务。

- **CVE-2026-4436**：低权限远程攻击者可通过 Modbus 报文操纵寄存器值，导致天然气管道加臭剂注入过多或过少。

- **Delta DVP12SE PLC**：Modbus TCP 服务无认证、无访问控制，允许未授权交互。

- **OpenPLC\_v3**：Modbus 主机侧代码存在堆缓冲区溢出漏洞。

### 2.2 传统模糊测试的痛点

- 依赖专家经验，耗时长

- 覆盖不全，难以适应私有协议

- 人工分析响应、判断异常效率低

- 无法快速生成多样化的测试用例

### 2.3 设计演进

PRD 早期设想为「多智能体协作（种子生成 / 测试用例生成 / 反馈分析）+ AgentScope + RAG + Flask Web」的完整框架。工程落地时我们收敛了架构，采用 **LLM 驱动变异 + 本地确定性回退**：LLM 负责生成语义化变异，LLM 不可用时自动回退到本地确定性随机变异。该路径已获得验证，可参考学术界 MALF 框架（多智能体 LLM 模糊测试，Qwen2.5-14B，Modbus/TCP 上 88–92% 测试用例通过率）。

### 2.4 隐私与本地化承诺

默认全程使用本地 Ollama，数据不出电脑，避免云端泄露。云端 API 请求会发送到第三方，隐私场景请勿使用。

### 2.5 成功标准

- **最小可行**：自动生成并发送 Modbus 变异用例，检测到异常响应。

- **合格**：本地 LLM 变异 + 异常检测 + 可复现测试报告。

- **优秀**：支持多种工业协议，成为高危工业设备的可信安全工具。

***

## 3. 路线图

| 版本     | 主要变更                                                      | 状态      |
| ------ | --------------------------------------------------------- | ------- |
| v1.8.1 | 测试体系 + CI/CD（147 项 pytest、test/release 工作流、pre-commit、动态版本）                | 已完成（当前） |
| v2.0.0 | 跨平台支持（macOS/Linux）、桌面端、NVD/CNVD 比对                        | 远期      |

***

## 4. 环境要求

| 项目      | 要求                                 |
| ------- | ---------------------------------- |
| Python  | 3.10 及以上（64 位）                     |
| 操作系统    | Windows 10 / 11（64 位）              |
| 磁盘空间    | 代码与依赖约 1 GB；拉取本地模型另计               |
| GPU（可选） | NVIDIA 显卡 + CUDA，仅用于加速本地 Ollama 推理 |

Ollama 默认在 CPU 上运行；使用本地 Ollama 时向导会询问是否启用 GPU 加速。

***

## 5. 系统兼容性

| 功能           | Windows 10/11 | macOS          | Linux          |
| ------------ | ------------- | -------------- | -------------- |
| 主流程（模糊测试）    | ✅ 已测试         | ⚠️ 未测试         | ⚠️ 未测试         |
| API Key 加密存储 | ✅ DPAPI       | ❌ 不支持          | ❌ 不支持          |
| S7Comm 协议    | ✅             | ⚠️ 需装 libsnap7 | ⚠️ 需装 libsnap7 |
| 自动打开报告       | ✅             | ⚠️未知           | ⚠️未知           |
| 默认端口 102/502 | ⚠️ 需管理员权限     | ⚠️ 需 sudo      | ⚠️ 需 sudo      |

**官方支持**：仅 Windows 10/11（64 位）。

**未测试**：macOS、Linux。理论可行，但可能存在以下问题：

- API Key 无法加密存储（DPAPI 是 Windows 专用），需改用"不用 LLM"模式

- 部分端口需要管理员权限

- 自动打开报告/目录可能失效

***

## 6. 如何安装？

### 源码安装（推荐开发者）

#### 按平台安装

**Windows 用户**（推荐，已测试）：
按下文步骤安装即可。

**macOS 用户**（未测试）：

1. 安装 Python 3.10+
2. 安装 Homebrew
3. `brew install snap7`（S7Comm 需要）
4. `pip install -r requirements.txt`
5. 已知问题：API Key 加密不可用，需用"不用 LLM或本地LLM"模式

**Linux 用户**（未测试）：

1. 安装 Python 3.10+
2. `sudo apt install libsnap7-dev`（S7Comm 需要）
3. `pip install -r requirements.txt`
4. 已知问题：端口 102/502 需要 sudo，API Key 加密不可用

#### 虚拟环境

虚拟环境用于隔离依赖，避免影响系统 Python。

- `python -m venv agentscope_env` 会创建独立的 `agentscope_env/` 目录，包含自己的 Python 和 pip。

- 激活后，终端提示符会变成 `(agentscope_env) PS C:\...>`。

- 退出虚拟环境用 `deactivate`。

- 删除虚拟环境：直接删除 `agentscope_env` 目录即可。

- 推荐用虚拟环境而非系统 Python：按项目隔离安装、避免版本冲突、删除时只需删一个目录。

```bash
# 1. 克隆仓库
git clone https://github.com/TaoYaTou/IndusFuzz.git
cd IndusFuzz/fuzz_agent

# 2. 创建并激活虚拟环境
python -m venv agentscope_env
.\agentscope_env\Scripts\activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置模型来源（见下一节）
python main.py
```

> Windows 下用 `.\agentscope_env\Scripts\activate` 激活虚拟环境（PowerShell 用 .ps1，cmd 用 .bat）。若是协作开发者，请将 git 地址替换为你的 fork。

### EXE 安装（推荐普通用户）

**可从 Releases 获取。** 从 GitHub [Releases](../../releases) 页面下载 `IndusFuzz.exe`；也可用打包工具链本地构建（产物见 `IndusFuzz-v1.8.1-win64\IndusFuzz.exe`）。

### 验证安装是否成功

```bash
python main.py
```

出现 IndusFuzz 横幅并进入交互向导即成功。按提示输入 `q` 退出。

***

## 7. 依赖清单

| 包名           | 版本     | 用途               |
| ------------ | ------ | ---------------- |
| openai       | 3.13.0 | LLM API 调用       |
| scapy        | 2.7.0  | 报文构造/捕获          |
| pywin32      | 311    | Windows DPAPI 加密 |
| pymodbus     | 3.15.0 | Modbus 协议        |
| reportlab    | 5.0.1  | PDF 生成           |
| asyncua      | 2.0.1  | OPC UA 协议        |
| python-snap7 | 3.1.2  | S7Comm 协议        |
| xhtml2pdf    | 0.2.19 | HTML 转 PDF       |

***

## 8. 模型配置

每次运行只需配置一个模型来源（对所有协议全局生效）。共 4 种：

| 选项        | 适用场景                                           |
| --------- | ---------------------------------------------- |
| 本地 Ollama | 推荐。免费、隐私，模型本地运行。可启用 GPU。                       |
| 云端 API    | DeepSeek / OpenAI / 自定义云端。需要 API Key。          |
| 自定义本地模型   | 局域网内 vLLM / LM Studio / LocalAI 的 OpenAI 兼容接口。 |
| 不用 LLM    | 仅本地变异。全离线，无需模型。                                |

### 方式一：本地 Ollama（推荐）

1. 安装并运行 Ollama。
2. 拉取模型，例如：

   ```bash
   ollama pull qwen2.5-coder:14b
   ollama serve
   ```
3. 在向导中选择 **本地 Ollama**，会自动列出已下载的模型。
4. GPU：使用 Ollama 时，向导会询问是否启用 GPU 加速，检测到兼容显卡后自动启用。

### 方式二：云端 API（DeepSeek / OpenAI）

1. 从服务商获取 API Key。
2. 在向导中选择 **云端 API**，选择预设（DeepSeek / OpenAI）或自定义地址。
3. 填写 API Key 与 Base URL。
4. API Key 使用 Windows DPAPI 加密后存入本地配置，但**云端API数据会发送给第三方，隐私环境切勿使用**

### 方式三：自定义本地模型（vLLM / LM Studio / LocalAI）

1. 需要一个提供 OpenAI 兼容 REST 接口的本地服务。
2. 在向导中选择 **自定义本地模型**。
3. 填写本地服务的 Base URL，例如 `http://localhost:1234/v1`。

### 方式四：不用 LLM

选择 **不用 LLM**，直接使用本地确定性随机变异。无需 API Key 和模型，完全离线。

***

## 9. 支持的模型

### 本地 Ollama 支持的模型（建议）

- `qwen2.5-coder:14b`（推荐）

- `qwen2.5-coder:7b`（轻量）

- `deepseek-coder:6.7b`

- `llama3.1:8b`

- 其他 Ollama 官方模型均可

### 云端 API 支持的提供商

- DeepSeek（`deepseek-chat`、`deepseek-coder`）

- OpenAI（`gpt-4o`、`gpt-4o-mini`）

- 其他 OpenAI 兼容接口（需自定义 Base URL）

### 自定义本地模型支持的框架

- vLLM

- LM Studio

- LocalAI

- 其他 OpenAI 兼容服务

***

## 10. 快速开始

1. **启动**：`python main.py`或`start_fuzz.bat`或`IndusFuzz.exe`
2. **按向导操作**：依次选择模型来源、场景、协议、功能码、目标地址、超时。
3. **测试完成后**：打开 `reports/` 目录下的报告。

***

## 11. 支持的协议

| 协议              | 默认端口  | 典型设备            | 内置模拟从站 |
| --------------- | ----- | --------------- | ------ |
| Modbus TCP      | 5020  | PLC、RTU、变频器     | 有      |
| S7Comm          | 10102 | 西门子 S7 PLC      | 有      |
| DNP3            | 20000 | RTU、IED（电力）     | 有      |
| IEC 60870-5-104 | 2404  | 变电站远动（SCADA）    | 有      |
| IEC 61850 MMS   | 102   | 变电站 IED、间隔控制器   | 有      |
| EtherNet/IP     | 44818 | 罗克韦尔/艾伦-布拉德利控制器 | 有      |
| OPC UA          | 4840  | 工业网关、HMI、服务器    | 有      |

预期继续增加新协议

典型应用场景：

- **Modbus TCP** — 最常见的工业传输协议，优先用于 PLC、RTU、变频器测试。

- **S7Comm** — 西门子 SIMATIC S7 控制器，ISO/COTP 层的私有协议。

- **DNP3** — 电力行业 SCADA 的 RTU 与 IED。

- **IEC 60870-5-104** — 电网调度/SCADA 的 TCP 远动控制。

- **IEC 61850 MMS** — 数字化变电站基于 MMS/ASN.1 的 IED 通信。

- **EtherNet/IP / CIP** — 罗克韦尔控制系统及常见工业以太网设备。

- **OPC UA** — 网关、HMI、历史库与现场服务器之间的互操作层。

***

## 12. 已知限制

| 编号     | 协议             | 说明                                                                              |
| ------ | -------------- | ------------------------------------------------------------------------------- |
| P2-006 | OPC UA         | OPC UA 实现基于**自定义帧格式**，可能与标准服务器不兼容。                                              |
| P2-011 | S7Comm         | S7Comm 模拟从站使用**自定义帧格式**（非标准端口）。                                                 |
| P2-016 | 全部（6 个 server） | 从站假定单次 `recv` 即可收到一帧完整报文，不处理 TCP 分片/粘包重组的报文。                                    |
| P2-017 | MCP 集成         | 3 个 MCP 集成（`codeinspectus_mcp`、`codeguard_mcp`、`vulnclaw_mcp`）仍为桩，开发中。          |
| R5-7   | 错误报告           | `_summarize_suggestions` 和 `generate_error_report` 目前仅被测试脚本调用，主流程集成待 v1.8.0 完成。 |

***

## 13. 使用说明

### 场景一：本机自测（local）

- 选择场景 **本机自测**。内置模拟从站在**严格**模式下自动启动。

- 在确认步骤可按 `L` 切换严格/宽松模式，运行后查看报告。

### 场景二：局域网测试（局域网设备）

- 按 `IP:端口` 指定局域网设备为目标。

- 请确保已获得测试授权。

### 场景三：真实设备测试（真实工业设备）

- 需要明确的测试授权。建议先在本机自测环境验证工具，再接触生产设备。

***

## 14. 真实设备测试指南

### 14.1 前置条件

在对真实工业设备执行模糊测试前，必须满足以下全部条件：

- [ ] 已获得设备所有者的**书面授权**

- [ ] 测试网络与生产网络**物理隔离**

- [ ] 已准备**紧急停止方案**（断电、急停按钮、网络断开）

- [ ] 测试设备**不涉及安全仪表系统（SIS）**

- [ ] 测试时间窗口已获运维团队批准

**平台要求**：真实设备测试功能目前仅在 Windows 10/11 上验证。macOS/Linux 用户连接真实设备时，部分协议握手可能因系统库差异（如 libsnap7 版本）而失败。

> ⚠️ 模糊测试会向设备发送畸形报文，可能导致设备崩溃、产线停摆甚至安全事故。未满足上述条件时严禁使用 lan / production 场景。

### 14.2 各协议连接参数

| 协议              | 必填参数                          | 默认值            | 说明                                        |
| --------------- | ----------------------------- | -------------- | ----------------------------------------- |
| Modbus TCP      | 设备 IP、端口、Unit ID              | 502 / 1        | Unit ID 范围 1-255，部分设备用 255                |
| S7Comm          | 设备 IP、端口、Rack、Slot            | 102 / 0 / 1    | S7-300/400 常用 Slot 2 或 3，S7-1200/1500 用 1 |
| DNP3            | 设备 IP、端口、Master/Outstation 地址 | 20000 / 1 / 10 | 主从地址需与设备配置匹配                              |
| IEC 60870-5-104 | 设备 IP、端口、Common Address       | 2404 / 1       | 公共地址需与设备一致                                |
| IEC 61850 MMS   | 设备 IP、端口、IED 引用               | 102 / （自动发现）   | IED 引用可选，留空自动发现                           |
| EtherNet/IP     | 设备 IP、端口、CPU 槽号               | 44818 / 0      | 槽号默认 0                                    |
| OPC UA          | Endpoint URL、安全策略             | 4840 / None    | Endpoint 格式 `opc.tcp://IP:端口`             |

### 14.3 各协议设备兼容性

| 协议          | 支持设备                     | 特殊要求                                     |
| ----------- | ------------------------ | ---------------------------------------- |
| Modbus TCP  | 通用 PLC / RTU / 网关        | 部分设备需 Unit ID 255                        |
| S7Comm      | 西门子 S7-300/400/1200/1500 | S7-1200/1500 需在 TIA Portal 开启 PUT/GET 通信 |
| DNP3        | 电力 RTU / IED             | 主从地址需与设备配置匹配                             |
| IEC 104     | 变电站 RTU / 调度主站           | Common Address 需与设备一致                    |
| IEC 61850   | 数字化变电站 IED（保护/测控）        | 需 IED 引用或自动发现                            |
| EtherNet/IP | 罗克韦尔 Logix / 施耐德 Modicon | 槽号默认 0                                   |
| OPC UA      | 工业网关 / OPC UA 服务器        | Endpoint URL 必须完整                        |

### 14.4 连接失败排查

| 错误                    | 原因           | 处理                           |
| --------------------- | ------------ | ---------------------------- |
| Connection refused    | 端口未开放或 IP 错误 | 检查设备 IP 和端口是否正确              |
| Timeout               | 网络不通或设备未响应   | 检查网络连接，尝试 `ping` 设备          |
| Authentication failed | 权限不足         | S7-1200/1500 检查 PUT/GET 设置   |
| Handshake failed      | 握手参数不匹配      | 检查 Rack / Slot / Address 等参数 |

### 14.5 测试流程建议

1. **连通性验证**：先用简单读写报文确认设备可达且参数正确
2. **低频模糊测试**：一次发送少量报文（5-10 条），观察设备响应
3. **观察设备日志**：确认设备无异常、无崩溃、无告警
4. **逐步增加强度**：在确认安全的前提下，逐步增加报文数量和变异幅度

### 14.6 生产环境注意事项

- **严禁**在产线运行期间进行测试

- 提前告知设备运维人员测试时间窗口

- 准备好设备重启和恢复方案

- 测试过程中全程监控设备状态

- 一旦出现异常，立即停止测试并断开网络

***

## 15. 报告说明

报告保存在 `reports/` 目录：

| 文件                  | 用途     |
| ------------------- | ------ |
| `report_<时间戳>.html` | 用浏览器打开 |
| `report_<时间戳>.pdf`  | 打印或分享  |
| `run.log`           | 原始运行日志 |

报告包含：统计摘要、风险分级、异常分布、功能码统计。当某协议的模糊测试因整体超时被强制终止时，报告顶部会显示相应的提示横幅。

***

## 测试

本项目使用 pytest 作为测试框架，覆盖协议注册、变异逻辑、报告生成、安全模块四大核心部分。

### 环境准备

安装测试依赖：

```bash
pip install pytest pytest-cov bandit flake8
```

> 测试依赖仅在开发时需要，运行 IndusFuzz 本身不需要安装这些（运行依赖见「依赖清单」）。

### 运行测试

运行全部测试：

```bash
cd /d/Application/AllToolsSet/AgnetPrograms/IndusFuzz/fuzz_agent
pytest tests/ -v
```

运行单个测试文件：

```bash
pytest tests/test_registry.py -v
pytest tests/test_mutator.py -v
pytest tests/test_reporter.py -v
pytest tests/test_security.py -v
```

运行单个测试函数：

```bash
pytest tests/test_security.py -k "test_encrypt" -v
```

查看详细输出（含每个用例的耗时与临时目录）：

```bash
pytest tests/ -v --tb=short
```

### 测试覆盖率

生成覆盖率报告：

```bash
pytest --cov=src tests/
```

产出的 HTML 覆盖率报告默认写入 `htmlcov/` 目录，用浏览器打开 `htmlcov/index.html` 即可查看每个模块的覆盖情况。

当前覆盖率目标为 **≥ 60%**，低于该阈值即视为未通过，新增/修改代码不得拉低覆盖率。

### 代码质量检查

Bandit 安全扫描：

```bash
bandit -r src -lll
```

flake8 风格检查：

```bash
flake8 src/ tests/
```

安全基线要求 **Bandit 零 HIGH 级别问题**，存在任一 HIGH 即不得合并进主分支。

### 测试体系说明

| 测试文件         | 覆盖模块                        | 主要测试内容                               |
| -------------- | ----------------------------- | ---------------------------------------- |
| test_registry.py | src/protocols/registry.py     | 协议注册、查找、列举                        |
| test_mutator.py  | src/protocols/*/mutator.py    | 7 个协议的变异逻辑、边界条件                                    |
| test_reporter.py | src/core/report_generator.py  | 报告生成、双语切换、PDF 输出                |
| test_security.py | src/core/security.py          | API Key 加密、HTTPS 校验、打码              |

### 贡献者须知

- **提 PR 前必须**：对受影响协议跑通 `python tools/check_protocol.py <协议名>`（11/11），并确保 `pytest tests/` 全部通过。
- **新功能必须加测试**：任何新增/修改的模块都必须配套对应的 pytest 用例，否则 PR 不通过。
- **测试覆盖率不能下降**：提交的改动不得使整体覆盖率低于 60%，也不得降低现有覆盖行。

***

## 16. 项目结构

```
fuzz_agent/
├── main.py                      # 入口：横幅、环境检查、向导、启动从站、模糊测试
├── requirements.txt             # Python 依赖
├── start_fuzz.bat               # 一键启动脚本
├── CHANGELOG.md                 # 版本发布历史
├── IndusFuzz.spec               # PyInstaller 打包配置（当前）
├── version_info.txt             # 打包 EXE 的版本元数据
├── verify_build.py              # 构建校验脚本
├── build.bat                    # 打包/构建脚本
├── make_release.bat             # 发布包组装脚本
├── build/                       # PyInstaller 中间构建产物
├── dist/                        # PyInstaller 输出（IndusFuzz.exe）
├── assets/
│   ├── fonts/simhei.ttf         # PDF 渲染用中文字体
│   └── concept_a_hex/           # 应用 Logo 图标（icon_128/256/512.png、icon.ico、icon.svg 等）
├── src/
│   ├── core/
│   │   ├── version.py           # 版本号的唯一来源
│   │   ├── menu.py              # 6 步交互向导
│   │   ├── fuzz_loop_llm.py     # 模糊测试编排、LLM 预检、超时熔断、错误报告
│   │   ├── llm_precheck.py      # LLM 连通性预检 + 协议超时熔断
│   │   ├── llm_status.py        # 每协议 LLM 调用状态收集
│   │   ├── report_generator.py  # HTML/PDF/LOG 报告生成
│   │   ├── result_analyzer.py   # 结果统计
│   │   ├── slave_launcher.py    # 后台启动/停止模拟从站
│   │   ├── diagnose.py          # 连通性诊断
│   │   ├── security.py          # Windows DPAPI 加密存储 API Key
│   │   ├── runtime_config.py    # 全局运行时开关（如 GPU）
│   │   ├── gpu_detector.py      # GPU 检测（nvidia-smi / torch）
│   │   └── color_output.py      # ANSI 彩色输出（Windows VT 降级）
│   ├── protocols/               # 协议插件
│   │   ├── registry.py          # 插件注册表
│   │   ├── base.py              # ProtocolBase 抽象基类
│   │   ├── llm_mutator_base.py  # LLM 变异基类（timeout/retry/错误分类/长度校验/None 防护统一收敛）
│   │   ├── func_codes/*.json    # 各协议功能码定义（7 个）
│   │   └── {modbus,s7comm,dnp3,iec104,iec61850,enip,opcua}/
│   │       ├── __init__.py      # register_protocol
│   │       ├── client.py        # 客户端、报文构造、分类、run_fuzz
│   │       ├── mutator.py       # 本地确定性变异
│   │       └── llm_mutator.py   # LLM 变异薄壳（委托给 llm_mutator_base）
│   │       （modbus 协议额外含 modbus_tools.py，基于 scapy 构造 Modbus 请求）
│   └── integrations/            # MCP 集成（开发中桩文件）
│       ├── vulnclaw_mcp.py
│       ├── codeguard_mcp.py
│       └── codeinspectus_mcp.py
├── config/
│   ├── __init__.py
│   └── connect_templates.yaml   # 真实设备连接参数模板（7 协议，对应 menu.py PROTOCOL_CONNECT_PARAMS）
├── server/                      # 全部 7 个协议的模拟从站（*_server.py，支持 --host --port --strict）
├── tools/
│   ├── check_protocol.py        # 协议完整性自检
│   └── clean_before_release.py  # 发布前清理临时/报告文件
├── tests/
│   ├── verify_*.py              # 验证脚本（fuzz_flow、phase7_static、strict_wiring、gpu 等）
│   ├── test_*.py                # 单元测试（mutator、reporter、tools）
│   ├── fuzz_loop.py             # fuzz 循环测试入口
│   └── legacy/                  # 遗留测试脚本
├── docs/                        # PRD 文档（协议扩展/审计/审计修复总结，共 3 份）
└── reports/                     # 生成的报告
```

***

## 17. 常见问题

**服务器连接失败怎么办？**
检查目标 `IP:端口` 是否可达、端口是否被占用（如 `netstat -ano | findstr 端口`）、环境与依赖是否安装。向导在失败时会给出排查提示。

**Ollama 未安装 / 不想用云端模型怎么配置？**
在模型步骤选择 **不用 LLM**。IndusFuzz 会在未配置模型时回退到本地确定性变异。

**自定义本地模型和云端 API 有什么区别？**
自定义本地模型指向本机/局域网内的 OpenAI 兼容服务（`http://localhost:1234/v1`），数据不离开本机，隐私保密；云端 API 会把请求发送到第三方，敏感场景请勿使用。

**报告里全是 NORMAL 是什么原因？**
当模拟从站处于**宽松**模式（始终返回固定响应），或目标对畸形帧不做响应时，NORMAL 占比高属正常现象。**严格**模式下从站会校验帧，对非法帧返回异常或断开连接。

**端口被占用怎么处理？**
更换端口，或释放被占用的端口。本机模式下，若默认端口被占用，向导可自动分配可用端口。

**选择哪个模型合适？**
本机自测推荐本地 Ollama（隐私、离线）。只有当你需要更强的 LLM 能力且能接受报文出网时才用云端 API。

**我在 macOS/Linux 上能用吗？**
v1.8.0 官方只支持 Windows 10/11。macOS/Linux 理论可行，但未经过完整测试，可能存在以下问题：

- API Key 无法加密存储

- 部分端口需要管理员权限

- 自动打开报告可能失效
  建议在 Windows 环境使用，或等待 v2.0 跨平台版本。

**为什么只支持 Windows？**
因为 v1.8.0 使用了 Windows 专用的 DPAPI 加密 API Key。v2.0 计划用跨平台的 keyring 库替代，届时将支持 macOS 和 Linux。

***

## 18. 免责声明

- 本工具**仅用于授权的安全测试**。

- **禁止**在未授权的生产设备上运行。

- 使用者需自行承担因未授权测试产生的全部法律责任。

- 模糊测试会发送畸形帧，可能导致工业设备故障、产线停摆或安全事故。

***

## 19. 开源协议

本项目采用 **Apache License 2.0** 开源。完整条款见 `LICENSE` 文件。
