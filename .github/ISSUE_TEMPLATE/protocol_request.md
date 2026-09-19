---
name: 协议支持申请
about: 申请支持一个新的工业协议
title: "[Protocol] <协议名> 支持"
labels: new-protocol
assignees: ""
---

## 目标协议

| 项目 | 值 |
|------|-----|
| 协议名 | [e.g. Profinet / BACnet / FINS] |
| 正式全名 | [e.g. Process Field Bus NETwork / Building Automation and Control Networks] |
| 默认端口 | [e.g. 502 / 47808] |
| 传输层 | [e.g. TCP / UDP / 串口 / RAW Ethernet] |
| 应用层协议 ID | [e.g. EtherType 0x0800 / MMS context] |

## 协议来源与参考

- 官方标准文档：**[URL 或 RFC 编号]**
- 公开协议实现（参考用，不抄代码）：**[URL / GitHub 仓库]**
- 参考的开源库：**[e.g. profinetio, bacpypes]**

## 功能码 / 服务 ID 概览

**列出关键请求码（至少 10 条）。**

| Code | 名称 | 说明 |
|------|------|------|
| 0x01 | [示例] | 读线圈 |
| ... | | |

## 报文格式概要

**描述典型请求帧的字段布局（长度、校验、寻址）。**

```
Start | Length | Control | Function Code | Address | Data | CRC
0x0564  1B       1B        2B              2B+2B    NB     2B(CRC16)
```

## 真实设备可用性

- [ ] 已有或可获取真实设备用于验证
- [ ] 仅在模拟从站上验证即可接受
- [ ] 已知设备型号 / 固件版本：**[填写]**

## 与现有协议的重叠

**是否与已支持的 7 种协议存在传输层重叠？**

<!-- e.g. FINS 与 OPC UA 都跑 TCP，但 FINS 是 Omron 私有；BACnet 有 TCP/IP (BACnet/IP) 和 UDP -->

## 自查清单（提交前确认）

- [ ] 已搜索现有 Issue，未发现重复申请
- [ ] 已提供至少 10 个请求功能码
- [ ] 已说明与现有 7 协议的重叠关系
- [ ] 若有真实设备，已注明型号
