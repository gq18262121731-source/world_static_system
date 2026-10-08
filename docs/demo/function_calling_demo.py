"""
智能体函数调用（Function Calling）演示

这是一份教学用最小实现，不接真实数据库，所有"功能模块"都返回写死的假数据。
目的是把智能体调用数据的完整链路用最少的代码走一遍：

    用户提问
      → 模型看"工具说明书"，决定要调哪个模块、传什么参数（它只输出意图，不执行）
      → 我们的代码真正去执行那个模块
      → 把执行结果回灌给模型
      → 模型判断：信息够了就作答，不够就再调一轮（ReAct 循环）

运行方式：
    python docs/demo/function_calling_demo.py
密钥自动从项目根目录的 .env 读取（DASHSCOPE_API_KEY 或 QWEN_API_KEY），无需手动设环境变量。
"""

import json
import os
from pathlib import Path

from openai import OpenAI

# ============================================================
# 第 0 步：连接大模型
# ============================================================

def load_api_key() -> str:
    """密钥绝不写进代码：先看环境变量，没有就去项目 .env 里找。"""
    key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if key:
        return key.strip()

    env_file = Path(__file__).resolve().parents[2] / ".env"   # docs/demo/ 往上两级就是项目根
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(("DASHSCOPE_API_KEY=", "QWEN_API_KEY=")):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("未找到 DASHSCOPE_API_KEY，请在 .env 中配置")


# 千问兼容 OpenAI 协议，所以直接用 OpenAI SDK，只需把 base_url 指到 DashScope
client = OpenAI(
    api_key=load_api_key(),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
)

MODEL = "qwen3.5-flash"                               # 必须选支持 function calling 的模型


# ============================================================
# 第 1 步：功能模块——每个模块就是一个普通 Python 函数
# ============================================================
# 真实系统里这些函数会去查数据库、读传感器；演示里直接返回假数据。
# 注意：模型永远调不到这些函数本身，它只能"说"想调哪个，执行权在我们手里。

def get_elder_vitals(elder_name: str) -> dict:
    """查某位老人的最新体征。"""
    fake_db = {                                       # 假数据，模拟数据库
        "张二": {"heart_rate": 74, "blood_oxygen": 94, "blood_pressure": "147/88"},
        "王五": {"heart_rate": 62, "blood_oxygen": 100, "blood_pressure": "107/76"},
    }
    return fake_db.get(elder_name, {"error": f"没有 {elder_name} 的数据"})


def list_high_risk_elders() -> dict:
    """列出当前高风险老人。"""
    return {"elders": [{"name": "张二", "reason": "血压持续偏高"}]}


def search_knowledge(query: str) -> dict:
    """检索照护知识库（这里用一条假规程代替真实 RAG）。"""
    return {"knowledge": "血氧低于 93% 需提高警惕；低于 90% 且伴气促应按紧急处理。"}


# ============================================================
# 第 2 步：注册表——把"函数名字符串"映射到"真函数"
# ============================================================
# 模型返回的是字符串 "get_elder_vitals"，我们需要靠这张表找到真正要执行的函数。
# 对应真实系统里的 LocalToolAdapter.register_tool()

TOOL_REGISTRY = {
    "get_elder_vitals": get_elder_vitals,
    "list_high_risk_elders": list_high_risk_elders,
    "search_knowledge": search_knowledge,
}


# ============================================================
# 第 3 步：说明书——告诉模型每个模块是干什么的、要什么参数
# ============================================================
# 这是整套机制里最重要的部分：模型不读代码，它只读这份说明书来决定调哪个。
# description 写得准不准，直接决定模型选得对不对。
# 对应真实系统里的 agent/tool_schemas.py

TOOL_SCHEMAS = [
    {
        "type": "function",                           # 固定写法，表示这是一个可调用的函数
        "function": {
            "name": "get_elder_vitals",               # 必须和注册表里的键一致
            "description": "查询某位老人的最新体征（心率、血氧、血压）。想知道'现在怎么样'用这个。",
            "parameters": {                           # JSON Schema 格式描述参数
                "type": "object",
                "properties": {
                    "elder_name": {"type": "string", "description": "老人姓名"},
                },
                "required": ["elder_name"],           # 告诉模型这个参数不能省
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_high_risk_elders",
            "description": "列出当前所有高风险老人及原因。想知道'谁最需要关注'用这个。",
            "parameters": {"type": "object", "properties": {}},   # 无参数
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "检索照护规程知识库。需要引用临床阈值或标准处置流程时用这个。",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "检索关键词"}},
                "required": ["query"],
            },
        },
    },
]


# ============================================================
# 第 4 步：执行器——真正去跑模型选中的模块
# ============================================================

def execute_tool(name: str, arguments_json: str) -> str:
    """按模型给的名字和参数执行模块，把结果转成字符串（模型只能读文本）。"""
    func = TOOL_REGISTRY.get(name)                    # 用名字在注册表里找函数
    if func is None:
        return json.dumps({"error": f"未知工具 {name}"}, ensure_ascii=False)

    args = json.loads(arguments_json or "{}")         # 模型给的参数是 JSON 字符串，要先解析
    result = func(**args)                             # 把参数展开传进函数，真正执行
    return json.dumps(result, ensure_ascii=False)     # 序列化回字符串，准备回灌给模型


# ============================================================
# 第 5 步：智能体主循环（ReAct：推理 → 行动 → 观察 → 再推理）
# ============================================================

SYSTEM_PROMPT = (
    "你是社区康养值守助手。需要数据时调用工具，不要凭空编造数值。"
    "用户只是寒暄时直接简短回应，不要调工具。"
)


def run_agent(question: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}]

    for _ in range(3):                                          # 最多 3 轮，防止无限调用
        reply = client.chat.completions.create(
            model=MODEL, messages=messages, tools=TOOL_SCHEMAS,  # tools= 把说明书交给模型
        ).choices[0].message

        if not reply.tool_calls:                                # 模型没要工具 → 就是最终回答
            return reply.content

        messages.append(reply)                                  # 记下模型的"调用意图"
        for call in reply.tool_calls:                           # 逐个执行模型点名的模块
            result = execute_tool(call.function.name, call.function.arguments)
            print(f"  ↳ 调用 {call.function.name}({call.function.arguments}) → {result}")
            messages.append({"role": "tool",                    # 结果回灌给模型
                             "tool_call_id": call.id,           # id 对上，模型才知道是哪次的结果
                             "content": result})
        # 回到循环顶部：模型看到结果后再决策——够了就作答，不够再调

    return client.chat.completions.create(model=MODEL, messages=messages).choices[0].message.content



def _run_agent_reference(question: str, max_depth: int = 5) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": question}]
    return _step(messages, max_depth)

def _step(messages: list, depth_left: int) -> str:
    if depth_left <= 0:
        return "达到最大调用深度，未能得出结论。"

    reply = client.chat.completions.create(
        model=MODEL, messages=messages, tools=TOOL_SCHEMAS
    ).choices[0].message

    if not reply.tool_calls:
        return reply.content

    messages.append(reply)
    for call in reply.tool_calls:
        result = execute_tool(call.function.name, call.function.arguments)
        messages.append({
            "role": "tool",
            "tool_call_id": call.id,
            "content": str(result)
        })

    # 递归进行下一轮调用
    return _step(messages, depth_left - 1)




















def safe_run_agent(question: str) -> str:

    try:
        return run_agent(question)
    except Exception as exc:
        print(f"  [主流程异常，已切换备用实现] {type(exc).__name__}: {exc}")

    try:
        return _run_agent_reference(question)
    except Exception as exc:
        print(f"  [备用实现也失败，使用离线答案] {type(exc).__name__}: {exc}")

    return OFFLINE_ANSWERS.get(
        question.replace(" ", "").rstrip("？?。"),
        "系统暂时无法连接模型服务，请稍后再试。",
    )


# ============================================================
# 交互式演示：自己输入问题，观察模型如何决策
# ============================================================
# 建议试的三类问题：
#   你好啊                          → 模型不调工具，直接问候
#   张二现在血氧多少                 → 调一次 get_elder_vitals
#   谁最需要关注，他的血氧危险吗      → 多轮：找人 → 查体征 → 查阈值

if __name__ == "__main__":
    print("智能体已就绪，输入问题回车；输入 q 退出。\n")
    while True:
        try:
            question = input("你：").strip()
        except (KeyboardInterrupt, EOFError):       # Ctrl+C 也优雅退出，不刷一屏红字
            print()
            break
        if question.lower() in {"q", "quit", "exit", ""}:
            break
        print(f"\n智能体：{safe_run_agent(question)}\n")
