# Contributing to IndusFuzz

感谢你愿意为 IndusFuzz 做出贡献。本文档描述了贡献流程与项目约定。

## 开发环境搭建

### 前置条件

| 工具 | 要求 |
|------|------|
| Python | 3.10+（64 位） |
| 操作系统 | Windows 10/11（64 位），官方支持 |
| Git | 任意版本 |
| Ollama（可选） | 用于本地 LLM 推理 |

### 安装步骤

```bash
# 1. 克隆仓库
git clone https://github.com/TaoYaTou/IndusFuzz.git
cd IndusFuzz

# 2. 创建并激活虚拟环境
python -m venv agentscope_env
.\agentscope_env\Scripts\activate   # PowerShell / cmd
# source agentscope_env/bin/activate   # macOS / Linux

# 3. 安装依赖
pip install -r requirements.txt

# 4. （可选）安装开发工具
pip install pytest bandit

# 5. 启动验证
python main.py
```

看到 IndusFuzz 横幅并进入交互向导即安装成功。

### 目录结构

```
IndusFuzz/                 # 项目根（README、LICENSE、一键脚本）
├── src/                   # 核心代码
│   ├── src/
│   │   ├── core/          # 核心模块（menu、fuzz_loop、report_generator 等）
│   │   ├── protocols/     # 协议插件（registry + 各协议 client/mutator/llm_mutator）
│   │   └── integrations/  # MCP 集成
│   ├── server/            # 各协议模拟从站
│   ├── config/            # 配置包（connect_templates.yaml）
│   ├── tools/             # check_protocol.py 等工具
│   ├── tests/             # 验证脚本与单元测试
│   ├── docs/              # PRD 文档
│   └── main.py            # 入口
├── agentscope_env/        # 开发用虚拟环境（不打包）
└── IndusFuzz-v1.8.1-win64/  # 发布产物（不提交）
```

## 测试运行

### 完整测试套件（pytest，147 用例）

```bash
cd IndusFuzz
python -m pytest tests/ -v
```

一键 6 阶段编排（含中文 HTML 报告）：

```bash
python run_all_tests.py
```

### 协议自检

每个协议都有独立的 11 项自检，新增或修改协议后必须跑通：

```bash
cd IndusFuzz
python tools/check_protocol.py modbus     # 替换为目标协议名
python tools/check_protocol.py dnp3
# 支持的协议名：modbus s7comm dnp3 iec104 iec61850 enip opcua
```

### Bandit 安全静态扫描

```bash
bandit -r src/server -lll
bandit -r src/protocols/<your-protocol>/ server/<your-protocol>_server.py -lll
```

安全基线：**Bandit 零 HIGH**。

### pre-commit 钩子（可选）

安装后提交时自动跑 black / flake8 / bandit：

```bash
pip install pre-commit
pre-commit install
```

### 模拟从站启动验证

```bash
# 开发模式
python main.py   # 在菜单里选"启动模拟从站"
# 或直接
python -m src.core.slave_launcher --protocol modbus --port 5020 --strict
```

### 单协议完整 fuzz 验证

跑一次交互向导，至少 3 个功能码、能正常发请求、收响应、分类、写报告。

## Issue 流程

1. **搜现有 Issue**：打开 [Issues](../../issues)，确认无人提过同类问题。
2. **使用模板**：新建 Issue 时选择对应模板（Bug Report / Feature Request / Protocol Request）。
3. **描述清楚**：
   - 复现步骤
   - 预期行为 vs 实际行为
   - 运行环境（OS / Python / IndusFuzz 版本）
   - 日志或截图（脱敏）
4. **安全问题**：涉及敏感信息（API Key、生产设备）时请仅在描述中注明"脱敏"，并使用 PGP 加密附件。

## Pull Request 流程

### 准备

- Fork 仓库，在独立分支上修改（推荐命名：`feature/<name>`、`fix/<issue>`）。
- 保持单个 PR 只做一类事（不把重构和功能混入同一个 PR）。

### 提交前自检

- [ ] `check_protocol.py` 对受影响协议全过（11/11）
- [ ] `bandit -r src -lll` 无 HIGH
- [ ] 代码无硬编码 Key（`rg -i "sk-[a-z0-9]{10}" src/` 零命中）
- [ ] 功能码 JSON、client、mutator、server、report_generator 五处数量一致（详见 docs/IndusFuzz 协议扩展 PRD.md 的"十七、多位置功能码一致性清单"）
- [ ] CHANGELOG.md 已更新（在对应版本段的 Added/Changed/Fixed 下追加条目）
- [ ] 不引入新依赖（或在 PR 描述中说明必要性）

### 提交

- 使用 `.github/PULL_REQUEST_TEMPLATE.md` 填写改动类型、关联 Issue、测试情况。
- 关联 Issue（Fixes #xxx / Refs #xxx）。
- 双语变更需同时更新 README.md 和 README.zh.md。

### Review 与合并

- Reviewer 确认通过后合并。
- 合并后删除功能分支。

## 代码风格

### Python

- Python 3.10+ 类型注解风格。
- 函数/方法加 docstring（英文）。
- 代码**不加中文注释**；终端输出、日志、错误消息**必须中文**（终端用户是中文使用者）。
- 遵循项目现有命名约定（类名 PascalCase、函数/方法 snake_case、常量 UPPER_CASE）。

### 文件与模块

- 协议命名：小写、与 registry 注册名一致（如 `src/protocols/dnp3/` → 注册名 `"dnp3"`）。
- 抽象基类签名（`src/protocols/base.py` 的 `ProtocolBase`）与所有实现类一致，禁止在子类签名中增删参数（反模式 Y）。
- 通用代码放 `core/` 或 `protocols/llm_mutator_base.py`，协议特有代码放各自子目录。

### 安全硬约束

- client.py / llm_mutator.py 严禁硬编码 API Key。
- server.py 默认监听 `127.0.0.1`（反模式 B + 审计 PRD 7.9 安全基线）。
- llm_mutator 必须走基类（`llm_mutator_base.py`），基类提供 `timeout=25` + `max_retries=0`，禁止协议各自复制一份。
- 云端 API 调用强制 HTTPS。
- 报告中所有外部文本（target、reason、error_msg 等）必须走 `_esc()` 函数（XSS 防护，反模式 T）。

### 反模式清单

提交前对照 `docs/IndusFuzz 协议扩展 PRD.md` 的"十六、反模式 A-Z"逐项自检。核心几条：

| 编号 | 描述 | 后果 |
|------|------|------|
| B | 在 menu.py / fuzz_loop_llm.py 加 if-elif 硬编码新协议 | 破坏 registry 自动发现 |
| C | 协议名硬编码分散在多个文件 | 改一处忘四处 |
| G | report_generator.py 同协议条目出现两次 | KeyError 或重复 |
| K | client.py 循环变量名不一致 | 批量 patch 易写错 |
| O | 写了代码但从未运行验证 | 假修复进入主分支 |
| T | HTML 拼接点转义遗漏 | 存储型 XSS |
| Y | 基类签名与实现类不对齐 | 调用方参数漂移 |
| Z | 测试 mock 打错模块层级 | 被测路径绕过 mock |

## 协议扩展指引

新增协议是本项目最有价值的贡献类型。完整流程见：

> **`docs/IndusFuzz 协议扩展 PRD.md`**（项目根 `docs/` 目录）

该文档涵盖：

- **11 步流程**：目录结构 → func_codes JSON → client 9 方法 → mutator → llm_mutator 薄壳 → registry 注册 → menu PROTOCOL_CONNECT_PARAMS → slave_launcher → fuzz_loop 通用分支 → report_generator PROTOCOL_CONFIG → README 真实设备指南
- **17 项 checklist**：动手前→代码→从站→报告→验证→清理→全面检查
- **阶段 7.10 真实设备支持**（v2.0 起新增协议必做）：connect 必须实现协议握手、send_payload 双模式、_recv_frame 按帧长循环等
- **九章握手表**：Modbus=连通性 / S7=COTP CR→CC+S7 Setup / DNP3=链路重置 / IEC104=STARTDT / IEC61850=MMS Initiate / ENIP=RegisterSession / OPC UA=HEL→ACK
- **十七/十八章**：多位置功能码一致性清单 + Checklist 完成情况示例

**快速参照（阶段 7.10 真实设备支持检查）**：

新增协议提交前必须满足：

- [ ] client.py 实现 9 个方法（build_request / send_payload / parse_response / get_default_port / get_func_codes / run_fuzz / connect / disconnect / is_connected）
- [ ] connect 实现协议握手（参照九章握手表）
- [ ] send_payload 双模式（persistent + 无状态回退 + 失败熔断 >3 次放弃）
- [ ] _recv_frame 按协议帧长循环接收（禁止一次性 recv(4096)）
- [ ] menu.py PROTOCOL_CONNECT_PARAMS 含新协议条目
- [ ] README.md + README.zh.md 的"真实设备测试指南"含新协议章节
- [ ] `check_protocol.py <new>` → 11/11 OK
- [ ] `bandit -r src/protocols/<new>/ server/<new>_server.py -lll` → 零 HIGH

## 许可证

提交代码即表示你同意项目以 Apache License 2.0 授权发布（见 `LICENSE`）。


