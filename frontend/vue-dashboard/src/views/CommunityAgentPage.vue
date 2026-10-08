<script setup lang="ts">
import {
  Activity,
  BellRing,
  Bot,
  Database,
  FileText,
  HeartPulse,
  LayoutDashboard,
  LineChart,
  ListOrdered,
  PanelRightClose,
  PanelRightOpen,
  RefreshCw,
  SendHorizontal,
  SlidersHorizontal,
  Sparkles,
  Square,
  Workflow,
  type LucideIcon,
} from "lucide-vue-next";
import { computed, nextTick, onMounted, ref, toRef, watch } from "vue";
import type { SessionUser } from "../api/client";
import AgentMarkdownContent from "../components/agent/AgentMarkdownContent.vue";
import AgentTracePanel from "../components/agent/AgentTracePanel.vue";
import CommunityAgentAttachmentRenderer from "../components/agent/CommunityAgentAttachmentRenderer.vue";
import { useCommunityAgentWorkbench } from "../composables/useCommunityAgentWorkbench";
import { useCommunityWorkspace } from "../composables/useCommunityWorkspace";

const props = defineProps<{
  sessionUser: SessionUser;
  /**
   * Trigger refresh behavior when user re-clicks the nav entry,
   * even if the route/hash doesn't change.
   */
  refreshKey?: number;
}>();

const workspace = useCommunityWorkspace(toRef(props, "sessionUser"));
const workbench = useCommunityAgentWorkbench(
  () => workspace.deviceStatuses.value.map((item) => item.device_mac),
  () => workspace.selectedDeviceMac.value,
);

watch(
  () => props.refreshKey,
  (key, prev) => {
    if (key == null) return;
    // Ignore the first run after mount; this page already initializes a clean state.
    if (prev == null) return;
    workbench.clearConversationState();
    void workbench.loadContext();
  },
);

/* ---------- 侧栏折叠 ---------- */
const SIDEBAR_STORAGE_KEY = "agent-page-sidebar-collapsed";
const sidebarCollapsed = ref(false);

onMounted(() => {
  sidebarCollapsed.value = localStorage.getItem(SIDEBAR_STORAGE_KEY) === "1";
});

function setSidebarCollapsed(collapsed: boolean) {
  sidebarCollapsed.value = collapsed;
  localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
}

function toggleSidebar() {
  setSidebarCollapsed(!sidebarCollapsed.value);
}

/* ---------- 对话区滚动 ---------- */
const scrollRef = ref<HTMLElement | null>(null);

/** 新消息或流式增量到达时贴到底部，与聊天界面预期一致 */
async function scrollToLatest() {
  await nextTick();
  const el = scrollRef.value;
  if (el) el.scrollTop = el.scrollHeight;
}

watch(
  () => {
    const list = workbench.messages.value;
    return [list.length, list.length ? list[list.length - 1].text.length : 0];
  },
  () => {
    void scrollToLatest();
  },
);

/* ---------- 当前选择上下文 ---------- */
const contextChips = computed(() => [
  workbench.selectedSubjectLabel.value,
  workbench.selectedWindow.value === "week" ? "过去一周" : "过去一天",
  `模型 ${workbench.selectedProvider.value}`,
  workbench.selectedEngine.value === "toolcall" ? "自主取数" : "固定流程",
]);

const sampleStatusText = computed(() => {
  if (workbench.demoDataStatus.value?.enabled && workbench.demoDataStatus.value.subject_count) {
    return `已纳入 ${workbench.demoDataStatus.value.subject_count} 位对象`;
  }
  return "样本待刷新";
});

/* ---------- 预设动作 ---------- */
/** 图标与数据说明；纯展示信息，与 composable 里的 workflow 定义解耦 */
const WORKFLOW_META: Record<string, { icon: LucideIcon; hint: string }> = {
  overview: { icon: LayoutDashboard, hint: "读取风险分层、设备在线率与告警统计" },
  risk_ranking: { icon: ListOrdered, hint: "按健康分与异常信号对全部对象排序" },
  community_report: { icon: FileText, hint: "汇总重点对象与告警热点，输出可归档报告" },
  alert_digest: { icon: BellRing, hint: "梳理窗口内告警的分布、趋势与处置顺序" },
  elder_focus: { icon: HeartPulse, hint: "读取体征曲线、健康分与异常记录" },
  elder_report: { icon: FileText, hint: "生成该老人的结构化健康分析报告" },
  device_focus: { icon: Database, hint: "读取设备上传状态与采样完整性" },
  report_generation: { icon: FileText, hint: "生成结构化分析报告" },
  free_chat: { icon: Sparkles, hint: "围绕当前范围自由提问" },
};

function workflowMeta(workflow: string) {
  return WORKFLOW_META[workflow] ?? { icon: Sparkles, hint: "围绕当前范围发起分析" };
}

const quickSuggestions = computed(() => workbench.quickActions.value.slice(0, 4));

/* ---------- 侧栏运行状态 ---------- */
const runStages = computed(() => workbench.stageRecords.value);

const activeStage = computed(() => {
  const list = runStages.value;
  return (
    [...list].reverse().find((item) => item.status === "running")
    ?? (list.length ? list[list.length - 1] : null)
  );
});

const doneStageCount = computed(
  () => runStages.value.filter((item) => item.status === "completed").length,
);

const runningTool = computed(() =>
  [...workbench.toolRecords.value].reverse().find((item) => item.status === "running"),
);

const showRunPanel = computed(() => workbench.running.value || runStages.value.length > 0);

/** 能力说明：把后端九个执行阶段归并成四步，避免罗列内部阶段名 */
const pipelineSteps = [
  { icon: Database, title: "读取数据", body: "按所选对象与时间范围取出体征采样、健康评分和告警记录。" },
  { icon: LineChart, title: "分析异常", body: "计算评分变化、检出异常波动，并做群体对比。" },
  { icon: Workflow, title: "检索与工具", body: "检索照护知识库，必要时调用图表与报告生成工具。" },
  { icon: FileText, title: "输出结论", body: "给出结论、处置建议，并附上图表与可归档报告。" },
];

function submitFreeChat() {
  void workbench.submit("free_chat");
}
</script>

<template>
  <section class="agent-page" :class="{ 'agent-page--narrow-side': sidebarCollapsed }">
    <!-- ===== 主体：对话 + 输入 ===== -->
    <div class="agent-main">
      <div ref="scrollRef" class="agent-scroll">
        <p v-if="workbench.errorText.value" class="feedback-banner feedback-error">
          {{ workbench.errorText.value }}
        </p>

        <!-- 空状态：预设动作卡直接落在对话区首屏 -->
        <div v-if="!workbench.messages.value.length" class="agent-welcome">
          <div class="agent-welcome__intro">
            <span class="agent-welcome__icon"><Sparkles :size="19" /></span>
            <h2>想了解{{ workbench.selectedSubjectLabel.value }}的哪方面？</h2>
            <p>选一个预设分析，或在下方直接提问。</p>
          </div>

          <div class="agent-welcome__cards">
            <button
              v-for="action in quickSuggestions"
              :key="action.workflow"
              type="button"
              class="guide-card"
              @click="workbench.submit(action.workflow, action.prompt)"
            >
              <span class="guide-card__icon">
                <component :is="workflowMeta(action.workflow).icon" :size="17" />
              </span>
              <strong class="guide-card__title">{{ action.label }}</strong>
              <small class="guide-card__hint">{{ workflowMeta(action.workflow).hint }}</small>
            </button>
          </div>
        </div>

        <!-- 消息流 -->
        <article
          v-for="message in workbench.messages.value"
          :key="message.id"
          class="agent-message"
          :class="`agent-message--${message.role}`"
        >
          <div class="agent-message__meta">
            <div class="agent-message__author">
              <span class="agent-message__avatar">
                <Bot v-if="message.role === 'assistant'" :size="15" />
                <span v-else>我</span>
              </span>
              <strong>{{ message.role === "assistant" ? "康养智能体" : "我" }}</strong>
            </div>
            <span class="agent-message__workflow">{{ workbench.workflowLabel(message.workflow) }}</span>
          </div>

          <AgentTracePanel
            v-if="message.role === 'assistant' && message.trace"
            :stages="message.trace.stages"
            :tools="message.trace.tools"
            :citations="message.trace.citations"
            :selected-model="message.trace.selectedModel"
            :degraded-notes="message.trace.degradedNotes"
            :streaming="message.status === 'streaming'"
          />

          <CommunityAgentAttachmentRenderer
            v-if="message.role === 'assistant' && message.attachments.length"
            :attachments="message.attachments"
          />

          <div
            v-if="message.role === 'user' || message.text || message.status !== 'completed'"
            class="agent-message__bubble"
            :data-role="message.role"
            :data-status="message.status"
          >
            <AgentMarkdownContent
              v-if="message.role === 'assistant' && message.text"
              :content="message.text"
              variant="bubble"
              :streaming="message.status === 'streaming'"
            />
            <p v-else>{{ message.text || (message.role === "assistant" ? "正在整理结果…" : "") }}</p>
          </div>
        </article>
      </div>

      <!-- 输入区：贴在对话区底边，不随内容滚动 -->
      <footer class="agent-composer">
        <div class="agent-composer__top">
          <div class="agent-composer__ctx">
            <span v-for="chip in contextChips" :key="chip" class="ctx-chip">{{ chip }}</span>
          </div>

          <div v-if="workbench.messages.value.length" class="agent-composer__quick">
            <button
              v-for="action in quickSuggestions"
              :key="action.workflow"
              type="button"
              class="agent-quick-pill"
              @click="workbench.submit(action.workflow, action.prompt)"
            >
              <component :is="workflowMeta(action.workflow).icon" :size="13" />
              {{ action.label }}
            </button>
          </div>
        </div>

        <textarea
          v-model="workbench.question.value"
          class="agent-composer__input"
          rows="2"
          :placeholder="
            workbench.selectedScope.value === 'elder'
              ? '例如：请分析这位老人过去一周的风险变化、异常原因和建议动作。'
              : '例如：请总结社区过去一天的高风险对象、告警热点和排班建议。'
          "
        />

        <div class="agent-composer__foot">
          <small class="agent-composer__hint">
            结论为辅助解读，不替代医疗诊断；处置请结合现场核实。
          </small>

          <div class="agent-composer__actions">
            <button
              v-if="workbench.running.value"
              type="button"
              class="agent-stop-btn"
              @click="workbench.cancel"
            >
              <Square :size="14" />
              停止
            </button>
            <button
              type="button"
              class="agent-start-btn"
              :disabled="workbench.running.value || !workbench.canAnalyze.value"
              @click="submitFreeChat"
            >
              <SendHorizontal :size="15" />
              {{ workbench.running.value ? "分析中…" : "开始分析" }}
            </button>
          </div>
        </div>
      </footer>
    </div>

    <!-- ===== 侧栏：设置 · 运行状态 · 流程说明 ===== -->
    <aside class="agent-side">
      <header class="agent-side__head">
        <Transition name="side-title">
          <div v-if="!sidebarCollapsed" class="agent-side__title">
            <strong>智慧康养智能体</strong>
            <small>AI 风险分析与报告</small>
          </div>
        </Transition>
        <button
          type="button"
          class="agent-side__toggle"
          :title="sidebarCollapsed ? '展开设置面板' : '收起设置面板'"
          @click="toggleSidebar"
        >
          <PanelRightOpen v-if="sidebarCollapsed" :size="16" />
          <PanelRightClose v-else :size="16" />
        </button>
      </header>

      <!-- 折叠态：图标轨道，保留可读的入口与运行指示，点任一项即展开 -->
      <Transition name="side-rail">
        <div v-if="sidebarCollapsed" class="side-rail">
          <button
            type="button"
            class="side-rail__btn"
            title="分析设置"
            @click="setSidebarCollapsed(false)"
          >
            <SlidersHorizontal :size="15" />
          </button>

          <button
            v-if="showRunPanel"
            type="button"
            class="side-rail__btn"
            :class="{ 'side-rail__btn--live': workbench.running.value }"
            :title="workbench.running.value ? `运行状态：正在${activeStage?.label ?? '分析'}` : '运行状态：已完成'"
            @click="setSidebarCollapsed(false)"
          >
            <Activity :size="15" />
            <span v-if="workbench.running.value" class="side-rail__dot"></span>
          </button>

          <button
            type="button"
            class="side-rail__btn"
            title="分析流程"
            @click="setSidebarCollapsed(false)"
          >
            <Workflow :size="15" />
          </button>

          <!-- 折叠时仍能一眼看到当前配置 -->
          <div class="side-rail__ctx">
            <span
              class="side-rail__tag"
              :title="workbench.selectedScope.value === 'elder' ? '分析范围：某位老人' : '分析范围：整个社区'"
            >
              {{ workbench.selectedScope.value === "elder" ? "个" : "社" }}
            </span>
            <span
              class="side-rail__tag"
              :title="workbench.selectedWindow.value === 'week' ? '时间范围：过去一周' : '时间范围：过去一天'"
            >
              {{ workbench.selectedWindow.value === "week" ? "周" : "日" }}
            </span>
          </div>
        </div>
      </Transition>

      <Transition name="side-body">
        <div v-if="!sidebarCollapsed" class="agent-side__scroll">
        <!-- 分析设置 -->
        <section class="side-card">
          <p class="side-card__label">分析设置</p>

          <div class="field">
            <span class="field__label">分析范围</span>
            <div class="seg">
              <button
                type="button"
                class="seg__btn"
                :class="{ 'seg__btn--on': workbench.selectedScope.value === 'elder' }"
                @click="workbench.selectedScope.value = 'elder'"
              >
                某位老人
              </button>
              <button
                type="button"
                class="seg__btn"
                :class="{ 'seg__btn--on': workbench.selectedScope.value === 'community' }"
                @click="workbench.selectedScope.value = 'community'"
              >
                整个社区
              </button>
            </div>
          </div>

          <label v-if="workbench.selectedScope.value === 'elder'" class="field">
            <span class="field__label">分析对象</span>
            <select v-model="workbench.selectedElderId.value" class="field__select">
              <option
                v-for="subject in workbench.elderSubjects.value"
                :key="subject.elder_id"
                :value="subject.elder_id"
              >
                {{ subject.elder_name }} / {{ subject.apartment }}
              </option>
            </select>
          </label>

          <div class="field">
            <span class="field__label">时间范围</span>
            <div class="seg">
              <button
                type="button"
                class="seg__btn"
                :class="{ 'seg__btn--on': workbench.selectedWindow.value === 'day' }"
                @click="workbench.selectedWindow.value = 'day'"
              >
                过去一天
              </button>
              <button
                type="button"
                class="seg__btn"
                :class="{ 'seg__btn--on': workbench.selectedWindow.value === 'week' }"
                @click="workbench.selectedWindow.value = 'week'"
              >
                过去一周
              </button>
            </div>
          </div>

          <label class="field">
            <span class="field__label">分析模型</span>
            <select v-model="workbench.selectedProvider.value" class="field__select">
              <option value="auto">自动</option>
              <option value="tongyi">Tongyi</option>
              <option value="ollama">Ollama</option>
            </select>
          </label>

          <div class="field">
            <span class="field__label">推理引擎</span>
            <div class="seg">
              <button
                type="button"
                class="seg__btn"
                :class="{ 'seg__btn--on': workbench.selectedEngine.value === 'pipeline' }"
                title="固定流程：每次拉取同一批数据，快且产出结构稳定"
                @click="workbench.selectedEngine.value = 'pipeline'"
              >
                固定流程
              </button>
              <button
                type="button"
                class="seg__btn"
                :class="{ 'seg__btn--on': workbench.selectedEngine.value === 'toolcall' }"
                title="自主取数：模型按问题决定调哪些工具，可多轮追查，更准但更慢"
                @click="workbench.selectedEngine.value = 'toolcall'"
              >
                自主取数
              </button>
            </div>
            <small class="field__hint">
              {{
                workbench.selectedEngine.value === "toolcall"
                  ? "模型按问题自行取数，可多轮追查；响应较慢。预设动作仍走固定流程。"
                  : "每次拉取固定数据集，响应快、产出结构稳定。"
              }}
            </small>
          </div>

          <div class="side-card__foot">
            <span class="side-card__sample">{{ sampleStatusText }}</span>
            <button
              type="button"
              class="ghost-btn"
              :disabled="workbench.refreshingSamples.value"
              @click="workbench.refreshCommunitySamples"
            >
              <RefreshCw :size="13" />
              {{ workbench.refreshingSamples.value ? "刷新中…" : "刷新样本" }}
            </button>
          </div>
        </section>

        <!-- 运行状态：不展开对话内的轨迹也能看到进度 -->
        <section v-if="showRunPanel" class="side-card">
          <p class="side-card__label">
            运行状态
            <span v-if="workbench.running.value" class="run-dot"></span>
          </p>

          <div class="run-now">
            <strong>
              {{
                runningTool
                  ? `正在调用 ${runningTool.title}`
                  : workbench.running.value
                    ? `正在${activeStage?.label ?? "分析"}`
                    : "分析已完成"
              }}
            </strong>
            <small>{{ runningTool?.summary || activeStage?.summary || activeStage?.detail || "" }}</small>
          </div>

          <div class="run-progress">
            <span class="run-progress__bar">
              <i
                :style="{
                  width: runStages.length
                    ? `${Math.round((doneStageCount / runStages.length) * 100)}%`
                    : '0%',
                }"
              ></i>
            </span>
            <small>{{ doneStageCount }}/{{ runStages.length }} 阶段</small>
          </div>

          <ul class="run-stages">
            <li
              v-for="stage in runStages"
              :key="stage.stage"
              class="run-stage"
              :class="`run-stage--${stage.status}`"
            >
              <span class="run-stage__dot"></span>
              <span class="run-stage__label">{{ stage.label }}</span>
              <small v-if="stage.elapsedMs != null" class="run-stage__ms">
                {{ Math.round(stage.elapsedMs) }}ms
              </small>
            </li>
          </ul>

          <p v-if="workbench.selectedModel.value" class="run-model">
            实际模型 {{ workbench.selectedModel.value }}
          </p>
        </section>

        <!-- 流程说明 -->
        <section class="side-card">
          <p class="side-card__label">分析流程</p>
          <ol class="flow-steps">
            <li v-for="(step, index) in pipelineSteps" :key="step.title">
              <span class="flow-steps__num">{{ index + 1 }}</span>
              <span class="flow-steps__body">
                <strong>{{ step.title }}</strong>
                <small>{{ step.body }}</small>
              </span>
            </li>
          </ol>
          <p class="flow-note">
            执行过程、调用的工具与引用的数据来源都会在回答里展开，分析中可随时中断。
          </p>
          </section>
        </div>
      </Transition>
    </aside>
  </section>
</template>

<style scoped>
/*
 * 聊天式布局：整页撑满可用高度，只有对话区滚动，输入框常驻底边。
 * 撑满依赖 AppShell 把 .app-shell__content 切到 --fill（align-content:stretch）；
 * 全局默认是 align-content:start，隐式网格行会按内容收缩，那样侧栏折叠后
 * 页面底部会留出空白。改这里的高度策略前，先确认 AppShell 的 FILL_HEIGHT_PAGES。
 */
.agent-page {
  height: 100%;
  min-height: 520px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 296px;
  gap: 14px;
  align-items: stretch;
  /* 网格轨道过渡（Chromium 107+ 支持），驱动侧栏收放时对话区平滑改宽 */
  transition: grid-template-columns 320ms cubic-bezier(0.22, 0.8, 0.3, 1);
}

.agent-page--narrow-side {
  grid-template-columns: minmax(0, 1fr) 48px;
}

/* ---------- 主体 ---------- */
.agent-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
}

.agent-scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 4px 4px 8px;
}

.agent-scroll::-webkit-scrollbar {
  width: 8px;
}

.agent-scroll::-webkit-scrollbar-thumb {
  background: var(--surface-2);
  border-radius: 4px;
}

/* ---------- 空状态 ---------- */
.agent-welcome {
  margin: auto 0;
  display: grid;
  gap: 18px;
  padding: 8px 0;
}

.agent-welcome__intro {
  display: grid;
  gap: 6px;
  justify-items: center;
  text-align: center;
}

.agent-welcome__icon {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-lg);
  background: var(--surface-cyan);
  color: var(--brand);
}

.agent-welcome__intro h2 {
  margin: 0;
  font-size: var(--fs-4);
  font-weight: 700;
  color: var(--text-main);
}

.agent-welcome__intro p {
  margin: 0;
  font-size: var(--fs-2);
  color: var(--text-muted);
}

.agent-welcome__cards {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

/* 预设动作数量随范围变化：社区 4 张铺满 2×2，老人 3 张时让末卡跨行补齐 */
.guide-card:last-child:nth-child(odd) {
  grid-column: span 2;
}

.guide-card {
  display: grid;
  gap: 7px;
  padding: 15px 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--panel-strong);
  text-align: left;
  font-family: inherit;
  cursor: pointer;
  box-shadow: var(--shadow-sm);
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}

.guide-card:hover {
  transform: translateY(-2px);
  border-color: color-mix(in srgb, var(--brand) 35%, transparent);
  box-shadow: var(--shadow);
}

/*
 * 依次入场，避免切换分析范围时四张卡齐刷刷弹出。
 * 必须用 backwards 而非 both：both 会在结束后锁住 transform，
 * 使上面的 :hover 浮起失效。
 */
.guide-card {
  animation: card-in 300ms cubic-bezier(0.22, 0.8, 0.3, 1) backwards;
}

.guide-card:nth-child(2) { animation-delay: 50ms; }
.guide-card:nth-child(3) { animation-delay: 100ms; }
.guide-card:nth-child(4) { animation-delay: 150ms; }

@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.guide-card__icon {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-md);
  background: var(--surface-cyan);
  color: var(--brand);
}

.guide-card__title {
  font-size: var(--fs-2);
  font-weight: 700;
  color: var(--text-main);
}

.guide-card__hint {
  font-size: var(--fs-1);
  color: var(--text-muted);
  line-height: 1.55;
}

/* ---------- 消息 ---------- */
.agent-message {
  display: grid;
  gap: 9px;
  max-width: 100%;
}

.agent-message--user {
  justify-self: end;
  max-width: min(620px, 100%);
}

.agent-message__meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.agent-message__author {
  display: flex;
  align-items: center;
  gap: 8px;
}

.agent-message__author strong {
  color: var(--text-main);
  font-weight: 700;
}

.agent-message__avatar {
  width: 26px;
  height: 26px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  background: var(--surface-cyan);
  color: var(--brand);
  font-size: var(--fs-1);
  font-weight: 700;
}

.agent-message__workflow {
  white-space: nowrap;
}

.agent-message__bubble {
  padding: 15px 17px;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--panel-strong);
  box-shadow: var(--shadow-sm);
}

.agent-message__bubble[data-status="streaming"] {
  border-color: color-mix(in srgb, var(--brand) 40%, transparent);
}

.agent-message__bubble[data-role="user"] {
  background: var(--surface-cyan);
  border-color: color-mix(in srgb, var(--brand) 24%, transparent);
}

.agent-message__bubble p {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.75;
  font-size: var(--fs-2);
  color: var(--text-main);
}

/* ---------- 输入区 ---------- */
.agent-composer {
  flex-shrink: 0;
  display: grid;
  gap: 10px;
  padding: 13px 15px;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--panel-strong);
  box-shadow: var(--shadow-sm);
}

.agent-composer__top {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 14px;
}

.agent-composer__ctx,
.agent-composer__quick {
  display: flex;
  flex-wrap: wrap;
  gap: 7px;
}

.ctx-chip {
  padding: 3px 10px;
  border-radius: 999px;
  background: var(--surface-cyan);
  color: var(--brand);
  font-size: var(--fs-0);
  font-weight: 700;
  white-space: nowrap;
}

.agent-quick-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 27px;
  padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-tinted);
  color: var(--text-sub);
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease;
}

.agent-quick-pill:hover {
  border-color: var(--brand);
  color: var(--brand);
}

.agent-composer__input {
  width: 100%;
  min-height: 62px;
  max-height: 26vh;
  resize: vertical;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--panel-tinted);
  color: var(--text-main);
  font: inherit;
  font-size: var(--fs-2);
  line-height: 1.65;
  outline: none;
  transition: border-color 150ms ease, box-shadow 150ms ease;
}

.agent-composer__input:focus {
  border-color: var(--brand);
  background: var(--panel-strong);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

.agent-composer__foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 14px;
}

.agent-composer__hint {
  font-size: var(--fs-1);
  color: var(--text-muted);
  line-height: 1.5;
}

.agent-composer__actions {
  display: flex;
  gap: 9px;
  flex-shrink: 0;
}

.agent-stop-btn,
.agent-start-btn {
  height: 36px;
  padding: 0 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  border-radius: 999px;
  font-size: var(--fs-2);
  font-weight: 700;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
}

.agent-stop-btn {
  border: 1px solid color-mix(in srgb, var(--risk-high) 40%, transparent);
  background: var(--surface-danger);
  color: var(--risk-high);
}

.agent-start-btn {
  min-width: 124px;
  border: none;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: #ffffff;
  box-shadow: var(--shadow-sm);
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.agent-start-btn:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow);
}

.agent-start-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* ---------- 侧栏 ---------- */
.agent-side {
  /* 定位上下文：收放动画的 leave 态用绝对定位脱离流，避免进出内容互相挤压 */
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--panel-strong);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
}

.agent-side__head {
  position: relative;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 12px 12px 15px;
  border-bottom: 1px solid var(--line);
}

.agent-page--narrow-side .agent-side__head {
  padding: 9px 0;
  justify-content: center;
  border-bottom: 1px solid var(--line);
}

.agent-side__title {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 1px;
}

.agent-side__title strong {
  font-size: var(--fs-2);
  font-weight: 700;
  color: var(--text-main);
}

.agent-side__title small {
  font-size: var(--fs-0);
  color: var(--text-muted);
}

.agent-side__toggle {
  flex-shrink: 0;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-tinted);
  color: var(--text-sub);
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease;
}

.agent-side__toggle:hover {
  border-color: var(--brand);
  color: var(--brand);
}

.agent-side__scroll {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: grid;
  gap: 12px;
  align-content: start;
  padding: 13px;
}

.agent-side__scroll::-webkit-scrollbar {
  width: 6px;
}

.agent-side__scroll::-webkit-scrollbar-thumb {
  background: var(--surface-2);
  border-radius: 3px;
}

/* ---------- 折叠态图标轨道 ---------- */
.side-rail {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 10px 0 14px;
  overflow: hidden;
}

.side-rail__btn {
  position: relative;
  width: 30px;
  height: 30px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-tinted);
  color: var(--text-sub);
  cursor: pointer;
  transition: transform 150ms ease, border-color 150ms ease, color 150ms ease;
}

.side-rail__btn:hover {
  transform: translateY(-1px);
  border-color: var(--brand);
  color: var(--brand);
}

.side-rail__btn--live {
  border-color: color-mix(in srgb, var(--brand) 45%, transparent);
  background: var(--surface-cyan);
  color: var(--brand);
}

.side-rail__dot {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--brand);
  box-shadow: 0 0 0 2px var(--panel-strong);
  animation: run-pulse 1.4s ease-in-out infinite;
}

/*
 * 顶部对齐而非贴底：快捷登录悬浮球可拖动且默认落在右下角，
 * 贴底会被它压住，靠留白避让不可靠。
 */
.side-rail__ctx {
  display: grid;
  gap: 6px;
  justify-items: center;
  margin-top: 4px;
  padding-top: 10px;
  border-top: 1px solid var(--line);
  width: 26px;
}

.side-rail__tag {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: var(--radius-sm);
  background: var(--surface-cyan);
  color: var(--brand);
  font-size: var(--fs-1);
  font-weight: 700;
}

/* ---------- 收放动画 ---------- */
/* 侧栏正文：淡出并向右让位，展开时略微延后进入，等宽度先铺开 */
.side-body-enter-active {
  transition: opacity 220ms ease 110ms, transform 220ms cubic-bezier(0.22, 0.8, 0.3, 1) 110ms;
}

.side-body-leave-active {
  transition: opacity 130ms ease, transform 130ms ease;
  position: absolute;
  inset: 44px 0 0;
}

.side-body-enter-from,
.side-body-leave-to {
  opacity: 0;
  transform: translateX(14px);
}

/* 图标轨道：反向进出，与正文交错 */
.side-rail-enter-active {
  transition: opacity 200ms ease 120ms, transform 200ms cubic-bezier(0.22, 0.8, 0.3, 1) 120ms;
}

.side-rail-leave-active {
  transition: opacity 120ms ease, transform 120ms ease;
  position: absolute;
  inset: 44px 0 0;
}

.side-rail-enter-from,
.side-rail-leave-to {
  opacity: 0;
  transform: translateX(-10px);
}

/* 标题：随宽度淡入淡出，避免在窄轨道里被挤压换行 */
.side-title-enter-active {
  transition: opacity 200ms ease 130ms;
}

.side-title-leave-active {
  transition: opacity 100ms ease;
  position: absolute;
}

.side-title-enter-from,
.side-title-leave-to {
  opacity: 0;
}

.side-card {
  display: grid;
  gap: 11px;
  padding: 13px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--panel-tinted);
}

.side-card__label {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--fs-0);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.field {
  display: grid;
  gap: 5px;
}

.field__label {
  font-size: var(--fs-1);
  font-weight: 600;
  color: var(--text-sub);
}

.field__hint {
  font-size: var(--fs-0);
  color: var(--text-muted);
  line-height: 1.5;
}

.seg {
  display: flex;
  padding: 2px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--surface-soft);
}

.seg__btn {
  flex: 1;
  min-width: 0;
  height: 28px;
  padding: 0 8px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text-sub);
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: background 150ms ease, color 150ms ease;
}

.seg__btn--on {
  background: var(--panel-strong);
  color: var(--brand);
  box-shadow: var(--shadow-sm);
}

.field__select {
  width: 100%;
  height: 32px;
  padding: 0 9px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-strong);
  color: var(--text-main);
  font-size: var(--fs-1);
  font-family: inherit;
  cursor: pointer;
  outline: none;
  min-width: 0;
}

.field__select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

.side-card__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 9px;
  border-top: 1px solid var(--line);
}

.side-card__sample {
  font-size: var(--fs-0);
  color: var(--text-muted);
}

.ghost-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  height: 28px;
  padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-strong);
  color: var(--text-sub);
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: border-color 150ms ease, color 150ms ease;
}

.ghost-btn:hover:not(:disabled) {
  border-color: var(--brand);
  color: var(--brand);
}

.ghost-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ---------- 侧栏运行状态 ---------- */
.run-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--brand);
  animation: run-pulse 1.4s ease-in-out infinite;
}

@keyframes run-pulse {
  0%, 100% { opacity: 0.35; }
  50% { opacity: 1; }
}

.run-now {
  display: grid;
  gap: 3px;
}

.run-now strong {
  font-size: var(--fs-2);
  color: var(--text-main);
  line-height: 1.4;
}

.run-now small {
  font-size: var(--fs-1);
  color: var(--text-muted);
  line-height: 1.5;
}

.run-progress {
  display: flex;
  align-items: center;
  gap: 8px;
}

.run-progress__bar {
  flex: 1;
  height: 5px;
  border-radius: 999px;
  background: var(--surface-0);
  overflow: hidden;
}

.run-progress__bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--brand), var(--brand-2));
  transition: width 320ms ease;
}

.run-progress small {
  flex-shrink: 0;
  font-size: var(--fs-0);
  font-family: var(--font-mono);
  color: var(--text-muted);
}

.run-stages {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 6px;
}

.run-stage {
  display: flex;
  align-items: center;
  gap: 7px;
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.run-stage__dot {
  flex-shrink: 0;
  width: 6px;
  height: 6px;
  border-radius: 999px;
  background: var(--surface-2);
}

.run-stage--completed .run-stage__dot { background: var(--risk-low); }
.run-stage--running .run-stage__dot { background: var(--brand); }
.run-stage--error .run-stage__dot { background: var(--risk-high); }

.run-stage--running .run-stage__label {
  color: var(--text-main);
  font-weight: 600;
}

.run-stage__label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.run-stage__ms {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: var(--fs-0);
  color: var(--text-muted);
}

.run-model {
  margin: 0;
  padding-top: 9px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-0);
  color: var(--text-muted);
}

/* ---------- 侧栏流程说明 ---------- */
.flow-steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 10px;
}

.flow-steps li {
  display: flex;
  gap: 9px;
  align-items: flex-start;
}

.flow-steps__num {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  margin-top: 1px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--surface-cyan);
  color: var(--brand);
  font-family: var(--font-mono);
  font-size: var(--fs-0);
  font-weight: 700;
}

.flow-steps__body {
  display: grid;
  gap: 1px;
}

.flow-steps__body strong {
  font-size: var(--fs-1);
  color: var(--text-main);
}

.flow-steps__body small {
  font-size: var(--fs-0);
  color: var(--text-muted);
  line-height: 1.55;
}

.flow-note {
  margin: 0;
  padding-top: 9px;
  border-top: 1px solid var(--line);
  font-size: var(--fs-0);
  color: var(--text-muted);
  line-height: 1.55;
}

/* ---------- 窄屏：回退为单列纵向流 ---------- */
@media (max-width: 1080px) {
  .agent-page,
  .agent-page--narrow-side {
    height: auto;
    min-height: 0;
    grid-template-columns: 1fr;
  }

  .agent-side {
    order: -1;
  }

  .agent-side__scroll {
    max-height: none;
    overflow: visible;
  }

  .agent-scroll {
    overflow: visible;
    max-height: none;
  }

  .agent-welcome {
    margin: 0;
  }

  .agent-welcome__cards {
    grid-template-columns: 1fr;
  }

  .agent-message--user {
    justify-self: stretch;
    max-width: 100%;
  }
}
</style>
