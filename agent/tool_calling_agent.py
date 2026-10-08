"""原生 function calling 智能体。

与 langgraph_health_agent 的根本区别：**工具由模型自己选**，不再按 scope+workflow
硬编码。这带来两个直接后果：
  1. 意图路由不需要了——模型面对寒暄/身份提问会自然地不调工具，直接作答。
     实测 qwen3.5-flash 对「你好啊」「你是谁」均不触发 tool_calls。
  2. 支持多轮推理——"先看谁高风险，再深挖那个人的历史"这类链条能走通。

保底策略（hybrid）：仍固定注入当前对象的最新体征与告警作为系统上下文。
纯靠模型决策时，偶发的"该调没调"会让回答空手而归；固定注入把这个风险压掉，
同时不妨碍模型再去补充调用。

事件格式与旧引擎保持一致，前端无需改动即可渲染。
"""
from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import httpx

from agent.langchain_rag_service import LangChainRAGService
from agent.mcp_adapter import ToolAdapter, ToolInvocation
from agent.tool_schemas import AGENT_TOOL_NAMES, AGENT_TOOL_SCHEMAS
from backend.config import Settings
from backend.models.user_model import UserRole

MAX_TOOL_ROUNDS = 3
RAG_TOOL_NAME = "search_care_knowledge"

# 能真正提供体征数值的工具。回答里出现体征数字但一个都没调过，说明是模型编的。
VITALS_TOOL_NAMES = frozenset(
    {
        "get_device_realtime",
        "get_device_trend",
        "get_vitals_around",
        "query_sensor_history",
        "summarize_window_metrics",
        "get_community_overview",
    }
)

# 体征数值的字面模式。宁可漏判也不要误判，所以要求数字必须紧挨单位或指标名。
VITALS_VALUE_PATTERNS = (
    re.compile(r"\d+\s*(?:bpm|次/分)"),
    re.compile(r"(?:血氧|SpO2|spo2)\D{0,6}\d{2,3}\s*%"),
    re.compile(r"\d{2,3}\s*/\s*\d{2,3}\s*mmHg"),
    re.compile(r"(?:体温)\D{0,6}\d{2}(?:\.\d)?\s*(?:°C|℃|摄氏度)"),
)

# 阈值引用的数值来自知识库规程，不是实测值，不能算编造。
# 逐个数值判断而非整句——同一句里可能既报实测又引阈值（"实测血氧 92%，低于 93% 阈值"），
# 按句放过会漏掉前半句的编造。
THRESHOLD_WORDS = r"低于|高于|超过|不足|小于|大于|不低于|不高于|≥|≤|<|>|阈值|参考值?|临界值?"

# 数值前方（紧邻）出现比较词
THRESHOLD_LOOKBEHIND = re.compile(rf"(?:{THRESHOLD_WORDS})\D{{0,4}}$")
# 比较词被吃进匹配内容本身：血氧模式的 \D{0,6} 会把"血氧低于 93%"整段吞掉，
# 此时回看窗口只剩"按规程"，看不到"低于"，必须补查匹配内容。
THRESHOLD_INLINE = re.compile(rf"(?:{THRESHOLD_WORDS})")

UNVERIFIED_VITALS_NOTE = "unverified_vitals_in_answer"
UNVERIFIED_VITALS_HINT = (
    "\n\n---\n"
    "⚠ 上文出现了体征数值，但本次分析未成功调取体征数据，这些数值不可采信。"
    "请点开执行过程核对，或重新提问以获取真实体征。"
)


def _has_unverified_vitals(answer: str, used_tools: list[str]) -> bool:
    """
    回答里报出了体征实测值，却没调过任何体征工具 —— 判定为编造。

    逐个数值判断：数值前紧邻比较词的（"低于 93%"）是引用知识库阈值，放过；
    其余视为在报告实测值，必须有工具来源。
    """
    if any(name in VITALS_TOOL_NAMES for name in used_tools):
        return False

    for pattern in VITALS_VALUE_PATTERNS:
        for match in pattern.finditer(answer):
            if THRESHOLD_INLINE.search(match.group()):
                continue      # 比较词在匹配内容里，如"血氧低于 93%"
            preceding = answer[max(0, match.start() - 12) : match.start()]
            if THRESHOLD_LOOKBEHIND.search(preceding):
                continue      # 比较词在数值前方，如"应低于 140/90 mmHg"
            return True       # 无来源的实测值
    return False

ROLE_BRIEF = {
    UserRole.COMMUNITY: "你是社区值守人员的康养助手，关注风险排序、告警处置与交接。",
    UserRole.FAMILY: "你是家属的家庭守护助手，用家属能懂的话说明状况与该做什么。",
    UserRole.ELDER: "你是面向老人的健康说明助手，用简单温和的短句。",
    UserRole.ADMIN: "你是运营审核助手，输出稳定、可复核。",
}

SYSTEM_RULES = """最高优先级铁律（违反即为严重错误）：
- 任何具体体征数值（心率、血氧、血压、体温）只能来自本轮实际调用的工具返回结果。
  没有调用过体征类工具，就绝对不许写出任何体征数字，也不许说"我调取了体征数据"
  这类话——只能写"未取到该时段体征数据"。
- 同理，姓名、房号、家属电话也必须来自工具结果，不许推测或补全。

工作方式：
- 需要数据时调用工具获取。
- 引用临床阈值或标准处置流程时，先调 search_care_knowledge 检索本地规程。
- 一次可以并行调多个工具；拿到结果后如果还缺关键信息，可以再调一轮。
- 涉及跌倒时按两步取证：先 query_fall_events 拿到 occurred_at 与 elder_wrist_mac，
  再把这两个值传给 get_vitals_around 看当时体征有无应激反应，最后按需检索处置规程。
  只做了第一步就想描述"当时身体状况"是不允许的。
- 数据确实取不到时，直接说明取不到，不要用猜测填补。

回答方式：
- 用户只是寒暄、道谢或询问你的身份能力时，简短自然地回应即可，不要输出健康分析。
- 回答健康问题时先给结论，再给依据（带具体数值），最后给可执行的下一步。
- 涉及紧急情况（SOS、极低血氧、意识异常）时把最紧急的动作放在最前面。
- 用中文，不要罗列内部字段名，不要提及你调用了哪些工具。
- 忽略体温相关字段，不要基于体温作判断。"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ToolCallingAgent:
    """模型自主选择工具的智能体。"""

    def __init__(
        self,
        settings: Settings,
        tool_adapter: ToolAdapter,
        rag_service: LangChainRAGService,
    ) -> None:
        self._settings = settings
        self._tools = tool_adapter
        self._rag = rag_service

    # ------------------------------------------------------------------ 公共入口

    def stream(
        self,
        *,
        role: UserRole,
        question: str,
        baseline: dict[str, Any],
        history: list[dict[str, str]] | None = None,
    ) -> Iterator[dict[str, Any]]:
        session_id = str(uuid.uuid4())
        yield {
            "type": "session.started",
            "session_id": session_id,
            "scope": str(baseline.get("scope", "community")),
            "timestamp": _now(),
        }

        try:
            yield from self._run(
                session_id=session_id,
                role=role,
                question=question,
                baseline=baseline,
                history=history or [],
            )
        except Exception as exc:  # noqa: BLE001 - 兜底成事件而不是 500
            yield {
                "type": "stage.changed",
                "stage": "answer",
                "label": "生成回答",
                "status": "error",
                "group": "trace",
                "summary": f"{exc.__class__.__name__}: {exc}"[:200],
                "timestamp": _now(),
            }
            yield {
                "type": "answer.completed",
                "session_id": session_id,
                "answer": "当前分析链路异常，未能完成本次回答。请稍后重试或改用固定流程引擎。",
                "references": [],
                "analysis": {},
                "timestamp": _now(),
            }
            yield {
                "type": "session.completed",
                "session_id": session_id,
                "selected_model": self._model,
                "degraded_notes": [f"toolcall_agent_error:{exc.__class__.__name__}"],
                "timestamp": _now(),
            }

    # ------------------------------------------------------------------ 主流程

    def _run(
        self,
        *,
        session_id: str,
        role: UserRole,
        question: str,
        baseline: dict[str, Any],
        history: list[dict[str, str]],
    ) -> Iterator[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self._build_system(role, baseline)}
        ]
        for turn in history[-6:]:
            turn_role = "assistant" if str(turn.get("role")) == "assistant" else "user"
            content = str(turn.get("content", "")).strip()
            if content:
                messages.append({"role": turn_role, "content": content})
        messages.append({"role": "user", "content": question})

        references: list[str] = []
        used_tools: list[str] = []

        for round_index in range(MAX_TOOL_ROUNDS):
            stage = f"decide_{round_index + 1}"
            label = "选择工具" if round_index == 0 else f"补充取数（第 {round_index + 1} 轮）"
            yield self._stage(stage, label, "running")

            reply = self._chat(messages, with_tools=True)
            calls = reply.get("tool_calls") or []

            if not calls:
                # 模型认为信息够了（寒暄类会在第一轮就走到这里）
                yield self._stage(
                    stage,
                    label,
                    "completed",
                    detail="无需取数" if round_index == 0 else "信息已足够",
                )
                break

            yield self._stage(stage, label, "completed", detail=f"决定调用 {len(calls)} 个工具")
            messages.append(
                {
                    "role": "assistant",
                    "content": reply.get("content") or "",
                    "tool_calls": calls,
                }
            )

            yield self._stage("tools", "工具调用", "running")
            for call in calls:
                fn = call.get("function", {})
                name = str(fn.get("name", ""))
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except json.JSONDecodeError:
                    args = {}
                if not isinstance(args, dict):
                    args = {}

                yield {
                    "type": "tool.started",
                    "stage": "tools",
                    "tool_name": name,
                    "request_id": str(call.get("id", "")),
                    "source": "local_service",
                    "timestamp": _now(),
                }

                result, refs = self._invoke(name, args)
                references.extend(refs)
                used_tools.append(name)

                ok = not result.get("_error")
                yield {
                    "type": "tool.finished",
                    "stage": "tools",
                    "tool_name": name,
                    "request_id": str(call.get("id", "")),
                    "source": "local_service",
                    "status": "ok" if ok else "error",
                    "success": ok,
                    "summary": self._summarize(name, result, ok),
                    "attachments": result.pop("_attachments", []),
                    "input_preview": json.dumps(args, ensure_ascii=False, default=str)[:240],
                    "output_preview": json.dumps(result, ensure_ascii=False, default=str)[:360],
                    "error_message": result.get("_error"),
                    "timestamp": _now(),
                }

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(call.get("id", "")),
                        "content": json.dumps(result, ensure_ascii=False, default=str)[:6000],
                    }
                )
            yield self._stage("tools", "工具调用", "completed", detail=f"已完成 {len(calls)} 次调用")

        # 最终作答：流式
        yield self._stage("answer", "生成回答", "running")
        full: list[str] = []
        for piece in self._chat_stream(messages):
            full.append(piece)
            yield {
                "type": "answer.delta",
                "session_id": session_id,
                "delta": piece,
                "timestamp": _now(),
            }
        yield self._stage("answer", "生成回答", "completed")

        answer = "".join(full).strip()
        if not answer:
            answer = "本次未能生成回答内容，请重试。"

        # 代码层兜底：提示词约束不住时，至少让问题可见而不是静默混进结论
        degraded_notes: list[str] = []
        if _has_unverified_vitals(answer, used_tools):
            degraded_notes.append(UNVERIFIED_VITALS_NOTE)
            answer += UNVERIFIED_VITALS_HINT
            yield {
                "type": "answer.delta",
                "session_id": session_id,
                "delta": UNVERIFIED_VITALS_HINT,
                "timestamp": _now(),
            }
            yield self._stage(
                "verify",
                "结论校验",
                "error",
                detail="回答含体征数值但未调用体征工具，已标记为不可采信",
            )
        else:
            yield self._stage("verify", "结论校验", "completed", detail="数值来源可追溯")

        yield {
            "type": "answer.completed",
            "session_id": session_id,
            "answer": answer,
            "references": references,
            "citations": [
                {"id": f"kb-{index}", "title": ref.split("]")[0].lstrip("["), "snippet": ref}
                for index, ref in enumerate(references)
            ],
            "analysis": {"used_tools": used_tools},
            "degraded_notes": degraded_notes,
            "timestamp": _now(),
        }
        yield {
            "type": "session.completed",
            "session_id": session_id,
            "selected_model": self._model,
            "degraded_notes": degraded_notes,
            "timestamp": _now(),
        }

    # ------------------------------------------------------------------ 提示词

    def _build_system(self, role: UserRole, baseline: dict[str, Any]) -> str:
        parts = [ROLE_BRIEF.get(role, ROLE_BRIEF[UserRole.COMMUNITY]), "", SYSTEM_RULES, ""]

        roster = baseline.get("roster") or []
        if roster:
            parts.append("当前监护名册（调工具时用这里的 MAC，不要臆造）：")
            for item in roster:
                parts.append(
                    f"- {item.get('name')} | 房号 {item.get('apartment')} | "
                    f"ID {item.get('elder_id')} | MAC {item.get('mac_address') or '未绑定'} | "
                    f"{item.get('status')}"
                )
            parts.append("")

        focus = baseline.get("focus")
        if focus:
            parts.append(
                f"用户当前选中的对象是 {focus.get('name')}（{focus.get('apartment')}）。"
                "用户说\"他/她/这位老人\"时指的就是这位。"
            )
            vitals = focus.get("vitals") or {}
            if vitals:
                parts.append(
                    "该对象最新体征："
                    + "、".join(f"{key} {value}" for key, value in vitals.items() if value is not None)
                )
            parts.append("")

        alarms = baseline.get("alarms") or []
        if alarms:
            parts.append(f"当前未处置告警 {len(alarms)} 条：")
            for item in alarms[:6]:
                parts.append(f"- {item}")
            parts.append("")

        parts.append(f"时间范围：{baseline.get('window_label', '过去一天')}。当前时间 {_now()}。")
        return "\n".join(parts)

    # ------------------------------------------------------------------ 工具执行

    def _invoke(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
        if name not in AGENT_TOOL_NAMES:
            return {"_error": f"未知工具 {name}"}, []

        if name == RAG_TOOL_NAME:
            query = str(args.get("query", "")).strip()
            if not query:
                return {"_error": "缺少 query"}, []
            hits = self._rag.search(query, top_k=self._settings.rag_top_k)
            return {"knowledge": hits}, list(hits)

        results = self._tools.invoke_many(
            [ToolInvocation(name=name, request_id=str(uuid.uuid4()), payload=args)]
        )
        result = results[0]
        if not result.success:
            return {"_error": result.error_message or result.error or "工具执行失败"}, []

        data = result.data if isinstance(result.data, dict) else {"value": result.data}
        payload = dict(data)
        attachments = payload.get("attachments")
        if isinstance(attachments, list) and attachments:
            payload["_attachments"] = attachments
        return payload, []

    @staticmethod
    def _summarize(name: str, data: dict[str, Any], ok: bool) -> str:
        if not ok:
            return str(data.get("_error", "工具执行失败"))[:80]
        if name == RAG_TOOL_NAME:
            return f"检索到 {len(data.get('knowledge', []))} 条规程"
        if "alarms" in data:
            return f"返回 {len(data.get('alarms') or [])} 条告警"
        if "points" in data:
            return f"返回 {len(data.get('points') or [])} 个数据点"
        if "heart_rate" in data:
            return "已读取最新体征"
        if "charts" in data:
            return f"生成 {len(data.get('charts') or [])} 组图表"
        if "elders" in data:
            return f"返回 {len(data.get('elders') or [])} 位老人"
        return "已返回结构化结果"

    # ------------------------------------------------------------------ 模型调用

    @property
    def _model(self) -> str:
        return self._settings.qwen_model or "qwen-plus"

    @property
    def _base_url(self) -> str:
        return "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

    @property
    def _headers(self) -> dict[str, str]:
        key = (
            getattr(self._settings, "qwen_api_key", "")
            or getattr(self._settings, "dashscope_api_key", "")
            or ""
        ).strip()
        if not key:
            raise RuntimeError("QWEN_API_KEY 未配置，无法使用 function calling 引擎")
        return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

    def _chat(self, messages: list[dict[str, Any]], *, with_tools: bool) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self._model, "messages": messages, "max_tokens": 900}
        if with_tools:
            body["tools"] = AGENT_TOOL_SCHEMAS
        timeout = max(20.0, float(self._settings.rag_timeout_seconds) * 3)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(self._base_url, headers=self._headers, json=body)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]

    def _chat_stream(self, messages: list[dict[str, Any]]) -> Iterator[str]:
        body = {
            "model": self._model,
            "messages": messages,
            "max_tokens": 1200,
            "stream": True,
        }
        timeout = max(60.0, float(self._settings.rag_timeout_seconds) * 6)
        with httpx.Client(timeout=timeout) as client:
            with client.stream("POST", self._base_url, headers=self._headers, json=body) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    chunk = line[5:].strip()
                    if not chunk or chunk == "[DONE]":
                        continue
                    try:
                        parsed = json.loads(chunk)
                    except json.JSONDecodeError:
                        continue
                    for choice in parsed.get("choices", []):
                        piece = (choice.get("delta") or {}).get("content")
                        if piece:
                            yield piece

    @staticmethod
    def _stage(stage: str, label: str, status: str, detail: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "type": "stage.changed",
            "stage": stage,
            "label": label,
            "status": status,
            "group": "trace",
            "summary": detail or f"{label}{'进行中' if status == 'running' else '已完成'}",
            "timestamp": _now(),
        }
        if detail:
            payload["detail"] = detail
        return payload
