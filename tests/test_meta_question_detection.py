from backend.models.user_model import UserRole

from agent.prompt_templates import detect_response_mode, is_meta_question
from agent.prompting import build_prompt_package


def test_meta_question_detection_identity():
    assert is_meta_question("你是谁？？？") is True
    assert detect_response_mode("你是谁？？？") == "meta"


def test_meta_question_detection_capability():
    assert is_meta_question("你能做什么") is True
    assert detect_response_mode("怎么使用") == "meta"


def test_meta_question_not_triggered_for_health_topics():
    assert is_meta_question("钱七的血压风险如何") is False
    assert is_meta_question("这个告警是什么意思") is False
    assert detect_response_mode("钱七的血压风险如何") == "advice"


def test_meta_prompt_skips_health_context():
    package = build_prompt_package(
        role=UserRole.COMMUNITY,
        scope="elder",
        question="你是谁",
        analysis_context="SHOULD_NOT_APPEAR",
        knowledge_context="SHOULD_NOT_APPEAR",
        search_context="SHOULD_NOT_APPEAR",
    )
    assert "Response mode: meta" in package["system"]
    assert "SHOULD_NOT_APPEAR" not in package["user"]
    assert "不要输出健康分析" in package["system"]
