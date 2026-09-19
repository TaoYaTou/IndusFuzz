## 改动类型

- [ ] 新增功能（Feature）
- [ ] 修复 Bug（Fix）
- [ ] 新协议接入（Protocol）
- [ ] 文档更新（Docs）
- [ ] 重构（Refactor）
- [ ] 安全加固（Security）
- [ ] 其他

## 改动概述

**一句话说明这个 PR 做了什么。**

<!-- e.g. 新增 Profinet 协议支持；修复打包后 PDF 中文乱码 -->

## 关联 Issue

<!-- 填 Fixes #xxx 或 Refs #xxx，没有则填 N/A -->

Fixes #

## 改动文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/protocols/dnp3/client.py` | 修改 | DNP3 客户端实现 |
| ... | | |

## 测试情况

**勾选你实际跑过的测试，并贴输出关键行。**

- [ ] 协议自检 `python tools/check_protocol.py <name>` → **11/11**
  ```
  [粘贴输出]
  ```
- [ ] Bandit `bandit -r src -lll` → **High=0**
  ```
  [粘贴输出]
  ```
- [ ] 完整 fuzz 流程跑通（至少 3 个功能码，有报告）
  - 目标类型：模拟从站 / 真实设备
  - 协议：
- [ ] 文档已同步（README.md / README.zh.md / CHANGELOG.md）
- [ ] 无硬编码 Key（`rg -i "sk-[a-z0-9]{10}" src/` 零命中）
- [ ] 五处功能码数量一致（func_codes JSON ↔ client ↔ mutator ↔ server ↔ report_generator）

## 协议扩展阶段 7.10 检查（仅新协议接入必填）

- [ ] client.py 9 个方法齐（build_request / send_payload / parse_response / get_default_port / get_func_codes / run_fuzz / connect / disconnect / is_connected）
- [ ] connect 实现协议握手（参照九章握手表）
- [ ] send_payload 双模式 + 熔断 >3 放弃
- [ ] _recv_frame 按帧长循环接收
- [ ] menu.py PROTOCOL_CONNECT_PARAMS 含新协议
- [ ] README 双语真实设备指南含新协议章节
- [ ] 无 if-elif 硬编码（反模式 B）

## 安全 / 审计

- [ ] 新增 server.py 默认监听 `127.0.0.1`
- [ ] 云端 API 调用强制 HTTPS
- [ ] 报告中所有外部文本走 `_esc()`（XSS 防护）
- [ ] llm_mutator 走基类 `llm_mutator_base.py`（timeout=25 / max_retries=0）

## 自查清单（提交前确认）

- [ ] 单个 PR 只做一类事（不同时引入新协议 + 重构）
- [ ] 已跑过并贴了 3 项测试输出
- [ ] CHANGELOG.md 已更新（在对应版本段追加）
- [ ] 不引入新依赖（或在描述中说明必要性）
- [ ] 不包含敏感信息（API Key、token、生产设备地址等）

## Reviewer 提示

<!-- 给 Reviewer 的备注，如：从哪个文件开始看、哪块需要重点审 -->
