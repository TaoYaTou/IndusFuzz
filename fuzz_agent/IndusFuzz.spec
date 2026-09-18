# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

datas = [
    ("src/protocols/func_codes/*.json", "src/protocols/func_codes"),
    ("assets/fonts/simhei.ttf", "assets/fonts"),
]

hiddenimports = [
    "src.protocols.registry",
    "src.protocols.base",
    "src.protocols.llm_mutator_base",
    "src.core.version",
    "src.core.security",
    "src.core.llm_precheck",
    "src.core.llm_status",
    "src.core.runtime_config",
    "src.core.gpu_detector",
    "src.core.color_output",
    "src.core._resource",
    "src.core.menu",
    "src.core.slave_launcher",
    "src.core.fuzz_loop_llm",
    "src.core.report_generator",
    "src.core.result_analyzer",
    "src.core.diagnose",
    "src.integrations",
    "src.integrations.vulnclaw_mcp",
    "src.integrations.codeguard_mcp",
    "src.integrations.codeinspectus_mcp",
    "server.modbus_server",
    "server.s7comm_server",
    "server.dnp3_server",
    "server.iec104_server",
    "server.iec61850_server",
    "server.enip_server",
    "server.opcua_server",
    "src.protocols.modbus.client",
    "src.protocols.modbus.mutator",
    "src.protocols.modbus.llm_mutator",
    "src.protocols.modbus.modbus_tools",
    "src.protocols.s7comm.client",
    "src.protocols.s7comm.mutator",
    "src.protocols.s7comm.llm_mutator",
    "src.protocols.dnp3.client",
    "src.protocols.dnp3.mutator",
    "src.protocols.dnp3.llm_mutator",
    "src.protocols.iec104.client",
    "src.protocols.iec104.mutator",
    "src.protocols.iec104.llm_mutator",
    "src.protocols.iec61850.client",
    "src.protocols.iec61850.mutator",
    "src.protocols.iec61850.llm_mutator",
    "src.protocols.enip.client",
    "src.protocols.enip.mutator",
    "src.protocols.enip.llm_mutator",
    "src.protocols.opcua.client",
    "src.protocols.opcua.mutator",
    "src.protocols.opcua.llm_mutator",
    "openai",
    "httpx",
    "pymodbus",
    "scapy",
    "xhtml2pdf",
    "html5lib",
    "six",
    "reportlab",
    "svglib",
    "pyhanko",
    "cryptography",
    "asyncua",
    "aiosqlite",
    "snap7",
    "win32crypt",
    "win32api",
    "pywintypes",
]

for mod in collect_submodules("scapy"):
    hiddenimports.append(mod)
for mod in collect_submodules("xhtml2pdf"):
    hiddenimports.append(mod)
for mod in collect_submodules("html5lib"):
    hiddenimports.append(mod)
for mod in collect_submodules("reportlab"):
    hiddenimports.append(mod)
for mod in collect_submodules("svglib"):
    hiddenimports.append(mod)
for mod in collect_submodules("pyhanko"):
    hiddenimports.append(mod)
for mod in collect_submodules("fontTools"):
    hiddenimports.append(mod)

excludes = [
    "tkinter",
    "matplotlib",
    "numpy.testing",
    "pandas.tests",
    "scipy",
    "pytest",
    "agentscope",
    "opentelemetry",
    "semgrep",
    "bandit",
    "pip_audit",
    "tests",
    "tests.*",
    "IPython",
    "jupyter",
    "notebook",
]

a = Analysis(
    ["main.py"],
    pathex=[os.path.abspath(".")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="IndusFuzz",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version="version_info.txt",
    icon=r"assets\concept_a_hex\icon.ico",
)
