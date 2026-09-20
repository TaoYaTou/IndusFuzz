"""
LLM 变异状态收集器。

7 个协议的 llm_mutator.py 共用同一套状态收集模式：
    status = LLMStatus()
    llm_generate_mutations(base_hex, count=5, status_collector=status)
    # 之后 status 里就有了本轮测试的完整 LLM 调用状态

传到报告里：status.serialize() → {"events": [...], "summary": {...}}
"""


class LLMStatus:
    """单协议一轮 fuzz 测试期间的 LLM 调用状态收集。"""

    # 事件类型常量
    EVT_LLM_CALL = "llm_call"                 # 开始调 LLM
    EVT_LLM_SUCCESS = "llm_success"           # LLM 返回
    EVT_LLM_ERROR = "llm_error"               # LLM 报错（429/401/500 等）
    EVT_LLM_PARTIAL = "llm_partial"           # LLM 返回但变异数 < count
    EVT_FALLBACK = "fallback"                 # 用本地变异补齐

    def __init__(self):
        self.events = []  # list of dict: {type, fc_str, details}
        self.total_func_codes = 0
        self.with_llm = 0         # 至少成功拿到 1 条变异
        self.with_partial = 0     # 部分成功（< count 条）
        self.with_error = 0       # 完全失败（所有重试都报错）
        self.with_fallback = 0    # 用过本地补齐
        self.fallback_only = 0    # 完全没调 LLM（本地 fallback only）
        self.error_429 = 0
        self.error_401 = 0
        self.error_other = 0
        self.first_429_msg = None
        self.first_401_msg = None
        self.model_info = None    # {"provider": str, "name": str, "base_url": str}，首次 set 后不再覆盖

    def set_model_info(self, provider, name, base_url):
        """记录本轮 fuzz 使用的 LLM 模型信息。首次设置后不覆盖（取第一个有效值）。"""
        if self.model_info is None:
            self.model_info = {
                "provider": provider or "none",
                "name": name or "unknown",
                "base_url": base_url or "",
            }

    def record(self, evt_type, fc_str=None, details=None):
        entry = {"type": evt_type}
        if fc_str is not None:
            entry["func_code"] = fc_str
        if details is not None:
            entry["details"] = details
        self.events.append(entry)

    # —— llm_mutator.py 调用入口 ——

    def on_call(self, fc_str):
        self.total_func_codes += 1
        self.record(self.EVT_LLM_CALL, fc_str=fc_str)

    def on_success(self, fc_str, n_mutations, count):
        self.with_llm += 1
        if n_mutations < count:
            self.with_partial += 1
            self.record(self.EVT_LLM_PARTIAL, fc_str=fc_str,
                        details=f"返回 {n_mutations}/{count} 条变异")
        else:
            self.record(self.EVT_LLM_SUCCESS, fc_str=fc_str,
                        details=f"返回 {n_mutations}/{count} 条变异")

    def on_error(self, fc_str, err_code, err_msg):
        self.with_error += 1
        self.record(self.EVT_LLM_ERROR, fc_str=fc_str,
                    details=f"[{err_code}] {err_msg}")
        if err_code == "429":
            self.error_429 += 1
            if self.first_429_msg is None:
                self.first_429_msg = err_msg
        elif err_code == "401":
            self.error_401 += 1
            if self.first_401_msg is None:
                self.first_401_msg = err_msg
        else:
            self.error_other += 1

    def on_fallback_used(self, fc_str, reason="partial"):
        self.with_fallback += 1
        self.record(self.EVT_FALLBACK, fc_str=fc_str, details=reason)

    def on_fallback_only(self, fc_str):
        self.fallback_only += 1
        self.with_fallback += 1
        self.record(self.EVT_FALLBACK, fc_str=fc_str,
                    details="LLM 未返回任何有效变异，全部用本地变异")

    # —— 报告输出 ——

    @property
    def has_warning(self) -> bool:
        """是否有需要警示用户的 LLM 问题。"""
        return (
            self.error_429 > 0
            or self.error_401 > 0
            or self.with_error > 0
            or self.fallback_only > 0
            or self.with_partial > 0
        )

    def warning_level(self) -> str:
        """严重程度：critical / high / medium / ok"""
        if self.error_401 > 0:
            return "critical"
        if self.error_429 > 0:
            return "high"
        if self.with_error > 0 or self.fallback_only > 0:
            return "medium"
        if self.with_partial > 0:
            return "low"
        return "ok"

    def build_warning_html(self, lang="zh") -> str:
        """生成报告顶部的警示框 HTML。"""
        import html as _html
        if not self.has_warning:
            return ""

        level = self.warning_level()
        # 转义来自云端 API 的可控错误消息，防止 XSS
        msg_401 = _html.escape(self.first_401_msg or "")
        msg_429 = _html.escape(self.first_429_msg or "")
        colors = {
            "critical": ("#721c24", "#f8d7da", "#721c24"),
            "high":     ("#856404", "#fff3cd", "#856404"),
            "medium":   ("#0c5460", "#d1ecf1", "#0c5460"),
            "low":      ("#383d41", "#e2e3e5", "#383d41"),
        }
        border, bg, text = colors.get(level, colors["medium"])

        if lang == "zh":
            title_map = {
                "critical": "🔴 LLM 鉴权完全失败 — 本次 fuzz 结果仅有本地随机变异",
                "high":     "🟠 LLM 云端限流 — 部分/全部变异由本地随机补齐，结果不完整",
                "medium":   "🟡 LLM 调用异常 — 部分变异由本地随机补齐",
                "low":      "🔵 LLM 返回不足 — 变异数量低于预期，已由本地补齐",
            }
            lines = [title_map.get(level, "LLM 状态异常")]
            lines.append("")
            if self.error_401 > 0:
                lines.append(
                    f"• 鉴权失败（401）{self.error_401} 次：{msg_401}"
                    if msg_401 else
                    f"• 鉴权失败（401）{self.error_401} 次，API Key 无效或已过期"
                )
            if self.error_429 > 0:
                lines.append(
                    f"• 云端限流（429）{self.error_429} 次：{msg_429}"
                    if msg_429 else
                    f"• 云端限流（429）{self.error_429} 次，免费额度用完或请求过于频繁"
                )
            if self.error_other > 0:
                lines.append(f"• 其他云端错误 {self.error_other} 次（500/502/503/timeout 等）")
            if self.fallback_only > 0:
                lines.append(
                    f"• {self.fallback_only}/{self.total_func_codes} 个功能码完全没有 LLM 变异，全部使用本地随机变异"
                )
            if self.with_partial > 0:
                lines.append(
                    f"• {self.with_partial}/{self.total_func_codes} 个功能码 LLM 返回不足 5 条，已由本地变异补齐"
                )
            if self.with_llm > 0 and not (self.error_429 or self.error_401):
                lines.append(
                    f"• LLM 成功：{self.with_llm}/{self.total_func_codes} 个功能码"
                    + (
                        f"（共使用 {self.with_fallback} 次本地补齐）"
                        if self.with_fallback else ""
                    )
                )
            lines.append("")
            lines.append("⚠️ 注意：本地随机变异是按字节翻转/插入构造的，不包含协议语义理解。")
            lines.append("   要获得高质量的 LLM 变异，请修复上述问题后重新运行。")
        else:
            title_map = {
                "critical": "🔴 LLM authentication failed — fuzz results are 100% local random mutations",
                "high":     "🟠 Cloud API rate-limited — some/all mutations were filled with local random",
                "medium":   "🟡 LLM call errors — some mutations filled with local random",
                "low":      "🔵 LLM returned fewer mutations than expected — locally filled",
            }
            lines = [title_map.get(level, "LLM status abnormal")]
            lines.append("")
            if self.error_401 > 0:
                lines.append(f"• Auth failure (401) x{self.error_401}")
            if self.error_429 > 0:
                lines.append(
                    f"• Rate limited (429) x{self.error_429}: {msg_429}"
                    if msg_429 else
                    f"• Rate limited (429) x{self.error_429}, quota exhausted or too many requests"
                )
            if self.error_other > 0:
                lines.append(f"• Other cloud errors x{self.error_other} (500/502/503/timeout)")
            if self.fallback_only > 0:
                lines.append(
                    f"• {self.fallback_only}/{self.total_func_codes} func codes have ZERO LLM mutations, all local random"
                )
            if self.with_partial > 0:
                lines.append(
                    f"• {self.with_partial}/{self.total_func_codes} func codes got <5 mutations from LLM, filled locally"
                )
            lines.append("")
            lines.append("⚠️ Local fallback mutations are pure byte flips/insertions without protocol semantics.")
            lines.append("   For high-quality LLM-crafted mutations, fix the issues above and re-run.")

        inner = "<br>".join(lines).replace(" ", "&nbsp;")
        return (
            f"<div style='background:{bg};border-left:5px solid {border};"
            f"color:{text};padding:16px 20px;margin:16px 0;border-radius:4px;"
            f"font-family:monospace;white-space:pre-wrap;line-height:1.6'>"
            f"<strong>{inner}</strong></div>"
        )

    def serialize(self) -> dict:
        return {
            "has_warning": self.has_warning,
            "level": self.warning_level(),
            "total_func_codes": self.total_func_codes,
            "with_llm": self.with_llm,
            "with_partial": self.with_partial,
            "with_error": self.with_error,
            "with_fallback": self.with_fallback,
            "fallback_only": self.fallback_only,
            "error_429": self.error_429,
            "error_401": self.error_401,
            "error_other": self.error_other,
            "events": self.events[:200],
            "model_info": self.model_info,
        }
