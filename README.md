# 智慧康养健康监测与预警系统

面向社区养老场景的一体化 AIoT 监护平台：手环体征实时采集、视觉跌倒检测、异常自动告警闭环，并由 AI 智能体读取真实数据、结合照护知识库给出可执行的处置建议。

系统同时服务两类使用者——**社区值守人员**（风险排序、告警处置、交接归档）与**家属**（家人实时状况、健康报告、跌倒告警）。

---

## 一、系统能做什么

### 多源数据接入

| 数据源 | 接入方式 | 产出 |
| --- | --- | --- |
| T10 手环 | 串口（CP210x/CH9102）+ MQTT 双通道 | 心率、血氧、血压、体温、电量、步数、SOS |
| 摄像头 / 机器狗 | MJPEG 流 | 姿态关键点、跌倒判定、关键帧快照 |
| 语音 | 手机端录音 | 语音问答（原生多模态，见下） |

### AI 能力

**智能体（Function Calling）** — 模型自主决定调用哪些数据模块，最多迭代三轮（ReAct 模式）。提供两套引擎并存可切换：

- `固定流程`：按场景硬编码取数，响应快（约 2–4 秒）、产出结构稳定
- `自主取数`：模型按问题自行选工具、可多轮追查（约 5–20 秒），能完成「先扫全社区找出风险最高者，再深挖此人历史，再检索处置规程」这类推理链

**知识库检索（RAG）** — 25 篇照护规程（SOS 流程、生命体征阈值、跌倒响应、发热与低血氧处置、随访指导等）切分为 36 个片段，采用关键词 + BM25 + 向量三路混合检索并重排。知识库本身封装为一个工具，由模型按需触发而非无条件拼接。

**语音多模态** — 音频以 `input_audio` 原生模态送入 Qwen-Omni，并将手环最新体征作为文本注入同一请求，实现「听见语音的同时看到体征」的跨模态融合，输出文字与语音双通道。

**视觉跌倒检测** — YOLO 姿态估计 + 跌倒分类器本地推理，检出后经 `/video-bridge/fall-events` 推送并升级为告警，携带关键帧地址。

### 数据可信性保障

医疗场景下模型编造数值的危害极大，系统在代码层做了兜底：回答中出现体征数值但本轮未调用任何体征工具时，自动标记 `unverified_vitals_in_answer` 并在回答末尾追加不可采信提示。判定逐个数值检查其前方有无比较词，因此引用知识库阈值（"血氧低于 93% 需警惕"）不会被误判。

---

## 二、技术构成

```
采集层   串口 / MQTT / MJPEG / 录音
   ↓
感知层   体征阈值判定 · YOLO 姿态与跌倒分类 · ASR
   ↓
存储层   时序体征 · 告警事件 · 关键帧 · 照护任务（SQLite）
   ↓
工具层   23 个工具（19 个暴露给模型），按 MCP 规范抽象
   ↓
智能体   Function Calling 循环 + RAG 检索
```

- **后端**：FastAPI + Pydantic v2，WebSocket 推送告警
- **前端**：Vue 3 + TypeScript + ECharts，医疗器械风视觉主题
- **模型**：DashScope Qwen（`qwen3.5-flash` 对话 / `text-embedding-v3` 向量 / `gte-rerank-v2` 重排 / `qwen2.5-omni-7b` 语音），本地 Ollama 作降级备选
- **视觉**：Ultralytics YOLO + PyTorch
- **移动端**：Flutter

---

## 三、快速开始

### 环境要求

Python 3.11、Node.js 18+、conda。项目统一使用名为 `helth` 的 conda 环境。

### 1. 后端

```powershell
conda create -n helth python=3.11
conda activate helth
pip install -r requirements.txt

# 配置密钥（从 .env.example 复制后填入自己的 key）
copy .env.example .env

conda run -n helth python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

必须配置的环境变量：

| 变量 | 用途 |
| --- | --- |
| `QWEN_API_KEY` / `DASHSCOPE_API_KEY` | 对话、向量、重排、语音 |
| `TAVILY_API_KEY` | 外部网页搜索（可选） |
| `SERIAL_PORT` | 手环网关串口号，如 `COM12`（无硬件可留空） |

### 2. 前端

```powershell
cd frontend/vue-dashboard
npm install
npm run dev
```

访问 http://localhost:5173

### 3. 一键启动（Windows）

```powershell
.\start_all.bat      # 启动后端 + 前端
.\watch_all.bat      # 启动服务守护，掉线自动重启
```

### 演示账号

登录页右下角有悬浮球，点开可一键切换演示账号（社区值守 / 家属 / 老人），默认密码 `123456`。

---

## 四、目录结构

```
agent/                        智能体
  tool_calling_agent.py         Function Calling 引擎（模型自主选工具）
  langgraph_health_agent.py      固定流程引擎
  tool_schemas.py                工具的 OpenAI 兼容 schema
  langchain_rag_service.py       混合检索 + 增量索引
backend/
  api/                          FastAPI 路由
  services/                     业务服务（体征、告警、视觉、语音、任务）
  repositories/                 SQLite 持久化
  workers/                      帧分析子进程
docs/
  knowledge-base/               25 篇照护规程（RAG 语料）
  demo/function_calling_demo.py 函数调用教学演示（带逐行批注）
frontend/vue-dashboard/         Vue 3 前端
fall_detection_model_bundle/    跌倒检测权重与配置
iot/                            串口与 MQTT 采集
mobile/flutter_app/             移动端
```

---

## 五、函数调用演示

想快速理解智能体如何调用数据，可直接运行教学脚本（约 200 行，每行关键代码带批注，不依赖数据库）：

```powershell
conda run -n helth python docs/demo/function_calling_demo.py
```

交互式输入，建议依次尝试：

1. `你好啊` — 模型不调工具，直接问候
2. `张二现在血氧多少` — 调一次 `get_elder_vitals`，参数由模型从问题中抽取
3. `谁最需要关注，他的血氧危险吗` — 多轮：找人 → 查体征 → 查阈值

第三个问题能直观说明「工具调用顺序由模型决定，代码里并未硬编码」。

---

## 六、当前实现边界

为便于评估，以下为已验证与尚未接通的能力，据实列出：

**已验证可用**

- 手环体征实时采集、健康评分、多级告警与 SOS
- 智能体自主选工具、多轮推理、知识库检索、跨模态时间关联（跌倒时刻 → 该时刻体征）
- 语音原生多模态与体征融合
- 视觉跌倒单帧检测、告警升级、关键帧留存
- 照护任务全流程（建/改/删/勾选，含家属权限隔离）

**尚未接通**

- **视觉大模型复核**：`fall_detection_multimodal_provider` 配置项已预留但无实现，中等置信度跌倒的真伪判别目前依赖人工。相关 CLI 脚本位于 `fall_detection_model_bundle/scripts/llm_fall_review.py`，未接入运行时。
- **跌倒时序判定**：`FallPoseSequenceService` 期望的 `pose_tcn_fall_v2.pt` 未包含在仓库中，当前仅有单帧判定，无跨帧确认。
- **智能体视觉工具**：智能体可读取跌倒事件的结构化字段与关键帧地址，但不会将图像送入模型分析。
- 天气、空气质量、周边设施三个工具为占位实现，返回固定提示。

---

## 七、开发约定

- 统一使用 `helth` conda 环境，不要混用裸 `python`
- 前端字号只取 `--fs-0` 至 `--fs-6` 字阶令牌，颜色只用 `demo-theme.css` 中的语义令牌
- 提交信息写明「为什么这样改」，而非仅罗列改了什么
- 密钥只进 `.env`（已在 `.gitignore` 中），不得硬编码

测试与验证：

```powershell
conda run -n helth pytest                              # 后端测试
cd frontend/vue-dashboard && npx vue-tsc --noEmit       # 前端类型检查
cd frontend/vue-dashboard && npm run shots              # Playwright 截图验证
```
