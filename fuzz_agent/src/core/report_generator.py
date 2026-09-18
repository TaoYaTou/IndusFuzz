import os
import html as _html
from datetime import datetime

from src.core.version import __version__
from src.core.result_analyzer import analyze_results, _EXCEPTION_CODE_OFFSET
from src.core._resource import resource_path, app_dir


def _esc(text):
    """对拼入 HTML 的用户/外部文本做转义，防止存储型 XSS。"""
    return _html.escape(str(text), quote=True)

REPORT_DIR = os.path.join(app_dir(), "reports")

# xhtml2pdf 中文字体注册（仅注册一次）
_CN_FONT_REGISTERED = False
_CN_FONT_PATH = None


def _get_cn_font_path():
    """返回项目内中文字体路径，不存在则尝试从系统复制。

    PyInstaller 打包后字体位于 sys._MEIPASS（临时目录），xhtml2pdf 的资源策略
    不允许读取报告目录之外的文件，因此需要将字体复制到项目目录内。
    """
    global _CN_FONT_PATH
    if _CN_FONT_PATH and os.path.exists(_CN_FONT_PATH):
        return _CN_FONT_PATH
    local_font = resource_path(os.path.join("assets", "fonts", "simhei.ttf"))
    # 若字体在临时目录（PyInstaller _MEIPASS），复制到项目目录内供 xhtml2pdf 读取
    if local_font and os.path.exists(local_font):
        import shutil
        # 复制到 reports/ 同级 assets/fonts 目录（项目目录内）
        target_dir = os.path.join(app_dir(), "assets", "fonts")
        os.makedirs(target_dir, exist_ok=True)
        target = os.path.join(target_dir, "simhei.ttf")
        if not os.path.exists(target):
            try:
                shutil.copy2(local_font, target)
            except Exception:
                pass
        if os.path.exists(target):
            _CN_FONT_PATH = target
            return _CN_FONT_PATH
        _CN_FONT_PATH = local_font
        return _CN_FONT_PATH
    sys_font = r"C:\Windows\Fonts\simhei.ttf"
    if os.path.exists(sys_font):
        try:
            target_dir = os.path.join(app_dir(), "assets", "fonts")
            os.makedirs(target_dir, exist_ok=True)
            target = os.path.join(target_dir, "simhei.ttf")
            import shutil
            shutil.copy2(sys_font, target)
            _CN_FONT_PATH = target
            return _CN_FONT_PATH
        except Exception:
            pass
    return None


def _register_cn_font():
    """为 xhtml2pdf/reportlab 注册中文字体，解决 PDF 中文乱码。

    关键：patch xhtml2pdf.context.registerTTFont，绕过 Windows 上临时文件
    权限问题（getNamedFile() 创建的临时文件 reportlab 无法再次打开）。
    """
    global _CN_FONT_REGISTERED
    if _CN_FONT_REGISTERED:
        return
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        import xhtml2pdf.context as xctx

        font_path = _get_cn_font_path()
        if not font_path:
            return

        # Patch registerTTFont：直接用原始字体路径，不通过临时文件
        _orig_register = xctx.registerTTFont

        def _patched_register(fullFontName, file):
            if fullFontName in pdfmetrics._fonts:
                return
            src_path = getattr(file, 'uri', None)
            if not src_path or not str(src_path).lower().endswith(('.ttf', '.ttc')):
                src_path = file.getNamedFile()
            pdfmetrics.registerFont(TTFont(fullFontName, src_path))

        xctx.registerTTFont = _patched_register
        _CN_FONT_REGISTERED = True
    except Exception:
        pass


def _break_long_text(text, max_len=14):
    """对长字符串（如 hex 报文）每隔 max_len 字符插入 <br>，防止 PDF 表格文字重叠/溢出。"""
    if not text or len(text) <= max_len:
        return text
    parts = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    return "<br>".join(parts)


def _break_func_name(name, max_len=16):
    """对长函数名在 camelCase / 下划线 / 连字符边界插入 <br>，防止 PDF 表格溢出。

    - 含空格的名称（如 "Read Holding Registers"）：直接返回，xhtml2pdf 可按空格自然换行。
    - 无空格名称（如 "TranslateBrowsePathsToNodeIds"、"INITIALIZE_APPLICATION"）：
      在语义边界断行；若断行后单段仍超 max_len，再强制切段。
    """
    import re
    if not name or len(name) <= max_len:
        return name
    if ' ' in name:
        return name
    s = name
    s = re.sub(r'([a-z0-9])([A-Z])', r'\1<br>\2', s)
    s = s.replace('_', '_<br>').replace('-', '-<br>')
    segs = s.split('<br>')
    out = []
    for seg in segs:
        if len(seg) <= max_len:
            out.append(seg)
        else:
            for i in range(0, len(seg), max_len):
                out.append(seg[i:i + max_len])
    return "<br>".join(out)


PROTOCOL_CONFIG = {
    "modbus": {
        "display_name": "Modbus TCP",
        "func_name_map": {
            0x01: "Read Coils",
            0x02: "Read Discrete Inputs",
            0x03: "Read Holding Registers",
            0x04: "Read Input Registers",
            0x05: "Write Single Coil",
            0x06: "Write Single Register",
            0x07: "Read Exception Status",
            0x08: "Diagnostics",
            0x0B: "Get Comm Event Counter",
            0x0C: "Get Comm Event Log",
            0x0F: "Write Multiple Coils",
            0x10: "Write Multiple Registers",
            0x11: "Report Slave ID",
            0x14: "Read File Record",
            0x15: "Write File Record",
            0x16: "Mask Write Register",
            0x17: "Read/Write Multiple Registers",
            0x18: "Read FIFO Queue",
            0x2B: "Read Device Identification",
        },
        "write_funcs": {0x05, 0x06, 0x0F, 0x10, 0x15, 0x16, 0x17},
        "critical_funcs": {0x08, 0x10, 0x0F, 0x17, 0x15},
        "slave_note": {
            "zh": "本报告使用本地 Modbus 模拟从站（基于 pymodbus）进行测试。模拟从站会返回真实的 Modbus 协议异常响应（如 Illegal Function、Illegal Data Address、Illegal Data Value、Slave Device Failure），因此报告中会出现 EXCEPTION 分类。但模拟从站无法完全模拟真实 PLC 的状态机、边界条件和故障处理逻辑。要获得更有意义的模糊测试结果，建议连接真实的 Modbus 设备（PLC、RTU、网关）。",
            "en": "This report was generated against a local Modbus simulator (pymodbus-based). The simulator returns real Modbus exception responses (Illegal Function, Illegal Data Address, Illegal Data Value, Slave Device Failure), so EXCEPTION classifications appear in this report. However, the simulator cannot fully replicate the state machine, boundary conditions, and fault handling of a real PLC. For more meaningful fuzzing results, testing against a real Modbus device (PLC, RTU, gateway) is recommended.",
        },
    },
    "s7comm": {
        "display_name": "S7Comm",
        "func_name_map": {
            0x00: "CPU Services",
            0x04: "Read Variable",
            0x05: "Write Variable",
            0x07: "Block Download",
            0x1A: "Upload",
            0x1B: "End Upload",
            0x1C: "Download Block",
            0x1D: "Download Ended",
            0x1E: "Start Upload",
            0x1F: "Diagnostics",
            0x28: "PLC Stop",
            0x29: "PLC Control",
            0xF0: "Setup Communication",
        },
        "write_funcs": {0x05, 0x07, 0x1C, 0x1D},
        "critical_funcs": {0x28, 0x29, 0x07},
        "slave_note": {
            "zh": "本报告使用本地 S7comm 模拟从站进行测试。该模拟从站仅实现了最简单的请求-响应回环，对所有请求返回固定格式响应，不产生异常响应，因此全 NORMAL 是预期行为。要获得有意义的模糊测试结果，需要连接真实的西门子 PLC。",
            "en": "This report was generated against a local S7comm simulator. The simulator only implements a basic request-response loop, returning a fixed response format for all requests, and does not generate exception responses, so an all-NORMAL result is expected. Meaningful fuzzing results require a real Siemens PLC.",
        },
    },
    "dnp3": {
        "display_name": "DNP3",
        "func_name_map": {
            0x00: "CONFIRM",
            0x01: "READ",
            0x02: "WRITE",
            0x03: "SELECT",
            0x04: "OPERATE",
            0x05: "DIRECT_OPERATE",
            0x06: "DIRECT_OPERATE_NR",
            0x07: "IMMED_FREEZE",
            0x08: "IMMED_FREEZE_NR",
            0x09: "FREEZE_CLEAR",
            0x0A: "FREEZE_CLEAR_NR",
            0x0B: "FREEZE_AT_TIME",
            0x0C: "FREEZE_AT_TIME_NR",
            0x0D: "COLD_RESTART",
            0x0E: "WARM_RESTART",
            0x0F: "INITIALIZE_DATA",
            0x10: "INITIALIZE_APPLICATION",
            0x11: "START_APPLICATION",
            0x12: "STOP_APPLICATION",
            0x13: "SAVE_CONFIGURATION",
            0x14: "ENABLE_UNSOLICITED",
            0x15: "DISABLE_UNSOLICITED",
            0x16: "ASSIGN_CLASS",
            0x17: "DELAY_MEASURE",
            0x18: "RECORD_CURRENT_TIME",
            0x19: "OPEN_FILE",
            0x1A: "CLOSE_FILE",
            0x1B: "DELETE_FILE",
            0x1C: "GET_FILE_INFO",
            0x1D: "AUTHENTICATE_FILE",
            0x1E: "ABORT_FILE",
            0x81: "RESPONSE",
            0x82: "UNSOLICITED_RESPONSE",
        },
        "write_funcs": {0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E},
        "critical_funcs": {0x0D, 0x0E, 0x10, 0x11, 0x12, 0x13},
        "slave_note": {
            "zh": "本报告使用本地 DNP3 模拟从站进行测试。模拟从站仅实现了固定响应回环，用于连通性和报文格式验证。要获得有意义的模糊测试结果，需要连接真实的 DNP3 设备（RTU、IED、网关）。",
            "en": "This report was generated against a local DNP3 simulator. The simulator only implements a basic request-response loop for connectivity testing. Meaningful fuzzing results require a real DNP3 device (RTU, IED, gateway).",
        },
    },
    "iec104": {
        "display_name": "IEC 60870-5-104",
        "func_name_map": {
            0x01: "M_SP_NA_1", 0x02: "M_SP_TA_1", 0x03: "M_DP_NA_1", 0x04: "M_DP_TA_1",
            0x05: "M_ST_NA_1", 0x06: "M_ST_TA_1", 0x07: "M_BO_NA_1", 0x08: "M_BO_TA_1",
            0x09: "M_ME_NA_1", 0x0A: "M_ME_TA_1", 0x0B: "M_ME_NB_1", 0x0C: "M_ME_TB_1",
            0x0D: "M_ME_NC_1", 0x0E: "M_ME_TC_1", 0x0F: "M_IT_NA_1", 0x10: "M_IT_TA_1",
            0x11: "M_EP_TA_1", 0x12: "M_EP_TB_1", 0x13: "M_EP_TC_1", 0x14: "M_PS_NA_1",
            0x15: "M_ME_ND_1", 0x1E: "M_SP_TB_1", 0x1F: "M_DP_TB_1", 0x20: "M_ST_TB_1",
            0x21: "M_BO_TB_1", 0x22: "M_ME_TD_1", 0x23: "M_ME_TE_1", 0x24: "M_ME_TF_1",
            0x25: "M_IT_TB_1", 0x26: "M_EP_TD_1", 0x27: "M_EP_TE_1", 0x28: "M_EP_TF_1",
            0x2D: "C_SC_NA_1", 0x2E: "C_DC_NA_1", 0x2F: "C_RC_NA_1", 0x30: "C_SE_NA_1",
            0x31: "C_SE_NB_1", 0x32: "C_SE_NC_1", 0x33: "C_BO_NA_1", 0x3A: "C_SC_TA_1",
            0x3B: "C_DC_TA_1", 0x3C: "C_RC_TA_1", 0x3D: "C_SE_TA_1", 0x3E: "C_SE_TB_1",
            0x3F: "C_SE_TC_1", 0x40: "C_BO_TA_1", 0x46: "M_EI_NA_1",
            0x64: "C_IC_NA_1", 0x65: "C_CI_NA_1", 0x66: "C_RD_NA_1", 0x67: "C_CS_NA_1",
            0x68: "C_TS_NA_1", 0x69: "C_RP_NA_1", 0x6A: "C_CD_NA_1", 0x6B: "C_TS_TA_1",
            0x6E: "P_ME_NA_1", 0x6F: "P_ME_NB_1", 0x70: "P_ME_NC_1", 0x71: "P_AC_NA_1",
            0x78: "F_FR_NA_1", 0x79: "F_SR_NA_1", 0x7A: "F_SC_NA_1", 0x7B: "F_LS_NA_1",
            0x7C: "F_FA_NA_1", 0x7D: "F_SG_NA_1", 0x7E: "F_DR_TA_1",
        },
        "write_funcs": {0x2D, 0x2E, 0x2F, 0x30, 0x31, 0x32, 0x33, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F, 0x40, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x6B, 0x6E, 0x6F, 0x70, 0x71, 0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E},
        "critical_funcs": {0x64, 0x67, 0x68, 0x69},
        "slave_note": {
            "zh": "本报告使用本地 IEC 104 模拟从站进行测试。模拟从站仅实现了固定响应回环，用于连通性和报文格式验证。要获得有意义的模糊测试结果，需要连接真实的 IEC 104 设备（RTU、IED、网关、调度主站）。",
            "en": "This report was generated against a local IEC 104 simulator. The simulator only implements a basic request-response loop for connectivity testing. Meaningful fuzzing results require a real IEC 104 device (RTU, IED, gateway, SCADA master).",
        },
    },
    "iec61850": {
        "display_name": "IEC 61850 MMS",
        "func_name_map": {
            0x81: "MMS_INITIATE", 0x82: "MMS_INITIATE_ACK",
            0x83: "MMS_CONFIRMED_REQUEST", 0x84: "MMS_CONFIRMED_RESPONSE", 0x85: "MMS_CONFIRMED_ERROR",
            0x86: "MMS_UNCONFIRMED_REQUEST",
            0xA8: "MMS_CANCEL_REQUEST", 0xA9: "MMS_CANCEL_RESPONSE", 0xAA: "MMS_CANCEL_ERROR",
            0xAB: "MMS_CONCLUDE_REQUEST",
            0xAC: "MMS_SERVICE_REQUEST", 0xAD: "MMS_SERVICE_RESPONSE", 0xAE: "MMS_SERVICE_ERROR",
            0xAF: "MMS_UNCONFIRMED_SERVICE",
            0xB0: "MMS_READ_REQUEST", 0xB1: "MMS_READ_RESPONSE",
            0xB2: "MMS_WRITE_REQUEST", 0xB3: "MMS_WRITE_RESPONSE", 0xB4: "MMS_WRITE_ERROR",
            0xB5: "MMS_GET_NAME_LIST_REQUEST", 0xB6: "MMS_GET_NAME_LIST_RESPONSE",
            0xB7: "MMS_IDENTIFY_REQUEST", 0xB8: "MMS_IDENTIFY_RESPONSE",
            0xB9: "MMS_RENAME_REQUEST", 0xBA: "MMS_RENAME_RESPONSE", 0xBB: "MMS_RENAME_ERROR",
            0xBC: "MMS_STATUS_REQUEST", 0xBD: "MMS_STATUS_RESPONSE", 0xBE: "MMS_STATUS_ERROR",
            0xBF: "MMS_GET_FILE_REQUEST", 0xC0: "MMS_GET_FILE_RESPONSE",
            0xC1: "MMS_SET_FILE_REQUEST", 0xC2: "MMS_DELETE_FILE_REQUEST",
            0xC3: "MMS_SET_FILE_RESPONSE", 0xC4: "MMS_DELETE_FILE_RESPONSE",
            0xC5: "MMS_GET_FILE_ATTR_REQUEST", 0xC6: "MMS_GET_FILE_ATTR_RESPONSE",
        },
        "write_funcs": {0x81, 0x83, 0x86, 0xA8, 0xAB, 0xAC, 0xAF, 0xB0, 0xB2, 0xB5, 0xB7, 0xB9, 0xBC, 0xBF, 0xC1, 0xC2, 0xC5},
        "critical_funcs": {0x81, 0xAB, 0xB2, 0xB9, 0xC2, 0xC1},
        "slave_note": {
            "zh": "本报告使用本地 IEC 61850 模拟从站（MMS over ISO 8650 / TCP 102）进行测试。模拟从站仅实现了固定响应回环，用于连通性和报文格式验证。要获得有意义的模糊测试结果，需要连接真实的 IEC 61850 IED（保护装置、测控装置）或 MMS 网关。",
            "en": "This report was generated against a local IEC 61850 simulator (MMS over ISO 8650 / TCP 102). The simulator only implements a basic request-response loop for connectivity testing. Meaningful fuzzing results require a real IEC 61850 IED (protection relay, bay controller) or MMS gateway.",
        },
    },
    "enip": {
        "display_name": "EtherNet/IP CIP",
        "func_name_map": {
            0x01: "Get_Attributes_All", 0x02: "Set_Attributes_All",
            0x03: "Get_Attribute_List", 0x04: "Set_Attribute_List",
            0x05: "Reset", 0x06: "Start", 0x07: "Stop",
            0x08: "Create", 0x09: "Delete",
            0x0A: "Multiple_Service_Packet",
            0x0D: "Apply_Attributes",
            0x0E: "Get_Attribute_Single",
            0x10: "Set_Attribute_Single",
            0x11: "Find_Next_Object_Instance",
            0x14: "Error_Response",
            0x15: "Restore", 0x16: "Save",
            0x17: "No_Operation",
            0x18: "Get_Member", 0x19: "Set_Member",
            0x1A: "Insert_Member", 0x1B: "Remove_Member",
            0x1C: "GroupSync",
            0x4C: "Read_Tag", 0x4D: "Write_Tag",
            0x4E: "Forward_Close",
            0x52: "Unconnected_Send",
            0x54: "Forward_Open",
        },
        "write_funcs": {0x02, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0D, 0x10, 0x15, 0x16, 0x19, 0x1A, 0x1B, 0x1C, 0x4D, 0x52, 0x54},
        "critical_funcs": {0x05, 0x06, 0x07, 0x09, 0x4D, 0x54},
        "slave_note": {
            "zh": "本报告使用本地 EtherNet/IP 模拟从站（CIP over TCP 44818）进行测试。模拟从站仅实现了固定响应回环，用于连通性和报文格式验证。要获得有意义的模糊测试结果，需要连接真实的 EtherNet/IP PLC（罗克韦尔 Logix 系列、施耐德 Modicon 等）或 CIP 网关。",
            "en": "This report was generated against a local EtherNet/IP CIP simulator (TCP 44818). The simulator only implements a basic request-response loop for connectivity testing. Meaningful fuzzing results require a real EtherNet/IP PLC (Rockwell Logix, Schneider Modicon) or CIP gateway.",
        },
    },
    "opcua": {
        "display_name": "OPC UA",
        "func_name_map": {
            446: "OpenSecureChannel", 447: "CloseSecureChannel",
            461: "CreateSession", 462: "ActivateSession", 463: "CloseSession", 464: "Cancel",
            486: "AddNodes", 487: "AddReferences", 488: "DeleteNodes", 489: "DeleteReferences",
            525: "Browse", 526: "BrowseNext", 527: "TranslateBrowsePathsToNodeIds",
            528: "RegisterNodes", 529: "UnregisterNodes",
            629: "Read", 630: "HistoryRead", 673: "Write", 674: "HistoryUpdate",
            712: "Call",
            749: "CreateMonitoredItems", 750: "ModifyMonitoredItems",
            751: "SetMonitoringMode", 752: "DeleteMonitoredItems",
            787: "CreateSubscription", 788: "ModifySubscription",
            789: "SetPublishingMode", 791: "DeleteSubscriptions",
        },
        "write_funcs": {488, 489, 486, 487, 673, 674, 712, 749, 750, 751, 787, 788, 789},
        "critical_funcs": {447, 463, 464, 488, 489, 752, 791},
        "slave_note": {
            "zh": "本报告使用本地 OPC UA 模拟服务器（TCP 4840）进行测试。模拟服务器仅实现了 Hello/ACK + 固定 MSG 块响应回环，用于连通性和报文格式验证。OPC UA 协议支持安全通道（加密 + 签名 + 证书），模糊测试应同时覆盖安全模式 NONE 和 SIGN 两种场景。",
            "en": "This report was generated against a local OPC UA simulator (TCP 4840). The simulator only implements Hello/ACK + fixed MSG chunk responses for connectivity testing. OPC UA supports secure channels (encryption + signature + certificates); fuzzing should cover both NONE and SIGN security modes.",
        },
    },
}


def _get_config(protocol_name):
    return PROTOCOL_CONFIG.get(protocol_name, {})


# 每个协议专属的报告注意事项 / Per-protocol Notes displayed in report
# 格式: {"zh": [("NOTE-P01", "内容", "建议"), ...], "en": [...]}
PROTOCOL_NOTES = {
    "modbus": {
        "zh": [
            ("NOTE-P01", "Modbus TCP 是简单的单请求-响应协议，写操作（0x05/0x06/0x0F/0x10）会持久化到从站寄存器", "测试前记录寄存器快照，测试后校验是否有意外修改"),
            ("NOTE-P02", "功能码 23/24（Read/Write Multiple Registers）处理 > 65535 以上的高位地址，容易触发地址越界 bug", "单独测试高位地址功能码，确认为 DoS 候选后提交"),
        ],
        "en": [
            ("NOTE-P01", "Modbus TCP is simple request-response. Write ops (0x05/0x06/0x0F/0x10) persist to slave registers.", "Record register snapshots before and after testing."),
            ("NOTE-P02", "FC 23/24 handle high addresses > 65535, common source of address-overflow bugs.", "Test high-address FCs separately, confirm DoS candidates."),
        ],
    },
    "s7comm": {
        "zh": [
            ("NOTE-P01", "S7comm 基于 ISO 8650 三层结构（COTP + S7 + ISO TP），变异 COTP 头字节会导致 PLC 拒绝整个请求", "建议关注 COTP length field 和 dst/src ref 的变异效果"),
            ("NOTE-P02", "Setup/Read/Write 命令需要不同的 COTP 头 setup reference，错误 reference 可能导致 PLC 状态机卡死", "对 setup reference 做系统性扫描（0x0000-0xFFFF）"),
        ],
        "en": [
            ("NOTE-P01", "S7comm uses ISO 8650 3-layer stack (COTP+S7+ISO TP). Mutating COTP bytes causes full request rejection.", "Focus on COTP length and dst/src ref mutations."),
            ("NOTE-P02", "Setup/Read/Write need different COTP setup refs. Wrong ref can freeze PLC state machine.", "Systematically scan setup refs 0x0000-0xFFFF."),
        ],
    },
    "dnp3": {
        "zh": [
            ("NOTE-P01", "DNP3 链路层有 CRC16，传输层有 LRC。变异报文需要同步更新 CRC 才能通过校验到达应用层", "CRC/LRC 不匹配的报文会被链路层丢弃，导致所有响应都是 CONN_CLOSED"),
            ("NOTE-P02", "功能码 0x12/0x15 是文件传输，报文可能很长（> 200 字节）", "长报文需要单独的变异策略，避免被截断"),
        ],
        "en": [
            ("NOTE-P01", "DNP3 link layer has CRC16, transport has LRC. Mutations must update both checksums.", "Mismatched CRC/LRC causes link-layer drops, all CONN_CLOSED."),
            ("NOTE-P02", "FC 0x12/0x15 are file transfer, payload can exceed 200 bytes.", "Long payloads need dedicated mutation to avoid truncation."),
        ],
    },
    "iec104": {
        "zh": [
            ("NOTE-P01", "IEC 104 有严格的序号递增机制（Tx 和 Rx 各维护一个），跳过或重复序号会导致通信中断", "变异序号字节时注意，不要让序号跳变过大"),
            ("NOTE-P02", "TESTFR/STARTDT/STOPDT 是控制帧（U 帧/S 帧），错误的控制帧可能导致主从状态机不同步", "单独测试控制帧变异"),
        ],
        "en": [
            ("NOTE-P01", "IEC 104 uses strict sequence numbering (separate Tx/Rx). Skipped/dup sequences cause comms breakdown.", "Don't let seq numbers jump too far in mutations."),
            ("NOTE-P02", "TESTFR/STARTDT/STOPDT are control frames (U/S type). Wrong control frames desync state machines.", "Test control frame mutations separately."),
        ],
    },
    "iec61850": {
        "zh": [
            ("NOTE-P01", "IEC 61850 MMS 基于 ISO 8650 + ASN.1 PER 编码，PDU 结构复杂，invoke ID 必须请求-响应配对", "变异 invoke ID 时保持请求-响应匹配关系"),
            ("NOTE-P02", "IEC 61850 是七层 OSI 完整协议栈（COTP/TPKT/Session/MMS），需要逐层变异", "建议按层（COTP → Session → MMS）逐层变异，观察哪一层最先崩溃"),
        ],
        "en": [
            ("NOTE-P01", "IEC 61850 MMS uses ISO 8650 + ASN.1 PER. Invoke IDs must match request-response pairs.", "Keep invoke ID matching when mutating."),
            ("NOTE-P02", "Full OSI 7-layer stack (COTP/TPKT/Session/MMS). Mutate layer by layer.", "Observe which layer crashes first."),
        ],
    },
    "enip": {
        "zh": [
            ("NOTE-P01", "EtherNet/IP 用 TCP（44818）+ UDP（2222）混合，封装 CIP 协议到 ENIP 层里", "TCP 侧做连接管理变异，UDP 侧做 Implicit Messaging 变异"),
            ("NOTE-P02", "CIP 协议有大量 Object/Attribute 路径，路径变异可能触发未处理的对象访问异常", "重点关注 Path Size + Path Segment 的变异组合"),
        ],
        "en": [
            ("NOTE-P01", "EtherNet/IP uses TCP (44818) + UDP (2222), encapsulates CIP inside ENIP layer.", "Mutate TCP for connection mgmt, UDP for Implicit Messaging."),
            ("NOTE-P02", "CIP has many Object/Attribute paths. Path mutations trigger unhandled object access exceptions.", "Focus on Path Size + Path Segment combinations."),
        ],
    },
    "opcua": {
        "zh": [
            ("NOTE-P01", "OPC UA 是唯一需要先 Hello→ACK 握手再发 MSG 的协议", "没有 Hello 握手的报文会被服务器直接拒绝（CONN_CLOSED），fuzz 已经内置了握手"),
            ("NOTE-P02", "OPC UA 的 Service Node ID（446-791）在二进制报文中不是功能码，而是 ExtensionObject 的 typeId", "变异时不要把 Node ID 当 Modbus 功能码那样替换，要保留 RequestHeader 结构"),
            ("NOTE-P03", "OPC UA MSG chunk 有 type 字段和 chunk header，变异 type=ERR 或 MSG→HEL 可能触发服务器解析异常", "重点变异 chunk type + header flags 字段"),
        ],
        "en": [
            ("NOTE-P01", "OPC UA is the only protocol requiring Hello→ACK handshake before MSG.", "Packets without Hello get rejected (CONN_CLOSED). Fuzz handles handshake internally."),
            ("NOTE-P02", "OPC UA Service Node IDs (446-791) are ExtensionObject typeIds, NOT function codes.", "Don't replace like Modbus FCs. Preserve RequestHeader structure."),
            ("NOTE-P03", "OPC UA MSG chunks have type + chunk header. Mutating type=ERR or MSG→HEL may trigger parse exceptions.", "Focus on chunk type + header flags."),
        ],
    },
}


def _get_protocol_notes(protocol_name, lang="zh"):
    """Return protocol-specific notes for the given protocol."""
    notes_dict = PROTOCOL_NOTES.get(protocol_name, {})
    return notes_dict.get(lang, notes_dict.get("zh", []))


def _get_func_name(func_code, protocol_name):
    cfg = _get_config(protocol_name)
    return cfg.get("func_name_map", {}).get(func_code, "Unknown")


def _get_display_name(protocol_name):
    cfg = _get_config(protocol_name)
    return cfg.get("display_name", protocol_name)


def _get_write_funcs(protocol_name):
    cfg = _get_config(protocol_name)
    return cfg.get("write_funcs", set())


def _get_critical_funcs(protocol_name):
    cfg = _get_config(protocol_name)
    return cfg.get("critical_funcs", set())


def _get_slave_note(protocol_name, lang="zh"):
    cfg = _get_config(protocol_name)
    notes = cfg.get("slave_note", {})
    if notes:
        return notes.get(lang, notes.get("zh", notes.get("en", "")))
    return ""

INFO_LEAK_EXC_CODES = {"01", "02", "03"}

EXC_MEANING_ZH = {
    "01": "Illegal Function（不支持的功能码）",
    "02": "Illegal Data Address（地址越界）",
    "03": "Illegal Data Value（数据值非法）",
    "04": "Slave Device Failure（从站设备故障）",
    "05": "Acknowledge（已接收，处理中）",
    "06": "Slave Device Busy（从站忙）",
    "08": "Memory Parity Error（内存奇偶校验错误）",
    "0A": "Gateway Path Unavailable（网关路径不可用）",
    "0B": "Gateway Target Device Failed to Respond（目标设备无响应）",
}
EXC_MEANING_EN = {
    "01": "Illegal Function",
    "02": "Illegal Data Address",
    "03": "Illegal Data Value",
    "04": "Slave Device Failure",
    "05": "Acknowledge",
    "06": "Slave Device Busy",
    "08": "Memory Parity Error",
    "0A": "Gateway Path Unavailable",
    "0B": "Gateway Target Device Failed to Respond",
}

IMPACTS = {
    "info_leak": (
        "异常码 0x{code} 泄露服务端功能/地址/数据校验逻辑，可能被攻击者用于指纹识别",
        "Exception code 0x{code} leaks server function/address/data validation logic, may be used for fingerprinting",
    ),
    "device_fault": (
        "异常码 0x{code} 暴露从站设备故障或状态，可能被用于状态探测",
        "Exception code 0x{code} exposes slave device fault or status, may be used for state probing",
    ),
    "no_exc_code": (
        "异常响应缺少可识别异常码，暴露服务端错误处理细节",
        "Exception response lacks identifiable code, exposes server error handling details",
    ),
    "empty_resp": (
        "空响应，可能导致客户端挂起或连接超时",
        "Empty response, may cause client hang or connection timeout",
    ),
    "critical_disconnect": (
        "关键写/诊断功能导致连接断开，可能造成 PLC 状态混乱或服务崩溃",
        "Critical write/diagnostic function caused disconnect, may cause PLC state chaos or service crash",
    ),
    "write_disconnect": (
        "写操作导致连接断开，存在远程 DoS 风险",
        "Write operation caused disconnect, potential remote DoS risk",
    ),
    "read_disconnect": (
        "读操作导致连接断开，可能被用于连接资源耗尽攻击",
        "Read operation caused disconnect, may be used for connection resource exhaustion attack",
    ),
    "unclassified": (
        "未分类",
        "Unclassified",
    ),
}

SEVERITY_LABEL = {
    "high": ("高危 (High)", "High"),
    "medium": ("中危 (Medium)", "Medium"),
    "low": ("低危 (Low)", "Low"),
}


def _get_impact(key, code="", lang="zh"):
    zh, en = IMPACTS.get(key, IMPACTS["unclassified"])
    template = zh if lang == "zh" else en
    return template.format(code=code)


def classify_severity(func_code, classification, response_hex, protocol_name="modbus"):
    if classification == "NORMAL":
        return None, None, None, ""

    if classification == "EXCEPTION":
        code = ""
        offset = _EXCEPTION_CODE_OFFSET.get((protocol_name or "").lower())
        if response_hex and offset and len(response_hex) >= offset[1]:
            code = response_hex[offset[0]:offset[1]].lower()
        if code in INFO_LEAK_EXC_CODES:
            return "low", "low", "info_leak", code
        if code:
            return "medium", "medium", "device_fault", code
        return "medium", "medium", "no_exc_code", ""

    if classification == "EMPTY":
        return "medium", "medium", "empty_resp", ""

    if classification == "CONN_CLOSED":
        critical = _get_critical_funcs(protocol_name)
        write_funcs = _get_write_funcs(protocol_name)
        if func_code in critical:
            return "high", "high", "critical_disconnect", ""
        if func_code in write_funcs:
            return "high", "high", "write_disconnect", ""
        return "medium", "medium", "read_disconnect", ""

    return "medium", "medium", "unclassified", ""


def _render_severity_group(level_class, level_title, items, protocol_name, lang="zh"):
    def t(zh, en):
        return zh if lang == "zh" else en

    html = []
    html.append(f"<h3 class='{level_class}'>{level_title} — {t('共', 'Total')} {len(items)} {t('项', 'items')}</h3>")
    html.append("<table class='filterable'>")
    html.append("<colgroup>")
    html.append("<col style='width:8%'>")
    html.append("<col style='width:17%'>")
    html.append("<col style='width:33%'>")
    html.append("<col style='width:12%'>")
    html.append("<col style='width:30%'>")
    html.append("</colgroup>")
    html.append(
        f"<tr><th>{t('轮次', 'Round')}</th>"
        f"<th>{t('功能码', 'Function Code')}</th>"
        f"<th>{t('变异报文', 'Mutation')}</th>"
        f"<th>{t('分类', 'Class')}</th>"
        f"<th>{t('潜在影响 / Impact', 'Impact')}</th></tr>"
    )
    if items:
        for r in items:
            fc = r.get("func_code", 0)
            fname = _break_func_name(_get_func_name(fc, protocol_name))
            mut = r.get('mutation', '') or ''
            impact = r.get('impact', '') or ''
            html.append(
                f"<tr class='{level_class}' data-severity='{level_class}' data-func='0x{fc:02X}'>"
                f"<td>{r.get('round','')}</td>"
                f"<td>0x{fc:02X} ({fname})</td>"
                f"<td>{_break_long_text(mut, 14)}</td>"
                f"<td>{r.get('classification','')}</td>"
                f"<td>{impact}</td>"
                f"</tr>"
            )
    else:
        html.append(f"<tr><td colspan='5'>{t('该等级无记录 / None', 'None')}</td></tr>")
    html.append("</table>")
    return html


def _build_timeline_data(results, protocol_name):
    timeline = []
    for r in results:
        cls = r.get("classification", "")
        if cls in ("CONN_CLOSED", "EXCEPTION", "EMPTY"):
            lvl_class, _, _, _ = classify_severity(
                r.get("func_code", 0), cls, r.get("response", ""), protocol_name
            )
            if lvl_class:
                timeline.append({
                    "round": r.get("round", 0),
                    "func_name": _get_func_name(r.get("func_code", 0), protocol_name),
                    "severity": lvl_class,
                    "classification": cls,
                    "mutation": r.get("mutation", ""),
                })
    timeline.sort(key=lambda x: x["round"])
    return timeline


def _render_timeline_svg(timeline_data):
    if not timeline_data:
        return "<p>No risk records.</p>"

    width = 900
    height = 200
    padding_left = 60
    padding_right = 30
    padding_top = 30
    padding_bottom = 40
    chart_width = width - padding_left - padding_right
    chart_height = height - padding_top - padding_bottom

    max_round = max(d["round"] for d in timeline_data)
    min_round = min(d["round"] for d in timeline_data)
    round_range = max(max_round - min_round, 1)

    severity_color = {"high": "#ff8a80", "medium": "#ffe082", "low": "#c8e6c9"}
    severity_radius = {"high": 8, "medium": 6, "low": 4}

    svg = [f'<svg width="{width}" height="{height}" style="background:#fff;border:1px solid #ddd;">']
    svg.append(f'<line x1="{padding_left}" y1="{height - padding_bottom}" x2="{width - padding_right}" y2="{height - padding_bottom}" stroke="#ccc" stroke-width="1"/>')

    for i in range(min_round, max_round + 1, max(1, round_range // 10)):
        x = padding_left + ((i - min_round) / round_range) * chart_width
        svg.append(f'<text x="{x}" y="{height - padding_bottom + 18}" text-anchor="middle" font-size="10" fill="#666">R{i}</text>')

    for d in timeline_data:
        x = padding_left + ((d["round"] - min_round) / round_range) * chart_width
        y_map = {"high": padding_top + 20, "medium": padding_top + chart_height // 2, "low": height - padding_bottom - 20}
        y = y_map.get(d["severity"], padding_top + chart_height // 2)
        color = severity_color.get(d["severity"], "#999")
        radius = severity_radius.get(d["severity"], 5)
        svg.append(f'<circle cx="{x}" cy="{y}" r="{radius}" fill="{color}" stroke="#fff" stroke-width="1.5"><title>R{d["round"]} {d["func_name"]} | {d["severity"]} | {d["classification"]}</title></circle>')

    legend_x = padding_left + 10
    for label, color in [("High", "#ff8a80"), ("Medium", "#ffe082"), ("Low", "#c8e6c9")]:
        svg.append(f'<circle cx="{legend_x}" cy="15" r="5" fill="{color}"/>')
        svg.append(f'<text x="{legend_x + 10}" y="19" font-size="11" fill="#333">{label}</text>')
        legend_x += 70

    svg.append("</svg>")
    return "\n".join(svg)


def _render_slave_notice(protocol_name, scenario, lang="zh", slave_mode="strict"):
    html = []
    if scenario != "local":
        if lang == "zh":
            title = "⚠️ 真实设备测试声明"
            text = "本报告针对真实工业设备进行测试。测试前已获得设备所有者授权，测试网络与生产网络物理隔离。"
        else:
            title = "⚠️ Real Device Testing Notice"
            text = "This report is based on testing against real industrial equipment. Authorization from the device owner was obtained prior to testing, and the test network is physically isolated from the production network."
        html.append("<div class='warning-box'>")
        html.append(f"<strong>{title}</strong><br>")
        html.append(text)
        html.append("</div>")
        return html
    if lang == "zh":
        mode_text = "严格（从站校验请求报文）" if slave_mode == "strict" else "宽松（从站固定响应）"
        html.append(f"<p><strong>模拟从站模式：</strong>{mode_text}</p>")
    else:
        mode_text = "Strict (slave validates request frames)" if slave_mode == "strict" else "Loose (slave replies with fixed responses)"
        html.append(f"<p><strong>Slave Mode:</strong> {mode_text}</p>")
    if slave_mode != "strict":
        if lang == "zh":
            warn_title = "⚠️ 宽松模式警示"
            warn_text = "当前为宽松模式，模拟从站对所有请求返回固定正常响应，测试结果全 NORMAL 是预期行为。建议在菜单确认页输入 L 切换为严格模式，以获得有意义的分类结果。"
        else:
            warn_title = "⚠️ Loose Mode Warning"
            warn_text = "The simulated slave returns a fixed normal response to every request, so all-NORMAL results are expected. Press L on the confirmation page to switch to strict mode for meaningful classifications."
        html.append("<div class='warning-box'>")
        html.append(f"<strong>{warn_title}</strong><br>")
        html.append(warn_text)
        html.append("</div>")
    text = _get_slave_note(protocol_name, lang)
    if text:
        title_zh = "⚠️ 模拟从站说明"
        title_en = "⚠️ Simulator Notice"
        title = title_zh if lang == "zh" else title_en
        html.append("<div class='warning-box'>")
        html.append(f"<strong>{title}</strong><br>")
        html.append(text)
        html.append("</div>")
    return html


def _build_html(results, skipped, build_failures, protocol_name, target, scenario="lan", lang="zh", llm_status=None, slave_mode="strict", protocol_timed_out=False, protocol_timeout=120):
    def t(zh, en):
        return zh if lang == "zh" else en

    for r in results:
        _, sev_key, imp_key, code = classify_severity(
            r.get("func_code", 0), r.get("classification", ""), r.get("response", ""), protocol_name
        )
        r["severity"] = sev_key
        r["severity_label"] = SEVERITY_LABEL.get(sev_key, ("", ""))[0 if lang == "zh" else 1] if sev_key else ""
        r["impact"] = _get_impact(imp_key, code, lang) if imp_key else ""
        r["func_name"] = _get_func_name(r.get("func_code", 0), protocol_name)

    total = len(results)
    normal = sum(1 for r in results if r.get("classification") == "NORMAL")
    exception = sum(1 for r in results if r.get("classification") == "EXCEPTION")
    conn_closed = sum(1 for r in results if r.get("classification") == "CONN_CLOSED")
    empty = sum(1 for r in results if r.get("classification") == "EMPTY")

    # 复用 result_analyzer 的分发表（按协议分发偏移，hex 字符语义）
    exception_groups = analyze_results(results)["exception_groups"]

    func_stats = {}
    for r in results:
        fc = r.get("func_code", 0)
        if fc not in func_stats:
            func_stats[fc] = {"total": 0, "NORMAL": 0, "EXCEPTION": 0, "CONN_CLOSED": 0, "EMPTY": 0}
        func_stats[fc]["total"] += 1
        cls = r.get("classification", "")
        if cls in func_stats[fc]:
            func_stats[fc][cls] += 1

    suspicious = [r for r in results if r.get("classification") in ("CONN_CLOSED", "EXCEPTION", "EMPTY")]
    high_items = [r for r in suspicious if r.get("severity") == "high"]
    medium_items = [r for r in suspicious if r.get("severity") == "medium"]
    low_items = [r for r in suspicious if r.get("severity") == "low"]

    timeline_data = _build_timeline_data(results, protocol_name)
    timeline_svg = _render_timeline_svg(timeline_data)

    protocol_display = _get_display_name(protocol_name)

    h = []
    h.append("<!DOCTYPE html>")
    h.append("<html lang='zh-CN'><head><meta charset='UTF-8'>")
    h.append(f"<title>{protocol_display} Fuzz Test Report</title>")
    h.append("<style>")
    h.append("body{font-family:'Microsoft YaHei','SimSun',Arial,sans-serif;padding:20px;background:#f5f8fa;color:#1a2a3a;}")
    h.append("h1{color:#2d8a4e;} h2{color:#1a2a4a;margin-top:30px;}")
    h.append("h3{margin-top:20px;padding:6px 10px;}")
    h.append("table{width:100%;border-collapse:collapse;margin-top:12px;background:#fff;}")
    h.append("table.filterable{table-layout:fixed;}")
    h.append("th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;font-size:12px;word-wrap:break-word;overflow-wrap:break-word;vertical-align:top;}")
    h.append("th{background:#f2f2f2;}")
    h.append("td{line-height:1.4;}")
    h.append(".normal{background:#e0f7fa;} .exception{background:#ffcdd2;}")
    h.append(".conn{background:#fff3e0;} .skip{background:#fff9c4;} .fail{background:#f8bbd0;}")
    h.append(".high{background:#ff8a80;font-weight:bold;} .medium{background:#ffe082;} .low{background:#c8e6c9;}")
    h.append("h3.high{background:#ff8a80;} h3.medium{background:#ffe082;} h3.low{background:#c8e6c9;}")
    h.append(".filter-bar{background:#fff;padding:12px;border:1px solid #ddd;margin:16px 0;}")
    h.append(".filter-bar button{margin:2px 6px;padding:6px 14px;border:1px solid #ccc;cursor:pointer;background:#f9f9f9;}")
    h.append(".filter-bar button.active{background:#2d8a4e;color:#fff;border-color:#2d8a4e;}")
    h.append(".filter-bar select{margin:2px 6px;padding:6px 10px;border:1px solid #ccc;}")
    h.append(".notice-box{background:#fff9c4;border-left:4px solid #fbc02d;padding:10px 16px;margin:12px 0;font-size:13px;}")
    h.append(".warning-box{background:#fff3cd;border:2px solid #ffc107;border-radius:6px;padding:14px 18px;margin:20px 0;font-size:14px;line-height:1.7;}")
    h.append("</style></head><body>")

    h.append(f"<h1>{t(f'{protocol_display} 模糊测试报告 / {protocol_display} Fuzz Test Report', f'{protocol_display} Fuzz Test Report')}</h1>")
    h.append(f"<p><strong>{t('生成时间 / Generated', 'Generated')}:</strong> {datetime.now().strftime('%Y%m%d_%H%M%S')} | <strong>{t('版本 / Version', 'Version')}:</strong> {__version__}</p>")
    if scenario == "local":
        h.append(f"<p><strong>{t('目标 / Target', 'Target')}:</strong> {_esc(target)}</p>")
    else:
        tag = t("（真实设备）", "(Real Device)")
        h.append(f"<p><strong>{t('目标 / Target', 'Target')}:</strong> {_esc(target)} <span style='color:#d32f2f;font-weight:bold;'>{tag}</span></p>")
        scenario_label = {"lan": t("局域网", "LAN"), "production": t("生产环境", "Production")}.get(scenario, scenario)
        h.append(f"<p><strong>{t('场景 / Scenario', 'Scenario')}:</strong> {scenario_label} | <strong>{t('授权 / Authorization', 'Authorization')}:</strong> {t('已确认', 'Confirmed')}</p>")

    h.extend(_render_slave_notice(protocol_name, scenario, lang, slave_mode))

    if protocol_timed_out:
        if lang == "zh":
            h.append("<div class='warning-box'>")
            h.append(f"<strong>⚠️ 本协议 fuzz 被强制中断</strong><br>")
            h.append(f"fuzz 运行超过 {protocol_timeout} 秒（整体协议超时上限），系统强制终止并基于已收集的 {len(results)} 条结果生成此报告。")
            h.append("<br><br>")
            h.append(f"<strong>最可能原因：</strong>LLM 推理过慢（尤其是本地 Ollama 大模型在 CPU 上），导致功能码未全部跑完。")
            h.append("<br>")
            h.append(f"<strong>建议：</strong>1) 选择更少的功能码（5-10 个）；2) 使用更小的本地模型（如 qwen2.5-coder:3b）；3) 启用 GPU 加速。")
            h.append("</div>")
        else:
            h.append("<div class='warning-box'>")
            h.append(f"<strong>⚠️ This protocol fuzz was forcefully terminated</strong><br>")
            h.append(f"Fuzz exceeded {protocol_timeout}s (protocol timeout limit) and was forcibly stopped. This report is based on {len(results)} collected results.")
            h.append("<br><br>")
            h.append(f"<strong>Likely cause:</strong> Slow LLM inference (especially local Ollama large models on CPU), preventing all function codes from completing.")
            h.append("<br>")
            h.append(f"<strong>Suggestions:</strong> 1) Select fewer function codes (5-10); 2) Use a smaller local model (e.g. qwen2.5-coder:3b); 3) Enable GPU acceleration.")
            h.append("</div>")

    # LLM status warning (if any issues)
    if llm_status is not None and getattr(llm_status, "has_warning", False):
        h.append(llm_status.build_warning_html(lang))

    try:
        from src.core.runtime_config import is_gpu_enabled, get_gpu_summary
        if is_gpu_enabled():
            gpu_info = _esc(get_gpu_summary())
            if lang == "zh":
                h.append(f"<p><strong>GPU 加速：</strong>已启用（{gpu_info}）</p>")
            else:
                h.append(f"<p><strong>GPU Acceleration:</strong> Enabled ({gpu_info})</p>")
    except Exception:
        pass

    h.append(f"<h2>{t('统计摘要 / Summary', 'Summary')}</h2>")
    h.append("<table>")
    h.append(f"<tr><th>{t('指标 / Metric', 'Metric')}</th><th>{t('数值 / Value', 'Value')}</th></tr>")
    h.append(f"<tr><td>{t('总测试数 / Total Tests', 'Total Tests')}</td><td>{total}</td></tr>")
    h.append(f"<tr><td>{t('NORMAL / 正常', 'NORMAL')}</td><td>{normal}</td></tr>")
    h.append(f"<tr><td>{t('EXCEPTION / 异常', 'EXCEPTION')}</td><td>{exception}</td></tr>")
    h.append(f"<tr><td>{t('CONN_CLOSED / 连接关闭', 'CONN_CLOSED')}</td><td>{conn_closed}</td></tr>")
    h.append(f"<tr><td>{t('EMPTY / 空响应', 'EMPTY')}</td><td>{empty}</td></tr>")
    h.append(f"<tr><td>{t('跳过的功能码 / Skipped', 'Skipped')}</td><td>{len(skipped)}</td></tr>")
    h.append(f"<tr><td>{t('构建/变异失败 / Build Failures', 'Build Failures')}</td><td>{len(build_failures)}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('漏洞时间线 / Vulnerability Timeline', 'Vulnerability Timeline')}</h2>")
    if lang == "zh":
        h.append("<p>按测试轮次展示风险点分布，圆点颜色表示风险等级，悬停查看详情。</p>")
        h.append(timeline_svg)
    else:
        h.append("<p>Risk points distributed by test round. See Severity Details below for full list.</p>")

    h.append(f"<h2>{t('风险等级分布 / Severity Distribution', 'Severity Distribution')}</h2>")
    h.append("<table>")
    h.append(f"<tr><th>{t('风险等级 / Severity', 'Severity')}</th><th>{t('数量 / Count', 'Count')}</th><th>{t('说明 / Description', 'Description')}</th></tr>")
    h.append(f"<tr class='high'><td>{t('高危 (High)', 'High')}</td><td>{len(high_items)}</td><td>{t('可能导致设备崩溃、拒绝服务、状态混乱，需立即修复', 'May cause device crash, DoS, state chaos. Immediate fix required.')}</td></tr>")
    h.append(f"<tr class='medium'><td>{t('中危 (Medium)', 'Medium')}</td><td>{len(medium_items)}</td><td>{t('可能被利用做资源耗尽或状态探测攻击，建议下一版本修复', 'May be exploited for resource exhaustion or state probing. Fix in next release.')}</td></tr>")
    h.append(f"<tr class='low'><td>{t('低危 (Low)', 'Low')}</td><td>{len(low_items)}</td><td>{t('信息泄露、异常处理细节暴露，建议加固', 'Information leak / error handling details exposed. Harden recommended.')}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('风险等级详情 / Severity Details', 'Severity Details')}</h2>")
    h.append("<div class='filter-bar'>")
    h.append(f"<strong>{t('风险等级筛选：', 'Severity Filter:')}</strong>")
    h.append(f"<button class='active' onclick='filterBySeverity(\"all\", event)'>{t('全部', 'All')}</button>")
    h.append(f"<button onclick='filterBySeverity(\"high\", event)'>{t('🔴 高危', '🔴 High')}</button>")
    h.append(f"<button onclick='filterBySeverity(\"medium\", event)'>{t('🟡 中危', '🟡 Medium')}</button>")
    h.append(f"<button onclick='filterBySeverity(\"low\", event)'>{t('🟢 低危', '🟢 Low')}</button>")
    h.append(f"<strong style='margin-left:20px;'>{t('功能码筛选：', 'Function Code:')}</strong>")
    h.append("<select id='funcFilter' onchange='filterByFunc(this.value)'>")
    h.append(f"<option value='all'>{t('全部', 'All')}</option>")
    for fc in sorted(func_stats.keys()):
        fname = _get_func_name(fc, protocol_name)
        h.append(f"<option value='0x{fc:02X}'>0x{fc:02X} ({fname})</option>")
    h.append("</select>")
    h.append("</div>")

    h.extend(_render_severity_group("high", t("🔴 高危 (High)", "🔴 High"), high_items, protocol_name, lang))
    h.extend(_render_severity_group("medium", t("🟡 中危 (Medium)", "🟡 Medium"), medium_items, protocol_name, lang))
    h.extend(_render_severity_group("low", t("🟢 低危 (Low)", "🟢 Low"), low_items, protocol_name, lang))

    h.append(f"<h2>{t('跳过的测试 / Skipped Tests', 'Skipped Tests')}</h2>")
    h.append("<table class='filterable'>")
    h.append("<colgroup><col style='width:12%'><col style='width:18%'><col style='width:70%'></colgroup>")
    h.append(f"<tr><th>{t('轮次 / Round', 'Round')}</th><th>{t('功能码 / Func', 'Func')}</th><th>{t('跳过原因 / Reason', 'Reason')}</th></tr>")
    if skipped:
        for s in skipped:
            fc = s.get('func_code', 0)
            try:
                fc_str = f"0x{int(fc):02X}" if not isinstance(fc, str) else fc
            except Exception:
                fc_str = str(fc)
            h.append(f"<tr class='skip'><td>{s.get('round','')}</td><td>{fc_str}</td><td>{_esc(s.get('reason',''))}</td></tr>")
    else:
        h.append(f"<tr><td colspan='3'>{t('无跳过项 / None', 'None')}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('构建与变异失败 / Build & Mutation Failures', 'Build & Mutation Failures')}</h2>")
    h.append("<table class='filterable'>")
    h.append("<colgroup><col style='width:15%'><col style='width:20%'><col style='width:65%'></colgroup>")
    h.append(f"<tr><th>{t('功能码 / Func', 'Func')}</th><th>{t('失败阶段 / Stage', 'Stage')}</th><th>{t('失败原因 / Reason', 'Reason')}</th></tr>")
    if build_failures:
        for f in build_failures:
            fc = f.get('func_code', 0)
            try:
                fc_str = f"0x{int(fc):02X}" if not isinstance(fc, str) else fc
            except Exception:
                fc_str = str(fc)
            h.append(f"<tr class='fail'><td>{fc_str}</td><td>{f.get('stage','')}</td><td>{_esc(f.get('reason',''))}</td></tr>")
    else:
        h.append(f"<tr><td colspan='3'>{t('无构建失败 / None', 'None')}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('异常分布 / Exception Distribution', 'Exception Distribution')}</h2>")
    h.append("<table>")
    h.append(f"<tr><th>{t('异常码 / Exception Code', 'Exception Code')}</th><th>{t('次数 / Count', 'Count')}</th><th>{t('含义 / Meaning', 'Meaning')}</th></tr>")
    for code, cnt in sorted(exception_groups.items()):
        meaning = EXC_MEANING_ZH.get(code.upper(), "未知") if lang == "zh" else EXC_MEANING_EN.get(code.upper(), "Unknown")
        h.append(f"<tr><td>{code}</td><td>{cnt}</td><td>{meaning}</td></tr>")
    if not exception_groups:
        h.append(f"<tr><td colspan='3'>{t('无异常记录 / No exceptions', 'No exceptions')}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('按功能码统计 / Per-Function Statistics', 'Per-Function Statistics')}</h2>")
    h.append("<table class='filterable'>")
    h.append("<colgroup><col style='width:10%'><col style='width:34%'><col style='width:9%'><col style='width:11%'><col style='width:14%'><col style='width:22%'></colgroup>")
    h.append(f"<tr><th>{t('功能码 / Func Code', 'Func Code')}</th><th>{t('名称 / Name', 'Name')}</th><th>{t('总数 / Total', 'Total')}</th><th>NORMAL</th><th>EXCEPTION</th><th>CONN_CLOSED</th></tr>")
    for fc in sorted(func_stats.keys()):
        s = func_stats[fc]
        h.append(f"<tr><td>0x{fc:02X}</td><td>{_break_func_name(_get_func_name(fc, protocol_name))}</td><td>{s['total']}</td><td>{s['NORMAL']}</td><td>{s['EXCEPTION']}</td><td>{s['CONN_CLOSED']}</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('注意事项 / Notes', 'Notes')}</h2>")
    h.append("<table class='filterable'>")
    h.append("<colgroup><col style='width:12%'><col style='width:50%'><col style='width:38%'></colgroup>")
    h.append(f"<tr><th>{t('编号 / ID', 'ID')}</th><th>{t('内容 / Content', 'Content')}</th><th>{t('建议 / Recommendation', 'Recommendation')}</th></tr>")

    # Protocol-specific notes first (NOTE-Pxx)
    for nid, content, rec in _get_protocol_notes(protocol_name, lang):
        h.append(f"<tr><td>{nid}</td><td>{content}</td><td>{rec}</td></tr>")

    # Generic notes (NOTE-xx) - NOTE-02 removed (now covered by llm_status warning box)
    if lang == "zh":
        h.append("<tr><td>NOTE-01</td><td>CONN_CLOSED 无法区分目标主动拒绝还是目标进程崩溃</td><td>对高危等级报文做二次复现，确认为 DoS 候选后提交修复</td></tr>")
        h.append("<tr><td>NOTE-02</td><td>Windows 下缺少 Npcap 会导致 Scapy pcap provider 不可用</td><td>可选装 Npcap，但不影响基于 socket 的模糊测试</td></tr>")
        h.append("<tr><td>NOTE-03</td><td>模糊测试会污染从站内部状态（连接队列、寄存器值等）</td><td>每轮测试前重启从站，保证测试基线干净、结果可比</td></tr>")
        h.append(f"<tr><td>NOTE-04</td><td>本报告仅对测试目标 {_esc(target)} 有效</td><td>禁止在未授权的生产环境上运行本工具</td></tr>")
        if scenario == "local":
            h.append(f"<tr><td>NOTE-05</td><td>本测试使用的是协议模拟从站，仅用于连通性验证</td><td>要获得有意义的模糊测试结果，请连接真实设备</td></tr>")
        else:
            h.append(f"<tr><td>NOTE-05</td><td>本测试针对真实工业设备，所有变异报文已实际发送至目标</td><td>发现异常响应或连接中断时，需结合设备日志人工确认是否为漏洞</td></tr>")
    else:
        h.append("<tr><td>NOTE-01</td><td>CONN_CLOSED cannot distinguish target rejection from target crash.</td><td>Reproduce high-severity packets to confirm DoS candidates.</td></tr>")
        h.append("<tr><td>NOTE-02</td><td>Missing Npcap on Windows disables Scapy pcap provider.</td><td>Optional. Does not affect socket-based fuzzing.</td></tr>")
        h.append("<tr><td>NOTE-03</td><td>Fuzzing pollutes slave internal state (connection queue, register values).</td><td>Restart slave before each test round for clean baseline.</td></tr>")
        h.append(f"<tr><td>NOTE-04</td><td>This report is valid only for the target {_esc(target)}.</td><td>Do not run this tool against unauthorized production systems.</td></tr>")
        if scenario == "local":
            h.append(f"<tr><td>NOTE-05</td><td>This test was run against a protocol simulator.</td><td>Use a real device for meaningful fuzzing results.</td></tr>")
        else:
            h.append(f"<tr><td>NOTE-05</td><td>This test targeted real industrial equipment; all mutated packets were sent to the target.</td><td>When abnormal responses or connection drops occur, cross-check with device logs to confirm vulnerabilities.</td></tr>")
    h.append("</table>")

    h.append(f"<h2>{t('数据库比对说明 / Vulnerability Database Notes', 'Vulnerability Database Notes')}</h2>")
    h.append("<div class='notice-box'>")
    if lang == "zh":
        h.append("<strong>⚠️ CNVD / CVE 数据库自动比对暂不支持</strong><br>")
        h.append(f"当前版本（v{__version__}）暂未集成 CNVD、CVE 等漏洞数据库的自动比对功能，原因如下：<br>")
        h.append("<ul>")
        h.append("<li><strong>CNVD</strong>：未提供公开的免费查询 API，官方数据接口需要授权或付费接入。</li>")
        h.append("<li><strong>CVE / NVD</strong>：NVD API v2.0 虽免费，但存在严格速率限制（无 API Key 时 6 秒/次），且需要在打包 EXE 时处理网络异常与离线降级。</li>")
        h.append("<li><strong>CNVD / CNNVD 商业 API</strong>：腾讯云、ThreatBook 等提供的漏洞库查询接口为付费服务，暂不纳入当前版本。</li>")
        h.append("</ul>")
        h.append("<strong>后续规划：</strong>v2.0 桌面端版本将评估以下方案：<br>")
        h.append("<ol>")
        h.append("<li>集成 NVD API（免费，带速率限制和本地缓存）。</li>")
        h.append("<li>允许用户自行配置第三方漏洞库 API Key，由用户承担费用。</li>")
        h.append("<li>支持离线漏洞库快照（定期从 NVD 导出 Modbus 相关 CVE 数据）。</li>")
        h.append("</ol>")
        h.append("<strong>当前替代方案：</strong>报告中的风险条目可按功能码和分类，人工在 NVD 或 CNVD 官网检索比对。")
    else:
        h.append("<strong>⚠️ CNVD / CVE Auto-Matching Not Supported Yet</strong><br>")
        h.append(f"Version v{__version__} does not integrate CNVD / CVE database auto-matching. Reasons:<br>")
        h.append("<ul>")
        h.append("<li><strong>CNVD</strong>: No public free query API. Official data access requires authorization or payment.</li>")
        h.append("<li><strong>CVE / NVD</strong>: NVD API v2.0 is free but heavily rate-limited (6s/request without API Key). Handling network failures and offline fallback in a single-file EXE adds significant complexity.</li>")
        h.append("<li><strong>CNVD / CNNVD Commercial API</strong>: Tencent Cloud, ThreatBook, etc. are paid services. Not included in this version.</li>")
        h.append("</ul>")
        h.append("<strong>Roadmap for v2.0 Desktop App:</strong><br>")
        h.append("<ol>")
        h.append("<li>Integrate NVD API (free, with rate limiting and local caching).</li>")
        h.append("<li>Allow users to configure their own third-party vulnerability DB API Keys (cost borne by user).</li>")
        h.append("<li>Support offline vulnerability DB snapshots (periodically exported Modbus-related CVE data from NVD).</li>")
        h.append("</ol>")
        h.append("<strong>Current Alternative:</strong> Manually cross-check risk entries by function code and class on NVD or CNVD websites.")
    h.append("</div>")

    if lang == "zh":
        h.append("<script>")
        h.append("""
        var currentSeverity = 'all';
        var currentFunc = 'all';
        function filterBySeverity(severity, event) {
            currentSeverity = severity;
            applyFilter();
            var buttons = document.querySelectorAll('.filter-bar button');
            buttons.forEach(function(b) { b.classList.remove('active'); });
            if (event && event.target) { event.target.classList.add('active'); }
        }
        function filterByFunc(func) { currentFunc = func; applyFilter(); }
        function applyFilter() {
            var rows = document.querySelectorAll('table.filterable tr[data-severity]');
            rows.forEach(function(row) {
                var sevMatch = (currentSeverity === 'all' || row.getAttribute('data-severity') === currentSeverity);
                var funcMatch = (currentFunc === 'all' || row.getAttribute('data-func') === currentFunc);
                row.style.display = (sevMatch && funcMatch) ? '' : 'none';
            });
        }
        """)
        h.append("</script>")

    h.append("</body></html>")
    return "\n".join(h)


def generate_report(results, skipped=None, build_failures=None, protocol_name="modbus", target="127.0.0.1:5020", scenario="lan", llm_status=None, slave_mode="strict", protocol_timed_out=False, protocol_timeout=120):
    skipped = skipped or []
    build_failures = build_failures or []

    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"report_{protocol_name}_{timestamp}.html")
    log_path = os.path.join(REPORT_DIR, f"run_{protocol_name}_{timestamp}.log")
    pdf_path = os.path.join(REPORT_DIR, f"report_{protocol_name}_{timestamp}.pdf")
    tmp_en_html = os.path.join(REPORT_DIR, f"_en_tmp_{protocol_name}_{timestamp}.html")

    html_zh = _build_html(results, skipped, build_failures, protocol_name, target, scenario, lang="zh", llm_status=llm_status, slave_mode=slave_mode, protocol_timed_out=protocol_timed_out, protocol_timeout=protocol_timeout)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html_zh)

    html_en = _build_html(results, skipped, build_failures, protocol_name, target, scenario, lang="en", llm_status=llm_status, slave_mode=slave_mode, protocol_timed_out=protocol_timed_out, protocol_timeout=protocol_timeout)
    with open(tmp_en_html, "w", encoding="utf-8") as f:
        f.write(html_en)

    with open(log_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(f"Round: {r.get('round')}, FuncCode: 0x{r.get('func_code',0):02X}, ")
            f.write(f"Mutation: {r.get('mutation')}, Response: {r.get('response')}, ")
            f.write(f"Classification: {r.get('classification')}, Severity: {r.get('severity','')}\n")
        f.write("\n--- Skipped ---\n")
        for s in skipped:
            f.write(f"Skipped Round {s.get('round')} Func {s.get('func_code')}: {s.get('reason')}\n")
        f.write("\n--- Build Failures ---\n")
        for b in build_failures:
            f.write(f"Func {b.get('func_code')} [{b.get('stage')}]: {b.get('reason')}\n")

    try:
        from xhtml2pdf import pisa
        _register_cn_font()
        with open(tmp_en_html, "rb") as src:
            with open(pdf_path, "wb") as dst:
                pisa_status = pisa.CreatePDF(src, dest=dst, encoding="utf-8")
        if pisa_status.err:
            print(f"PDF 生成有警告: {pisa_status.err}")
        else:
            print(f"PDF (English) 已生成: {pdf_path}")
    except ImportError:
        print("xhtml2pdf 未安装，跳过 PDF 生成。安装: pip install xhtml2pdf")
    except Exception as e:
        print(f"PDF 生成失败: {e}")
    finally:
        if os.path.exists(tmp_en_html):
            os.remove(tmp_en_html)

    return report_path, log_path


LOG_FILENAME = "run.log"

import re as _re
_EMOJI_RE = _re.compile(
    "["
    "\U0001F000-\U0001FAFF"
    "\u2300-\u23FF"
    "\u2600-\u27BF"
    "\u2900-\u297F"
    "\u2B00-\u2BFF"
    "\U0001F1E6-\U0001F1FF"
    "\uFE00-\uFE0F"
    "\u200D"
    "]+",
    flags=_re.UNICODE,
)


def _strip_emoji(text):
    return _EMOJI_RE.sub("", text)


def _append_log(all_protocol_data):
    log_path = os.path.join(REPORT_DIR, LOG_FILENAME)
    os.makedirs(REPORT_DIR, exist_ok=True)
    sep = "=" * 80
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{sep}\n")
        f.write(f"RUN START: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{sep}\n")
        for pd in all_protocol_data:
            pname = pd["protocol_name"]
            target = pd.get("target", "")
            f.write(f"\n--- Protocol: {pname} | Target: {target} ---\n")
            for r in pd.get("results", []):
                fc = r.get("func_code", 0)
                try:
                    fc_str = f"0x{int(fc):02X}"
                except Exception:
                    fc_str = str(fc)
                f.write(f"Round: {r.get('round')}, FuncCode: {fc_str}, ")
                f.write(f"Mutation: {r.get('mutation')}, Response: {r.get('response')}, ")
                f.write(f"Classification: {r.get('classification')}, Severity: {r.get('severity', '')}\n")
            skipped = pd.get("skipped", [])
            if skipped:
                f.write("--- Skipped ---\n")
                for s in skipped:
                    f.write(f"Skipped Round {s.get('round')} Func {s.get('func_code')}: {s.get('reason')}\n")
            bf = pd.get("build_failures", [])
            if bf:
                f.write("--- Build Failures ---\n")
                for b in bf:
                    f.write(f"Func {b.get('func_code')} [{b.get('stage')}]: {b.get('reason')}\n")
        f.write(f"\n{sep}\n")
        f.write(f"RUN END: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    return log_path


def generate_combined_report(all_protocol_data, scenario="lan", protocol_errors=None):
    """
    生成整合报告（单一协议或多协议统一输出一份 HTML + PDF）。

    all_protocol_data: list of dict, each dict:
        {
            "protocol_name": str,
            "target": str,
            "results": list,
            "skipped": list,
            "build_failures": list,
            "llm_status": LLMStatus or None,
            "slave_mode": str,
            "protocol_timed_out": bool,
        }
    protocol_errors: list of dict, 协议级错误（超时/异常），整合到报告中，不再单独生成 error_report。
    """
    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = os.path.join(REPORT_DIR, f"report_{timestamp}.html")
    pdf_path = os.path.join(REPORT_DIR, f"report_{timestamp}.pdf")
    tmp_en_html = os.path.join(REPORT_DIR, f"_en_tmp_{timestamp}.html")

    log_path = _append_log(all_protocol_data)

    protocols = [pd["protocol_name"] for pd in all_protocol_data]
    is_multi = len(all_protocol_data) > 1

    html_parts = []
    html_parts.append("<!DOCTYPE html>")
    html_parts.append("<html lang='zh-CN'><head><meta charset='UTF-8'>")
    html_parts.append(f"<title>IndusFuzz Fuzz Test Report</title>")
    html_parts.append("<style>")
    html_parts.append("body{font-family:'Microsoft YaHei','SimSun',Arial,sans-serif;padding:20px;background:#f5f8fa;color:#1a2a3a;}")
    html_parts.append("h1{color:#2d8a4e;} h2{color:#1a2a4a;margin-top:30px;}")
    html_parts.append("h3{margin-top:20px;padding:6px 10px;}")
    html_parts.append("table{width:100%;border-collapse:collapse;margin-top:12px;background:#fff;}")
    html_parts.append("table.filterable{table-layout:fixed;}")
    html_parts.append("th,td{border:1px solid #ddd;padding:6px 8px;text-align:left;font-size:12px;word-wrap:break-word;overflow-wrap:break-word;vertical-align:top;}")
    html_parts.append("td{line-height:1.4;}")
    html_parts.append("th{background:#f2f2f2;}")
    html_parts.append(".normal{background:#e0f7fa;} .exception{background:#ffcdd2;}")
    html_parts.append(".conn{background:#fff3e0;} .skip{background:#fff9c4;} .fail{background:#f8bbd0;}")
    html_parts.append(".high{background:#ff8a80;font-weight:bold;} .medium{background:#ffe082;} .low{background:#c8e6c9;}")
    html_parts.append("h3.high{background:#ff8a80;} h3.medium{background:#ffe082;} h3.low{background:#c8e6c9;}")
    html_parts.append(".filter-bar{background:#fff;padding:12px;border:1px solid #ddd;margin:16px 0;}")
    html_parts.append(".filter-bar button{margin:2px 6px;padding:6px 14px;border:1px solid #ccc;cursor:pointer;background:#f9f9f9;}")
    html_parts.append(".filter-bar button.active{background:#2d8a4e;color:#fff;border-color:#2d8a4e;}")
    html_parts.append(".protocol-section{display:none;}")
    html_parts.append(".protocol-section.active{display:block;}")
    html_parts.append(".notice-box{background:#fff9c4;border-left:4px solid #fbc02d;padding:10px 16px;margin:12px 0;font-size:13px;}")
    html_parts.append(".warning-box{background:#fff3cd;border:2px solid #ffc107;border-radius:6px;padding:14px 18px;margin:20px 0;font-size:14px;line-height:1.7;}")
    html_parts.append("</style></head><body>")

    html_parts.append("<h1>IndusFuzz 模糊测试报告 / IndusFuzz Fuzz Test Report</h1>")
    html_parts.append(f"<p><strong>生成时间 / Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | <strong>版本 / Version:</strong> {__version__}</p>")
    html_parts.append(f"<p><strong>场景 / Scenario:</strong> {scenario} | <strong>协议数 / Protocols:</strong> {len(all_protocol_data)}</p>")

    if is_multi:
        html_parts.append("<div class='filter-bar'>")
        html_parts.append("<strong>协议筛选 / Protocol Filter:</strong>")
        html_parts.append("<button class='active' onclick=\"filterProtocol('all', event)\">全部 / All</button>")
        for pd in all_protocol_data:
            pname = pd["protocol_name"]
            display = _get_display_name(pname)
            html_parts.append(f"<button onclick=\"filterProtocol('{pname}', event)\">{display}</button>")
        html_parts.append("</div>")

    total_all = sum(len(pd.get("results", [])) for pd in all_protocol_data)
    html_parts.append("<h2>汇总统计 / Overall Summary</h2>")
    html_parts.append("<table class='filterable'>")
    html_parts.append("<colgroup><col style='width:18%'><col style='width:20%'><col style='width:10%'><col style='width:12%'><col style='width:14%'><col style='width:10%'><col style='width:16%'></colgroup>")
    html_parts.append("<tr><th>协议 / Protocol</th><th>目标 / Target</th><th>总数 / Total</th><th>EXCEPTION</th><th>CONN_CLOSED</th><th>EMPTY</th><th>状态 / Status</th></tr>")
    for pd in all_protocol_data:
        pname = pd["protocol_name"]
        res = pd.get("results", [])
        exc = sum(1 for r in res if r.get("classification") == "EXCEPTION")
        cc = sum(1 for r in res if r.get("classification") == "CONN_CLOSED")
        emp = sum(1 for r in res if r.get("classification") == "EMPTY")
        status = "超时 / Timeout" if pd.get("protocol_timed_out") else "完成 / Done"
        html_parts.append(f"<tr><td>{_get_display_name(pname)}</td><td>{_esc(pd.get('target',''))}</td><td>{len(res)}</td><td>{exc}</td><td>{cc}</td><td>{emp}</td><td>{status}</td></tr>")
    html_parts.append("</table>")

    # 协议级错误信息（整合到主报告，不再单独生成 error_report）
    if protocol_errors:
        html_parts.append("<h2>⚠️ 异常协议 / Failed Protocols</h2>")
        html_parts.append("<table class='filterable'>")
        html_parts.append("<colgroup><col style='width:15%'><col style='width:15%'><col style='width:12%'><col style='width:58%'></colgroup>")
        html_parts.append("<tr><th>协议 / Protocol</th><th>错误类型 / Error Type</th><th>耗时 / Elapsed</th><th>原因 / Reason</th></tr>")
        for e in protocol_errors:
            etype = e.get("error_type", "?")
            reason = _esc(e.get("reason") or e.get("error_msg", ""))
            elapsed = e.get("elapsed", "?")
            elapsed_str = f"{elapsed}s" if isinstance(elapsed, (int, float)) else str(elapsed)
            html_parts.append(f"<tr><td>{_esc(e.get('protocol','?'))}</td><td>{etype}</td><td>{elapsed_str}</td><td>{reason}</td></tr>")
        html_parts.append("</table>")

    html_parts.append("<div id='protocol-sections'>")
    for pd in all_protocol_data:
        pname = pd["protocol_name"]
        section_cls = "protocol-section active"
        html_parts.append(f"<div class='{section_cls}' data-protocol='{pname}'>")
        inner = _build_html(
            pd.get("results", []), pd.get("skipped", []), pd.get("build_failures", []),
            pname, pd.get("target", ""), scenario, lang="zh",
            llm_status=pd.get("llm_status"), slave_mode=pd.get("slave_mode", "strict"),
            protocol_timed_out=pd.get("protocol_timed_out", False),
            protocol_timeout=120,
        )
        body_start = inner.find("<body>") + len("<body>")
        body_end = inner.find("</body>")
        body_content = inner[body_start:body_end]
        html_parts.append(body_content)
        html_parts.append("</div>")
    html_parts.append("</div>")

    if is_multi:
        html_parts.append("<script>")
        html_parts.append("""
        function filterProtocol(protocol, event) {
            var sections = document.querySelectorAll('.protocol-section');
            sections.forEach(function(s) {
                s.classList.remove('active');
                if (protocol === 'all' || s.getAttribute('data-protocol') === protocol) {
                    s.classList.add('active');
                }
            });
            var buttons = document.querySelectorAll('.filter-bar button');
            buttons.forEach(function(b) { b.classList.remove('active'); });
            if (event && event.target) { event.target.classList.add('active'); }
        }
        """)
        html_parts.append("</script>")

    html_parts.append("</body></html>")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))

    en_parts = []
    en_parts.append("<!DOCTYPE html><html><head><meta charset='UTF-8'>")
    en_parts.append("<style>")
    cn_font = _get_cn_font_path()
    if cn_font:
        en_parts.append(f"@font-face {{ font-family: SimHei; src: url('{cn_font}'); }}")
    en_parts.append("body{font-family:SimHei,Arial,sans-serif;padding:20px;background:#f5f8fa;color:#1a2a3a;}")
    en_parts.append("h1{color:#2d8a4e;} h2{color:#1a2a4a;margin-top:30px;}")
    en_parts.append("table{width:100%;border-collapse:collapse;margin-top:12px;background:#fff;}")
    en_parts.append("th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:13px;word-break:break-all;overflow-wrap:break-word;}")
    en_parts.append("th{background:#f2f2f2;}")
    en_parts.append("table{table-layout:fixed;width:100%;}")
    en_parts.append(".notice-box{background:#fff9c4;border-left:4px solid #fbc02d;padding:10px 16px;margin:12px 0;font-size:13px;}")
    en_parts.append(".warning-box{background:#fff3cd;border:2px solid #ffc107;border-radius:6px;padding:14px 18px;margin:20px 0;font-size:14px;line-height:1.7;}")
    en_parts.append("</style></head><body>")
    en_parts.append(f"<h1>IndusFuzz Fuzz Test Report</h1>")
    en_parts.append(f"<p><strong>Generated:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | <strong>Version:</strong> {__version__}</p>")
    en_parts.append(f"<p><strong>Scenario:</strong> {scenario} | <strong>Protocols:</strong> {len(all_protocol_data)}</p>")
    en_parts.append("<h2>Overall Summary</h2>")
    en_parts.append("<table><tr><th>Protocol</th><th>Target</th><th>Total</th><th>EXCEPTION</th><th>CONN_CLOSED</th><th>EMPTY</th><th>Status</th></tr>")
    for pd in all_protocol_data:
        pname = pd["protocol_name"]
        res = pd.get("results", [])
        exc = sum(1 for r in res if r.get("classification") == "EXCEPTION")
        cc = sum(1 for r in res if r.get("classification") == "CONN_CLOSED")
        emp = sum(1 for r in res if r.get("classification") == "EMPTY")
        status = "Timeout" if pd.get("protocol_timed_out") else "Done"
        en_parts.append(f"<tr><td>{_get_display_name(pname)}</td><td>{_esc(pd.get('target',''))}</td><td>{len(res)}</td><td>{exc}</td><td>{cc}</td><td>{emp}</td><td>{status}</td></tr>")
    en_parts.append("</table>")
    if protocol_errors:
        en_parts.append("<h2>Failed Protocols</h2>")
        en_parts.append("<table><tr><th>Protocol</th><th>Error Type</th><th>Elapsed</th><th>Reason</th></tr>")
        for e in protocol_errors:
            etype = e.get("error_type", "?")
            reason = _esc(e.get("reason") or e.get("error_msg", ""))
            elapsed = e.get("elapsed", "?")
            elapsed_str = f"{elapsed}s" if isinstance(elapsed, (int, float)) else str(elapsed)
            en_parts.append(f"<tr><td>{_esc(e.get('protocol','?'))}</td><td>{etype}</td><td>{elapsed_str}</td><td>{reason}</td></tr>")
        en_parts.append("</table>")
    for pd in all_protocol_data:
        pname = pd["protocol_name"]
        en_parts.append(f"<h2>Protocol: {_get_display_name(pname)}</h2>")
        inner = _build_html(
            pd.get("results", []), pd.get("skipped", []), pd.get("build_failures", []),
            pname, pd.get("target", ""), scenario, lang="en",
            llm_status=pd.get("llm_status"), slave_mode=pd.get("slave_mode", "strict"),
            protocol_timed_out=pd.get("protocol_timed_out", False),
            protocol_timeout=120,
        )
        body_start = inner.find("<body>") + len("<body>")
        body_end = inner.find("</body>")
        en_parts.append(inner[body_start:body_end])
    en_parts.append("</body></html>")

    en_content = _strip_emoji("\n".join(en_parts))
    with open(tmp_en_html, "w", encoding="utf-8") as f:
        f.write(en_content)

    try:
        from xhtml2pdf import pisa
        _register_cn_font()
        with open(tmp_en_html, "rb") as src:
            with open(pdf_path, "wb") as dst:
                pisa_status = pisa.CreatePDF(src, dest=dst, encoding="utf-8")
        if pisa_status.err:
            print(f"PDF 生成有警告: {pisa_status.err}")
        else:
            print(f"PDF (English) 已生成: {pdf_path}")
    except ImportError:
        print("xhtml2pdf 未安装，跳过 PDF 生成。安装: pip install xhtml2pdf")
    except Exception as e:
        print(f"PDF 生成失败: {e}")
    finally:
        if os.path.exists(tmp_en_html):
            os.remove(tmp_en_html)

    return report_path, pdf_path, log_path


def _html_to_pdf(html_path, pdf_path):
    try:
        from xhtml2pdf import pisa
        _register_cn_font()
        with open(html_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        clean = _strip_emoji(html_content)
        # 注入中文字体 + 表格换行 CSS
        cn_font = _get_cn_font_path()
        font_css = f"@font-face{{font-family:SimHei;src:url('{cn_font}');}}" if cn_font else ""
        clean = clean.replace(
            "</head>",
            f"<style>{font_css}body{{font-family:SimHei,Arial,sans-serif;}}"
            "td,th{word-break:break-all;overflow-wrap:break-word;}"
            "table{table-layout:fixed;width:100%;}</style></head>",
        )
        tmp = html_path + ".clean.html"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(clean)
        try:
            with open(tmp, "rb") as src:
                with open(pdf_path, "wb") as dst:
                    pisa_status = pisa.CreatePDF(src, dest=dst, encoding="utf-8")
            if pisa_status.err:
                print(f"PDF 生成有警告: {pisa_status.err}")
            else:
                print(f"PDF 已生成: {pdf_path}")
            return True
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    except ImportError:
        print("xhtml2pdf 未安装，跳过 PDF 生成。安装: pip install xhtml2pdf")
        return False
    except Exception as e:
        print(f"PDF 生成失败: {e}")
        return False


# Used by tests/verify_combined_report.py, verify_error_report.py, verify_fixes.py; main flow integration pending.
def generate_error_report(errors, total_protocols, llm_config=None, suggestion="", lang="zh"):
    os.makedirs(REPORT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = os.path.join(REPORT_DIR, f"error_report_{timestamp}.html")
    pdf_path = os.path.join(REPORT_DIR, f"error_report_{timestamp}.pdf")

    provider = (llm_config or {}).get("provider", "unknown") if llm_config else "unknown"
    model_name = (llm_config or {}).get("name", "") if llm_config else ""
    base_url = (llm_config or {}).get("base_url", "") if llm_config else ""

    if isinstance(suggestion, dict):
        sug_zh = suggestion.get("zh", "")
        sug_en = suggestion.get("en", "")
    else:
        sug_zh = str(suggestion or "")
        sug_en = str(suggestion or "")

    def _build_html_str(zh_en_pair):
        """zh_en_pair: True -> bilingual HTML, False -> English-only (for PDF)"""
        def t(zh, en):
            return f"{zh} / {en}" if zh_en_pair else en

        lines = []
        lines.append("<!DOCTYPE html>")
        lines.append("<html lang='en'><head><meta charset='UTF-8'>")
        lines.append(f"<title>IndusFuzz {t('错误报告', 'Error Report')}</title>")
        lines.append("<style>")
        lines.append("body{font-family:Arial,'Microsoft YaHei',sans-serif;padding:20px;background:#f5f8fa;color:#1a2a3a;}")
        lines.append("h1{color:#c62828;} h2{color:#1a2a4a;margin-top:30px;}")
        lines.append("table{width:100%;border-collapse:collapse;margin-top:12px;background:#fff;}")
        lines.append("th,td{border:1px solid #ddd;padding:10px;text-align:left;font-size:13px;vertical-align:top;}")
        lines.append("th{background:#f2f2f2;}")
        lines.append(".error-row{background:#ffebee;}")
        lines.append(".timeout-row{background:#fff3e0;}")
        lines.append(".suggestion-box{background:#fff3cd;border:2px solid #ffc107;border-radius:6px;padding:14px 18px;margin:20px 0;font-size:14px;line-height:1.7;white-space:pre-wrap;}")
        lines.append(".llm-box{background:#e3f2fd;border-left:4px solid #1976d2;padding:12px 16px;margin:12px 0;font-size:13px;line-height:1.6;}")
        lines.append("</style></head><body>")

        warn = "" if zh_en_pair else ""  # no emoji in PDF
        lines.append(f"<h1>{t('IndusFuzz 错误报告', 'IndusFuzz Error Report')}</h1>")
        lines.append(f"<p><strong>{t('生成时间', 'Generated')}:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | <strong>{t('版本', 'Version')}:</strong> {__version__}</p>")
        lines.append(f"<p><strong>{t('协议总数', 'Total Protocols')}:</strong> {total_protocols} | <strong>{t('异常协议数', 'Failed Protocols')}:</strong> {len(errors)}</p>")

        lines.append(f"<h2>{t('异常协议列表', 'Failed Protocols')}</h2>")
        lines.append("<table>")
        lines.append(f"<tr><th>{t('协议', 'Protocol')}</th><th>{t('错误类型', 'Error Type')}</th><th>{t('耗时', 'Elapsed')}</th><th>{t('原因', 'Reason')}</th></tr>")
        for e in errors:
            etype = e.get("error_type", "?")
            row_class = "timeout-row" if etype == "timeout" else "error-row"
            reason = _esc(e.get("reason") or e.get("error_msg", ""))
            elapsed = e.get("elapsed", "?")
            elapsed_str = f"{elapsed}s" if isinstance(elapsed, (int, float)) else str(elapsed)
            lines.append(f"<tr class='{row_class}'><td>{_esc(e.get('protocol','?'))}</td><td>{etype}</td><td>{elapsed_str}</td><td>{reason}</td></tr>")
        lines.append("</table>")

        if llm_config:
            lines.append(f"<h2>{t('LLM 配置', 'LLM Configuration')}</h2>")
            lines.append("<div class='llm-box'>")
            lines.append(f"<strong>{t('提供商', 'Provider')}:</strong> {provider}<br>")
            lines.append(f"<strong>{t('模型', 'Model')}:</strong> {model_name}<br>")
            lines.append(f"<strong>{t('地址', 'Base URL')}:</strong> {base_url}<br>")
            lines.append("</div>")

        sug_text = sug_zh if zh_en_pair else sug_en
        if sug_text:
            lines.append(f"<h2>{t('诊断与建议', 'Diagnosis & Suggestions')}</h2>")
            lines.append(f"<div class='suggestion-box'>{sug_text}</div>")

        lines.append(f"<h2>{t('说明', 'Notes')}</h2>")
        lines.append("<ul>")
        if zh_en_pair:
            lines.append("<li>超时的协议已收集到部分结果，仍生成了对应的 fuzz 报告（见 reports 目录）。 / Timed-out protocols still generated partial fuzz reports (see reports directory).</li>")
            lines.append("<li>如果是 LLM 推理过慢导致超时，可在菜单中选择更少的功能码，或使用更小的本地模型（如 qwen2.5-coder:3b）。 / If timeouts are due to slow LLM inference, select fewer function codes or use a smaller local model (e.g. qwen2.5-coder:3b).</li>")
            lines.append("<li>如果是云端 API 问题，可切换到本地 Ollama 确认 fuzz 逻辑正常。 / If cloud API issues, switch to local Ollama to confirm fuzz logic works.</li>")
        else:
            lines.append("<li>Timed-out protocols still generated partial fuzz reports (see reports directory).</li>")
            lines.append("<li>If timeouts are due to slow LLM inference, select fewer function codes or use a smaller local model (e.g. qwen2.5-coder:3b).</li>")
            lines.append("<li>If cloud API issues, switch to local Ollama to confirm fuzz logic works.</li>")
        lines.append("</ul>")

        lines.append("</body></html>")
        return "\n".join(lines)

    # HTML: bilingual
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_build_html_str(zh_en_pair=True))

    # PDF: English-only, strip emoji
    en_html = _strip_emoji(_build_html_str(zh_en_pair=False))
    tmp_en = html_path + ".en.html"
    try:
        with open(tmp_en, "w", encoding="utf-8") as f:
            f.write(en_html)
        _html_to_pdf(tmp_en, pdf_path)
    finally:
        if os.path.exists(tmp_en):
            os.remove(tmp_en)

    return html_path, pdf_path