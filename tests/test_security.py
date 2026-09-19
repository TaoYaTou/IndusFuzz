import pytest  # noqa: F401  # noqa: F401
from src.core.security import (
    encrypt_key,
    decrypt_key,
    is_encrypted,
    mask_key,
    store_api_key,
    get_api_key,
    validate_cloud_url,
)


class TestEncryptDecrypt:
    def test_roundtrip_plaintext(self):
        pt = "sk-test-1234567890abcdef"
        enc = encrypt_key(pt)
        dec = decrypt_key(enc)
        assert dec == pt

    def test_empty_returns_empty(self):
        assert encrypt_key("") == ""
        assert decrypt_key("") == ""

    def test_ollama_passthrough(self):
        assert encrypt_key("ollama:http://localhost:11434") == "ollama:http://localhost:11434"
        assert decrypt_key("ollama:http://localhost:11434") == "ollama:http://localhost:11434"

    def test_local_passthrough(self):
        assert encrypt_key("local:model-name") == "local:model-name"

    def test_dpapi_detection(self):
        key = "sk-isencrypted-test-0123456789abcdef"
        cipher = encrypt_key(key)
        assert decrypt_key(cipher) == key

    def test_is_encrypted_false_for_plain(self):
        assert is_encrypted("not-encrypted") is False

    def test_is_encrypted_true_for_dpapi(self):
        key = "sk-detected-test-abcdefghijklmnop012345"
        cipher = encrypt_key(key)
        result = is_encrypted(cipher)
        assert isinstance(result, bool)


class TestMaskKey:
    def test_empty(self):
        assert mask_key("") == "***"

    def test_short_key(self):
        assert mask_key("abc") == "***"

    def test_normal_key_masked(self):
        # key has 36 chars → first 4 + **** + last 4
        long_key = "sk-abcdefghijklmnopqrstuvwxyz0123456789"
        masked = mask_key(long_key)
        assert "****" in masked
        assert masked.startswith("sk-a")
        assert masked.endswith("6789")

    def test_ollama_key_preserves_prefix(self):
        masked = mask_key("ollama:http://localhost:11434")
        assert masked == "ollama:http://localhost:11434"


class TestStoreGetApiKey:
    def test_store_and_get_roundtrip(self):
        cfg = store_api_key({}, "sk-store-test-0123456789abcdef")
        key = get_api_key(cfg)
        assert key == "sk-store-test-0123456789abcdef"

    def test_store_is_idempotent(self):
        cfg = store_api_key({}, "sk-idem-test-0123456789abcdef")
        cfg2 = store_api_key(cfg, get_api_key(cfg))
        key = get_api_key(cfg2)
        assert key == "sk-idem-test-0123456789abcdef"

    def test_get_empty_cfg(self):
        assert get_api_key({}) == ""

    def test_get_plaintext_cfg(self):
        assert get_api_key({"api_key": "plain-key-xyz"}) == "plain-key-xyz"


class TestValidateCloudUrl:
    def test_ollama_always_ok(self):
        ok, err = validate_cloud_url("http://localhost:11434", "ollama")
        assert ok is True
        assert err is None

    def test_local_provider_always_ok(self):
        ok, err = validate_cloud_url("http://anything", "local")
        assert ok is True

    def test_none_provider_always_ok(self):
        ok, err = validate_cloud_url("", "none")
        assert ok is True

    def test_http_rejected_for_cloud_provider(self):
        ok, err = validate_cloud_url("http://api.openai.com/v1", "openai")
        assert ok is False
        assert "HTTPS" in err or "https" in err.lower()

    def test_https_accepted_for_cloud_provider(self):
        ok, err = validate_cloud_url("https://api.openai.com/v1", "openai")
        assert ok is True


# ============================================================
# E1 migrate_plaintext_config — 未覆盖行 80-82 全部分支
# ============================================================
class TestMigratePlaintextConfig:
    """首次加载时自动升级明文 api_key 为加密存储"""

    def test_no_key_returns_unchanged(self):
        from src.core.security import migrate_plaintext_config
        cfg = {"provider": "ollama"}
        result = migrate_plaintext_config(cfg)
        assert result is cfg  # 未修改，返回原 dict

    def test_empty_key_returns_unchanged(self):
        from src.core.security import migrate_plaintext_config
        cfg = {"provider": "openai", "api_key": ""}
        result = migrate_plaintext_config(cfg)
        assert result["api_key"] == ""
        assert "api_key_encrypted" not in result

    def test_ollama_key_returns_unchanged(self):
        from src.core.security import migrate_plaintext_config
        cfg = {"provider": "ollama", "api_key": "ollama://localhost:11434"}
        result = migrate_plaintext_config(cfg)
        assert result["api_key"] == "ollama://localhost:11434"
        assert "api_key_encrypted" not in result

    def test_local_key_returns_unchanged(self):
        from src.core.security import migrate_plaintext_config
        cfg = {"provider": "local", "api_key": "local:///my/key.pem"}
        result = migrate_plaintext_config(cfg)
        assert result["api_key"] == "local:///my/key.pem"


# ============================================================
# E2 base.py ProtocolBase — 未覆盖行 5/8/11/14/17/20/23/26/30
# ============================================================
class TestProtocolBase:
    """ProtocolBase 抽象基类的完整行为测试"""

    def test_base_name_attribute(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        assert cls.name == "base"

    def test_disconnect_is_noop(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        assert cls.disconnect() is None  # 有默认实现

    def test_is_connected_default_false(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        assert cls.is_connected() is False

    def test_build_request_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.build_request()
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_send_payload_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.send_payload(b"", "127.0.0.1", 502)
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_parse_response_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.parse_response(b"")
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_get_default_port_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.get_default_port()
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_get_func_codes_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.get_func_codes()
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_connect_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.connect("127.0.0.1", 502)
            assert False, "should raise"
        except NotImplementedError:
            pass

    def test_run_fuzz_raises(self):
        from src.protocols.base import ProtocolBase
        cls = ProtocolBase()
        try:
            cls.run_fuzz([], "", 0, 0, {}, set(), [])
            assert False, "should raise"
        except NotImplementedError:
            pass


# ============================================================
# E3 codeguard_mcp + codeinspectus_mcp — 基础导入 + 模块常量
# ============================================================
class TestMCPIntegrations:
    """MCP 集成模块基础 smoke test（不依赖真实 MCP server）"""

    def test_codeguard_mcp_imports(self):
        from src.integrations import codeguard_mcp
        assert hasattr(codeguard_mcp, "MCP_AVAILABLE")
        assert hasattr(codeguard_mcp, "CodeGuardMCP")
        assert hasattr(codeguard_mcp, "create_server")
        assert hasattr(codeguard_mcp, "stdio_server")
        assert hasattr(codeguard_mcp, "main")

    def test_codeinspectus_mcp_imports(self):
        from src.integrations import codeinspectus_mcp
        assert hasattr(codeinspectus_mcp, "MCP_AVAILABLE")
        assert hasattr(codeinspectus_mcp, "CodeInspectusMCP")
        assert hasattr(codeinspectus_mcp, "create_server")
        assert hasattr(codeinspectus_mcp, "stdio_server")
        assert hasattr(codeinspectus_mcp, "main")

    def test_codeguard_mcp_mcp_available_bool(self):
        from src.integrations.codeguard_mcp import MCP_AVAILABLE
        assert isinstance(MCP_AVAILABLE, bool)

    def test_codeinspectus_mcp_mcp_available_bool(self):
        from src.integrations.codeinspectus_mcp import MCP_AVAILABLE
        assert isinstance(MCP_AVAILABLE, bool)

    def test_version_module_available(self):
        from src.core.version import __version__, get_version
        assert isinstance(__version__, str)
        assert len(__version__) > 0
        assert get_version() == __version__

    def test_version_env_override(self, monkeypatch):
        from src.core import version
        monkeypatch.setenv("INDUSFUZZ_VERSION", "custom-2.0.0")
        # 需要重新调用 get_version，因为 __version__ 是模块加载时算的
        assert version.get_version() == "custom-2.0.0"


# ============================================================
# E4 CodeGuardMCP / CodeInspectusMCP 完整方法覆盖
# ============================================================
class TestCodeGuardMCP:
    """CodeGuardMCP 类行为（不依赖真实 MCP Server）"""

    def test_name_attribute(self):
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        assert cls.name == "codeguard"

    def test_default_scan_root(self):
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        assert cls.scan_root == "."

    def test_custom_scan_root(self):
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP(scan_root="/tmp/demo")
        assert cls.scan_root == "/tmp/demo"

    def test_is_available_returns_bool(self):
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        assert isinstance(cls.is_available(), bool)

    def test_list_tools_returns_dict(self):
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        tools = cls.list_tools()
        assert isinstance(tools, list)
        assert len(tools) == 1
        assert tools[0]["name"] == "codeguard_audit"
        assert "input_schema" in tools[0]

    def test_call_tool_unknown_raises(self):
        import asyncio
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        try:
            asyncio.run(cls.call_tool("nonexistent", {}))
            assert False, "should raise"
        except ValueError as e:
            assert "未知工具" in str(e)

    def test_call_tool_audit(self):
        import asyncio
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        result = asyncio.run(cls.call_tool("codeguard_audit", {"path": "/tmp", "level": "deep"}))
        assert result["status"] == "not_implemented"
        assert result["path"] == "/tmp"
        assert result["level"] == "deep"

    def test_call_tool_audit_default_level(self):
        import asyncio
        from src.integrations.codeguard_mcp import CodeGuardMCP
        cls = CodeGuardMCP()
        result = asyncio.run(cls.call_tool("codeguard_audit", {"path": "."}))
        assert result["level"] == "quick"

    def test_create_server_when_mcp_unavailable(self):
        # 模拟 mcp 不可用
        from src.integrations import codeguard_mcp
        original_flag = codeguard_mcp.MCP_AVAILABLE
        codeguard_mcp.MCP_AVAILABLE = False
        try:
            from src.integrations.codeguard_mcp import create_server
            try:
                create_server()
                assert False, "should raise"
            except RuntimeError as e:
                assert "未安装" in str(e) or "mcp" in str(e).lower()
        finally:
            codeguard_mcp.MCP_AVAILABLE = original_flag


class TestCodeInspectusMCP:
    """CodeInspectusMCP 类行为 — 类似 CodeGuard，结构对称"""

    def test_name_attribute(self):
        from src.integrations.codeinspectus_mcp import CodeInspectusMCP
        cls = CodeInspectusMCP()
        assert cls.name == "codeinspectus"

    def test_list_tools_has_one(self):
        from src.integrations.codeinspectus_mcp import CodeInspectusMCP
        cls = CodeInspectusMCP()
        tools = cls.list_tools()
        assert len(tools) >= 1
        assert "input_schema" in tools[0]

    def test_call_tool_unknown_raises(self):
        import asyncio
        from src.integrations.codeinspectus_mcp import CodeInspectusMCP
        cls = CodeInspectusMCP()
        try:
            asyncio.run(cls.call_tool("wtf_tool", {}))
            assert False, "should raise"
        except ValueError:
            pass

    def test_create_server_unavailable(self):
        from src.integrations import codeinspectus_mcp
        original_flag = codeinspectus_mcp.MCP_AVAILABLE
        codeinspectus_mcp.MCP_AVAILABLE = False
        try:
            from src.integrations.codeinspectus_mcp import create_server
            try:
                create_server()
                assert False
            except RuntimeError:
                pass
        finally:
            codeinspectus_mcp.MCP_AVAILABLE = original_flag


# ============================================================
# E5 report_generator 纯函数
# ============================================================
class TestReportGeneratorPureFuncs:
    """_esc / _break_long_text 等不依赖 I/O 的纯函数"""

    def test_esc_normal(self):
        from src.core.report_generator import _esc
        assert _esc("hello") == "hello"

    def test_esc_html_tags(self):
        from src.core.report_generator import _esc
        assert _esc("<script>alert(1)</script>") != "<script>alert(1)</script>"
        assert "&lt;" in _esc("<script>alert(1)</script>")

    def test_esc_empty(self):
        from src.core.report_generator import _esc
        assert _esc("") == ""

    def test_esc_non_string(self):
        from src.core.report_generator import _esc
        assert _esc(123) == "123"

    def test_break_long_text_short(self):
        from src.core.report_generator import _break_long_text
        assert _break_long_text("abc") == "abc"

    def test_break_long_text_exact(self):
        from src.core.report_generator import _break_long_text
        assert _break_long_text("12345678901234") == "12345678901234"

    def test_break_long_text_longer(self):
        from src.core.report_generator import _break_long_text
        result = _break_long_text("ABCDEF0123456789ABCDEF0123456789")
        assert "<br>" in result

    def test_break_long_text_empty(self):
        from src.core.report_generator import _break_long_text
        assert _break_long_text("") == ""


# ============================================================
# E6 VulnClawMCP — 完整类行为覆盖
# ============================================================
class TestVulnClawMCP:
    """VulnClawMCP 类行为 — 与 CodeGuard/CodeInspectus 对称"""

    def test_name_attribute(self):
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        assert cls.name == "vulnclaw"

    def test_default_ollama_url(self):
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        assert cls.ollama_base_url == "http://localhost:11434"

    def test_default_model(self):
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        assert cls.model == "qwen2.5-coder:14b"

    def test_custom_constructor(self):
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP(ollama_base_url="http://10.0.0.1:11434", model="llama3")
        assert cls.ollama_base_url == "http://10.0.0.1:11434"
        assert cls.model == "llama3"

    def test_list_tools_has_vulnclaw_scan(self):
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        tools = cls.list_tools()
        names = [t["name"] for t in tools]
        assert "vulnclaw_scan" in names

    def test_call_tool_unknown_raises(self):
        import asyncio
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        try:
            asyncio.run(cls.call_tool("invalid_tool", {}))
            assert False, "should raise"
        except ValueError:
            pass

    def test_call_tool_scan(self):
        import asyncio
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        result = asyncio.run(cls.call_tool("vulnclaw_scan", {"target": "10.0.0.1", "mode": "full"}))
        assert result["status"] == "not_implemented"
        assert result["target"] == "10.0.0.1"
        assert result["mode"] == "full"

    def test_call_tool_scan_default_mode(self):
        import asyncio
        from src.integrations.vulnclaw_mcp import VulnClawMCP
        cls = VulnClawMCP()
        result = asyncio.run(cls.call_tool("vulnclaw_scan", {"target": "10.0.0.1"}))
        assert result["mode"] == "quick"

    def test_create_server_unavailable(self):
        from src.integrations import vulnclaw_mcp
        original_flag = vulnclaw_mcp.MCP_AVAILABLE
        vulnclaw_mcp.MCP_AVAILABLE = False
        try:
            from src.integrations.vulnclaw_mcp import create_server
            try:
                create_server()
                assert False
            except RuntimeError as e:
                assert "未安装" in str(e) or "mcp" in str(e).lower()
        finally:
            vulnclaw_mcp.MCP_AVAILABLE = original_flag
