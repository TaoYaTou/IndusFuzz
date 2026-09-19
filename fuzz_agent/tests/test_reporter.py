import os
import pytest
from src.core.report_generator import (
    _esc,
    _get_display_name,
    classify_severity,
    generate_report,
    _get_protocol_notes,
    _get_slave_note,
)

_SEVERITY_LEVELS = {"critical", "high", "medium", "low", "info"}


class TestEsc:
    def test_plain_text_unchanged(self):
        assert _esc("hello world") == "hello world"

    def test_html_chars_escaped(self):
        assert _esc("<script>") == "&lt;script&gt;"
        assert _esc("a & b") == "a &amp; b"

    def test_quotes_escaped(self):
        result = _esc('say "hi"')
        assert "&quot;" in result or '"' not in result

    def test_xss_angle_brackets_neutralized(self):
        result = _esc("<img src=x onerror=alert(1)>")
        assert "&lt;" in result
        assert "&gt;" in result


class TestGetDisplayName:
    @pytest.mark.parametrize("proto", ["modbus", "s7comm", "opcua", "dnp3", "iec104", "iec61850", "enip"])
    def test_all_builtins_have_display_name(self, proto):
        name = _get_display_name(proto)
        assert name is not None
        assert isinstance(name, str)
        assert len(name) > 0


class TestClassifySeverity:
    def test_returns_tuple_with_level(self):
        result = classify_severity(0x03, "EXCEPTION", b"0x86 0x02", "modbus")
        assert isinstance(result, tuple)
        assert len(result) >= 1
        level = result[0].lower()
        assert level in _SEVERITY_LEVELS

    def test_normal_response_returns_tuple(self):
        result = classify_severity(0x03, "SUCCESS", b"0x03 0x02 0x00 0x00", "modbus")
        assert isinstance(result, tuple)
        assert result[0].lower() in _SEVERITY_LEVELS

    def test_unknown_has_safe_first_element(self):
        result = classify_severity(0xFF, "UNKNOWN", b"", "modbus")
        assert isinstance(result, tuple)
        assert result[0].lower() in _SEVERITY_LEVELS


class TestGenerateReport:
    def test_returns_tuple_of_paths(self, tmp_report_dir):
        results = []
        skipped = []
        failures = []
        out = generate_report(
            results, skipped, failures,
            protocol_name="modbus",
            target="127.0.0.1:5020",
        )
        assert out is not None
        assert isinstance(out, tuple)
        assert len(out) >= 1
        html_path = out[0]
        assert isinstance(html_path, str)
        assert html_path.endswith(".html")

    def test_empty_results_generates_report(self):
        out = generate_report([], [], [], protocol_name="s7comm", target="192.168.1.10:102")
        html_path = out[0]
        assert os.path.isfile(html_path)

    def test_report_file_exists(self):
        out = generate_report([], [], [], protocol_name="opcua", target="opc.example.com:4840")
        assert os.path.isfile(out[0])

    def test_bilingual_notes_exist(self):
        zh = _get_protocol_notes("modbus", lang="zh")
        en = _get_protocol_notes("modbus", lang="en")
        assert zh is not None
        assert en is not None

    def test_slave_note_both_langs(self):
        zh = _get_slave_note("modbus", lang="zh")
        en = _get_slave_note("modbus", lang="en")
        assert isinstance(zh, str)
        assert isinstance(en, str)
