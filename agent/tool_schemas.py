"""OpenAI 兼容的 function schema，供模型自主选择工具。

与 backend/dependencies.py 注册的 handler 一一对应，参数名必须与 handler 读取的
payload 键一致——例如 MAC 只认 `mac_address`（见 _normalize_mac_from_payload），
写成 device_mac 会导致 handler 收到空 MAC 并静默返回空数据。

故意不暴露的工具：
- weather_lookup / air_quality_lookup / nearby_facility_lookup / holiday_lookup
  这四个是占位实现，返回固定字符串。暴露给模型只会浪费一轮调用。
"""
from __future__ import annotations

from typing import Any

_WINDOW = {
    "type": "string",
    "enum": ["day", "week"],
    "description": "时间范围：day=过去一天，week=过去一周",
}

_MAC = {
    "type": "string",
    "description": "设备 MAC 地址，形如 53:57:08:00:00:04。必须从系统给出的监护名册中取，不要臆造。",
}


def _fn(name: str, description: str, properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required or [],
            },
        },
    }


AGENT_TOOL_SCHEMAS: list[dict[str, Any]] = [
    _fn(
        "get_device_realtime",
        "查询某位老人手环的最新一条体征（心率、血氧、体温、血压、电量、步数）。想知道"
        "\"现在怎么样\"用这个。",
        {"mac_address": _MAC},
        ["mac_address"],
    ),
    _fn(
        "get_device_trend",
        "查询某位老人近期体征的时间序列，用于判断趋势是上升、下降还是平稳。",
        {
            "mac_address": _MAC,
            "minutes": {
                "type": "integer",
                "description": "回溯多少分钟，默认 180。要看一天写 1440，一周写 10080。",
            },
        },
        ["mac_address"],
    ),
    _fn(
        "get_device_status",
        "查询设备在线状态与绑定状态。怀疑离线、掉线、未绑定时用这个。",
        {"mac_address": _MAC},
        ["mac_address"],
    ),
    _fn(
        "get_elder_profile",
        "查询老人的档案，含房号、绑定设备与关联家属。",
        {
            "elder_user_id": {"type": "string", "description": "老人 ID，如 elder03_01"},
            "mac_address": _MAC,
        },
    ),
    _fn(
        "get_family_relations",
        "查询某位老人的家属联系关系，含称谓与联系电话。需要通知家属时先查这个。",
        {"elder_user_id": {"type": "string", "description": "老人 ID，如 elder03_01"}},
        ["elder_user_id"],
    ),
    _fn(
        "get_active_alarms",
        "查询告警记录。不传 mac_address 则返回全社区告警。",
        {
            "mac_address": _MAC,
            "active_only": {
                "type": "boolean",
                "description": "true 只看未处置的活跃告警，false 看全部历史。默认 true。",
            },
        },
    ),
    _fn(
        "get_community_overview",
        "查询全社区监测概览：设备总数、风险分层、平均健康分。回答\"整体怎么样\"用这个。",
        {},
    ),
    _fn(
        "get_care_directory",
        "查询社区照护目录：全部老人、家属及其绑定关系。需要知道有哪些人时用这个。",
        {},
    ),
    _fn(
        "summarize_window_metrics",
        "汇总指定时间范围内的关键指标统计（均值、极值、触发的预警次数、采样条数）。"
        "需要\"多少次采样中有多少次异常\"这类量化依据时用这个。",
        {
            "window": _WINDOW,
            "device_macs": {
                "type": "array",
                "items": {"type": "string"},
                "description": "限定设备范围，留空则统计全社区",
            },
        },
    ),
    _fn(
        "query_alert_history",
        "查询时间范围内的告警历史，可按设备过滤。用于分析告警频次与分布。",
        {"window": _WINDOW, "mac_address": _MAC},
    ),
    _fn(
        "query_health_scores",
        "查询某设备的健康评分历史，用于看评分是变好还是变差。",
        {"window": _WINDOW, "mac_address": _MAC},
    ),
    _fn(
        "query_sensor_history",
        "查询某设备的分桶体征历史，比 get_device_trend 更适合长时间跨度的聚合观察。",
        {"window": _WINDOW, "mac_address": _MAC},
    ),
    _fn(
        "query_device_status_history",
        "查询设备的在线/离线状态变化历史，用于排查反复掉线。",
        {"window": _WINDOW, "mac_address": _MAC},
    ),
    _fn(
        "build_chart_payloads",
        "生成可视化图表数据。用户明确要图、要趋势可视化时用这个。",
        {"window": _WINDOW},
    ),
    _fn(
        "generate_analysis_report",
        "生成结构化分析报告。用户要\"报告\"\"日报\"\"交班材料\"时用这个。",
        {
            "scope": {
                "type": "string",
                "enum": ["community", "elder"],
                "description": "community=社区整体报告，elder=单个老人报告",
            },
            "window": _WINDOW,
        },
    ),
    _fn(
        "query_fall_events",
        "查询跌倒检测事件，返回发生时刻 occurred_at、严重度、跌倒置信度、关键帧地址、复核结论，"
        "以及该老人的手环 MAC（elder_wrist_mac）。用户问\"有没有摔倒\"\"什么时候摔的\"时用这个。"
        "不传 elder_id 则返回全社区跌倒事件。"
        "注意：返回里的 camera_device_mac 是摄像头，不是手环，查体征时不要用它。",
        {
            "elder_id": {
                "type": "string",
                "description": "老人 ID，如 elder01_02。留空返回全社区。",
            },
            "limit": {"type": "integer", "description": "最多返回多少条，默认 10"},
        },
    ),
    _fn(
        "get_vitals_around",
        "查询某个时刻前后一段时间的体征。判断\"摔倒那一刻身体状况如何\"必须用这个工具，"
        "不允许凭推测给出体征数值。"
        "标准用法：先调 query_fall_events，把返回的 elder_wrist_mac 作为 mac_address、"
        "occurred_at 作为 at 传进来。",
        {
            "mac_address": {
                "type": "string",
                "description": "老人手环 MAC。跌倒场景下取 query_fall_events 返回的 elder_wrist_mac，"
                "不要用 camera_device_mac。",
            },
            "at": {
                "type": "string",
                "description": "中心时刻，ISO 8601 格式，例如 2026-09-01T14:32:00Z。通常取跌倒事件的 occurred_at。",
            },
            "span_minutes": {
                "type": "integer",
                "description": "前后各取多少分钟，默认 10",
            },
        },
        ["mac_address", "at"],
    ),
    _fn(
        "search_care_knowledge",
        "检索本地照护知识库（生命体征阈值、SOS 流程、跌倒响应、发热与低血氧处置、"
        "随访指导等 25 篇规程）。需要引用临床阈值或标准处置流程时用这个。",
        {"query": {"type": "string", "description": "检索关键词或问题"}},
        ["query"],
    ),
    _fn(
        "run_tavily_search",
        "外部网页搜索。仅当本地数据与知识库都不足以回答，且问题确实需要外部资料时使用。",
        {"query": {"type": "string", "description": "搜索关键词"}},
        ["query"],
    ),
]

# 模型可见的工具名集合，用于拒绝幻觉出来的工具名
AGENT_TOOL_NAMES = {item["function"]["name"] for item in AGENT_TOOL_SCHEMAS}
