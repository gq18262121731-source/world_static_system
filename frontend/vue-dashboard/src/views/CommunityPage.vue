<script setup lang="ts">
import { computed, toRef, ref } from "vue";
import { AlertTriangle } from "lucide-vue-next";

import type { SessionUser } from "../api/client";
import CommunityAlertsPanel from "../components/CommunityAlertsPanel.vue";
import CommunityDeviceRail from "../components/CommunityDeviceRail.vue";
import CommunityHandoverReport from "../components/CommunityHandoverReport.vue";
import CommunityQuickActions from "../components/CommunityQuickActions.vue";
import CommunityRealtimeVitalsPanel from "../components/CommunityRealtimeVitalsPanel.vue";
import CommunityTaskPanel from "../components/CommunityTaskPanel.vue";
import ModalShell from "../components/layout/ModalShell.vue";
import PageHeader from "../components/layout/PageHeader.vue";
import DeltaChip from "../components/viz/DeltaChip.vue";
import MiniSparkline from "../components/viz/MiniSparkline.vue";
import { useCommunityWorkspace } from "../composables/useCommunityWorkspace";
import { useCountUp } from "../composables/useCountUp";
import { useOverviewModals } from "../composables/useOverviewModals";

const props = defineProps<{
  sessionUser: SessionUser;
  canAccessDebug?: boolean;
}>();

const workspace = useCommunityWorkspace(toRef(props, "sessionUser"));
const isSimulating = ref(false);

/** 未确认告警数：来自真实告警流，与告警面板同源 */
const unacknowledgedAlarmCount = computed(
  () => workspace.recentAlerts.value.filter((item) => !item.acknowledged).length,
);

/**
 * 值守自检：在当前已绑定设备的老人上触发一次 SOS，用于验证告警链路（弹窗、音效、处置流程）是否通畅。
 * 仅调试权限可见；事件带 simulated 标记，便于与真实求助区分。
 */
async function triggerSOSSimulation() {
  if (isSimulating.value) return;

  const target = workspace.topRiskElders.value.find((item) => Boolean(item.device_mac));
  if (!target?.device_mac) return;

  isSimulating.value = true;
  try {
    window.dispatchEvent(
      new CustomEvent("sos-simulation", {
        detail: {
          id: `sim_${Date.now()}`,
          device_mac: target.device_mac,
          alarm_type: "sos",
          alarm_level: 1,
          alarm_layer: "device",
          message: `${target.elder_name} 触发紧急求助`,
          created_at: new Date().toISOString(),
          acknowledged: false,
          metadata: {
            is_real_device: true,
            elder_id: target.elder_id,
            elder_name: target.elder_name,
            apartment: target.apartment,
            sos_trigger: "double_click",
            simulated: true,
          },
        },
      }),
    );
  } finally {
    setTimeout(() => {
      isSimulating.value = false;
    }, 2000);
  }
}

const syncLabel = computed(() =>
  workspace.lastSyncAt.value
    ? workspace.lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false })
    : "尚未同步",
);

const noDeviceCount = computed(() =>
  workspace.topRiskElders.value.filter((item) => !item.device_mac || item.device_status === "no_device").length,
);

const offlineCount = computed(() =>
  workspace.topRiskElders.value.filter((item) => item.device_status === "offline").length,
);

const pageMeta = computed(() => [
  `社区 ${workspace.community.value?.name ?? "未分配"}`,
  `无设备 ${noDeviceCount.value}`,
  `离线 ${offlineCount.value}`,
  `同步 ${syncLabel.value}`,
]);

/* ---- 态势 Hero ---- */
const averageHealthScore = computed(() => {
  const scores = workspace.topRiskElders.value
    .map((item) => item.latest_health_score)
    .filter((score): score is number => score != null && Number.isFinite(score));
  if (!scores.length) return null;
  return scores.reduce((sum, score) => sum + score, 0) / scores.length;
});

const ringScoreDisplay = useCountUp(averageHealthScore);
const avgScoreDisplay = useCountUp(averageHealthScore, { decimals: 1 });
const onlineDisplay = useCountUp(computed(() => workspace.metrics.value?.device_online ?? null));
const elderCountDisplay = useCountUp(computed(() => workspace.metrics.value?.elder_count ?? null));

const RING_CIRCUMFERENCE = 289;
const ringOffset = computed(() => {
  const score = ringScoreDisplay.value;
  if (score == null) return RING_CIRCUMFERENCE;
  return RING_CIRCUMFERENCE - (RING_CIRCUMFERENCE * Math.min(Math.max(score, 0), 100)) / 100;
});

/*
 * Hero 主 KPI 的趋势序列。
 * 后端对没有采样的时间桶返回 average_health_score=0，那是"无数据"而非"健康分为 0"，
 * 直接入图会画出从 0 暴涨的假趋势，因此必须先剔除。
 */
const scoreSeries = computed(() =>
  workspace.scoreTrend.value
    .map((point) => point.average_health_score)
    .filter((value): value is number => value != null && Number.isFinite(value) && value > 0),
);

const scoreDelta = computed(() => {
  const series = scoreSeries.value;
  if (series.length < 2) return null;
  return series[series.length - 1] - series[0];
});

const alertSeries = computed(() =>
  workspace.scoreTrend.value.map((point) => point.alert_count ?? 0),
);

/** 全零的告警序列画出来只是一条平线，不如让位给文字说明 */
const hasAlertTrend = computed(
  () => alertSeries.value.length > 1 && Math.max(...alertSeries.value) > 0,
);

const heroSummary = computed(() => {
  const total = workspace.metrics.value?.device_total ?? 0;
  const highRisk = workspace.metrics.value?.high_risk_elder_count ?? 0;
  if (!total) return "暂无设备纳入分析，等待成员设备完成注册与绑定。";
  if (highRisk > 0) return `${total} 台设备纳入分析，${highRisk} 个高风险对象需要本班次优先闭环。`;
  return `${total} 台设备纳入分析，整体平稳，保持常规巡检节奏。`;
});

/* ---- 弹窗：告警、交接报告、值守任务都改为弹出查看，不占页面篇幅 ---- */
const modals = useOverviewModals();

/** 告警里点"查看对象"：切换焦点老人并关掉弹窗，让用户直接看到实时曲线 */
function locateElderFromAlert(elderId: string) {
  workspace.setSelectedElderId(elderId);
  modals.alertsOpen.value = false;
}

function goToTopology() {
  window.location.hash = "#/topology";
}
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="社区监护态势"
      title="总览监护"
      description="本班次社区整体健康态势与告警处置情况。点选老人卡片可查看其实时体征曲线。"
      :meta="pageMeta"
    >
      <template #actions>
        <button type="button" class="modern-refresh-btn" @click="workspace.refreshDashboardData">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>
          </svg>
          刷新数据
        </button>
        
        <button
          v-if="canAccessDebug"
          type="button"
          class="modern-simulate-alarm-icon-btn"
          :class="{ 'modern-simulate-alarm-icon-btn--active': isSimulating }"
          :disabled="isSimulating"
          :title="isSimulating ? '自检进行中…' : '告警链路自检：在已绑定设备上触发一次 SOS'"
          @click="triggerSOSSimulation"
        >
          <AlertTriangle :size="16" />
        </button>
      </template>
      
    </PageHeader>

    <p v-if="workspace.dashboardLoadError.value" class="feedback-banner feedback-error">
      {{ workspace.dashboardLoadError.value }}
    </p>

    <div v-else class="overview-stage stage-enter">
      <!-- 社区态势 Hero -->
      <section class="panel hero-panel">
        <div class="hero-score">
          <div class="hero-ring">
            <svg width="108" height="108" viewBox="0 0 108 108">
              <circle class="hero-ring__track" cx="54" cy="54" r="46" />
              <circle
                class="hero-ring__bar"
                cx="54"
                cy="54"
                r="46"
                :style="{ strokeDashoffset: ringOffset }"
              />
            </svg>
            <div class="hero-ring__val">
              <b>{{ ringScoreDisplay != null ? Math.round(ringScoreDisplay) : "--" }}</b>
              <span>社区健康指数</span>
            </div>
          </div>
          <div class="hero-score__meta">
            <h2>今日社区态势</h2>
            <p>{{ heroSummary }}</p>
            <span class="hero-score__tag">同步 {{ syncLabel }}</span>
          </div>
        </div>

        <div class="hero-kpis">
          <!-- 主 KPI：跨列 + 趋势线，承担"北极星指标"的视觉重量 -->
          <div class="hero-kpi hero-kpi--primary">
            <div class="hero-kpi__top">
              <span class="hero-kpi__label">平均健康分</span>
              <DeltaChip :delta="scoreDelta" :decimals="1" />
            </div>
            <span class="hero-kpi__value hero-kpi__value--lg">
              {{ avgScoreDisplay != null ? avgScoreDisplay.toFixed(1) : "--" }}
            </span>
            <MiniSparkline v-if="scoreSeries.length > 1" :values="scoreSeries" :height="34" tone="auto" />
            <span class="hero-kpi__foot">
              {{ scoreSeries.length > 1 ? `近 ${scoreSeries.length} 个时段趋势` : "数据积累中，暂不足以显示趋势" }}
            </span>
          </div>

          <div class="hero-kpi">
            <span class="hero-kpi__label">在线设备</span>
            <span class="hero-kpi__value">
              {{ onlineDisplay ?? 0 }}<small>/{{ workspace.metrics.value?.device_total ?? 0 }}</small>
            </span>
            <span class="hero-kpi__foot">离线 {{ workspace.metrics.value?.device_offline ?? 0 }} · 待激活 {{ workspace.metrics.value?.device_pending ?? 0 }}</span>
          </div>

          <div
            class="hero-kpi hero-kpi--clickable"
            :class="{ 'hero-kpi--alert': unacknowledgedAlarmCount > 0 }"
            title="查看告警队列"
            @click="modals.openAlerts()"
          >
            <span class="hero-kpi__label">
              <AlertTriangle :size="13" />
              未确认告警
            </span>
            <span class="hero-kpi__value">{{ unacknowledgedAlarmCount }}</span>
            <MiniSparkline
              v-if="hasAlertTrend"
              :values="alertSeries"
              :height="18"
              :rise-is-good="false"
              :show-last-dot="false"
            />
            <span v-else class="hero-kpi__foot">
              {{ unacknowledgedAlarmCount > 0 ? "待值守确认处置" : "全部已确认" }}
            </span>
          </div>

          <div class="hero-kpi">
            <span class="hero-kpi__label">监护对象</span>
            <span class="hero-kpi__value">{{ elderCountDisplay ?? 0 }}</span>
            <span class="hero-kpi__foot">无设备 {{ noDeviceCount }} · 离线 {{ offlineCount }}</span>
          </div>

          <div
            class="hero-kpi"
            :class="{ 'hero-kpi--alert': (workspace.metrics.value?.high_risk_elder_count ?? 0) > 0 }"
          >
            <span class="hero-kpi__label">高风险对象</span>
            <span class="hero-kpi__value">{{ workspace.metrics.value?.high_risk_elder_count ?? 0 }}</span>
            <span class="hero-kpi__foot">
              {{ (workspace.metrics.value?.high_risk_elder_count ?? 0) > 0 ? "需本班次优先跟进" : "暂无高风险对象" }}
            </span>
          </div>
        </div>
      </section>

      <CommunityQuickActions
        :alarm-count="unacknowledgedAlarmCount"
        :offline-count="offlineCount"
        @go-alarms="modals.openAlerts()"
        @go-report="modals.openReport()"
        @new-task="modals.openTask()"
        @go-topology="goToTopology"
      />

      <CommunityDeviceRail
        :elders="workspace.topRiskElders.value"
        :selected-elder-id="workspace.selectedElderId.value"
        @select="workspace.setSelectedElderId"
      />

      <CommunityRealtimeVitalsPanel
        :elder="workspace.selectedElder.value"
        :device="workspace.selectedDevice.value"
        :current-sample="workspace.selectedMonitorCurrentSample.value"
        :samples="workspace.selectedMonitorSamples.value"
        :awaiting-realtime="workspace.isAwaitingSelectedRealtime.value"
      />

    </div>

    <!-- 告警 -->
    <ModalShell
      :open="modals.alertsOpen.value"
      title="告警队列"
      :subtitle="`共 ${workspace.recentAlerts.value.length} 条，未确认 ${unacknowledgedAlarmCount} 条`"
      size="md"
      @close="modals.alertsOpen.value = false"
    >
      <CommunityAlertsPanel
        :alerts="workspace.recentAlerts.value"
        :elders="workspace.topRiskElders.value"
        @locate="locateElderFromAlert"
      />
    </ModalShell>

    <!-- 值守任务 -->
    <ModalShell
      :open="modals.taskOpen.value"
      title="值守任务"
      subtitle="随访、巡检与交接事项"
      size="sm"
      @close="modals.taskOpen.value = false"
    >
      <CommunityTaskPanel :elders="workspace.topRiskElders.value" />
    </ModalShell>

    <!-- 交接报告 -->
    <ModalShell
      :open="modals.reportOpen.value"
      title="社区健康运营交接报告"
      subtitle="屏幕版便于浏览，可导出 A4 版打印归档"
      size="lg"
      @close="modals.reportOpen.value = false"
    >
      <CommunityHandoverReport
        :community-name="workspace.community.value?.name ?? '当前社区'"
        :device-macs="workspace.deviceStatuses.value.map((item) => item.device_mac)"
        :device-statuses="workspace.deviceStatuses.value"
        :recent-alerts="workspace.recentAlerts.value"
      />
    </ModalShell>
  </section>
</template>

<style scoped>
.overview-stage,
.overview-stage__detail-row {
  display: grid;
  gap: 18px;
}

/* ---- 态势 Hero ---- */
.hero-panel {
  display: flex;
  align-items: center;
  gap: 26px;
  flex-wrap: wrap;
}

.hero-score {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.hero-ring {
  position: relative;
  width: 108px;
  height: 108px;
}

.hero-ring svg {
  transform: rotate(-90deg);
}

.hero-ring__track {
  fill: none;
  stroke: var(--surface-0);
  stroke-width: 9;
}

.hero-ring__bar {
  fill: none;
  stroke: var(--brand);
  stroke-width: 9;
  stroke-linecap: round;
  stroke-dasharray: 289;
  transition: stroke-dashoffset 900ms cubic-bezier(0.4, 0, 0.2, 1);
}

.hero-ring__val {
  position: absolute;
  inset: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  text-align: center;
}

.hero-ring__val b {
  font-family: var(--font-mono);
  font-size: 30px;
  display: block;
  line-height: 1;
  color: var(--text-main);
}

.hero-ring__val span {
  font-size: 12px;
  color: var(--text-muted);
}

.hero-score__meta h2 {
  margin: 0 0 4px;
  font-size: 19px;
  font-family: var(--font-display);
  color: var(--text-main);
}

.hero-score__meta p {
  margin: 0;
  font-size: 14px;
  color: var(--text-sub);
  max-width: 220px;
  line-height: 1.55;
}

.hero-score__tag {
  display: inline-flex;
  margin-top: 8px;
  font-size: 13px;
  color: var(--brand);
  background: var(--surface-cyan);
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 600;
}

/* 主次分明：主 KPI 占据左侧整列，次 KPI 三个紧凑排布 */
.hero-kpis {
  flex: 1;
  min-width: 460px;
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr) minmax(0, 1fr);
  grid-template-rows: auto auto;
  gap: 12px;
}

.hero-kpi--primary {
  grid-row: span 2;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-color: color-mix(in srgb, var(--brand) 28%, transparent);
  background: linear-gradient(160deg, var(--surface-cyan), var(--panel-tinted) 70%);
}

.hero-kpi__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.hero-kpi__value--lg {
  font-size: 38px;
  line-height: 1.1;
  margin-top: 2px;
}

.hero-kpi--primary .hero-kpi__foot {
  margin-top: auto;
}

.hero-kpi {
  border: 1px solid var(--line);
  background: var(--panel-tinted);
  border-radius: var(--radius-md);
  padding: 13px 15px;
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.hero-kpi:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.hero-kpi--clickable {
  cursor: pointer;
}

.hero-kpi__label {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 13px;
  color: var(--text-muted);
}

.hero-kpi__value {
  display: block;
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 700;
  margin-top: 4px;
  color: var(--text-main);
}

.hero-kpi__value small {
  font-size: 13.5px;
  color: var(--text-muted);
  font-weight: 400;
}

.hero-kpi__foot {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.hero-kpi--alert .hero-kpi__value,
.hero-kpi--alert .hero-kpi__label {
  color: var(--risk-high);
}

.hero-kpi--alert {
  border-color: rgba(197, 48, 48, 0.35);
  background: var(--surface-danger);
}

/* ---- 告警时间线 ---- */
.alert-timeline {
  display: grid;
  gap: 0;
}

@keyframes tl-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(197, 48, 48, 0.45); }
  70%  { box-shadow: 0 0 0 7px rgba(197, 48, 48, 0); }
  100% { box-shadow: 0 0 0 0 rgba(197, 48, 48, 0); }
}

.overview-stage {
  width: 100%;
  align-content: start;
}

.overview-stage > * {
  min-width: 0;
}

@media (max-width: 1280px) {
  .overview-stage__insight-grid {
    grid-template-columns: 1fr;
  }
}

/* 现代化刷新按钮 */
.modern-refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border: 2px solid #e2e8f0;
  border-radius: 12px;
  background: #ffffff;
  color: #475569;
  font-size: 0.9rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 200ms ease;
  white-space: nowrap;
}

.modern-refresh-btn:hover {
  background: #0891b2;
  border-color: #0891b2;
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(8, 145, 178, 0.3);
}

.modern-refresh-btn svg {
  transition: transform 200ms ease;
}

.modern-refresh-btn:hover svg {
  transform: rotate(180deg);
}

/* 低调的模拟告警图标按钮（方案B） */
.modern-simulate-alarm-icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border: 1px solid #fca5a5;
  border-radius: 8px;
  background: #ffffff;
  color: #ef4444;
  cursor: pointer;
  transition: all 200ms ease;
}

.modern-simulate-alarm-icon-btn:hover:not(:disabled) {
  background: #fef2f2;
  border-color: #ef4444;
  transform: translateY(-1px);
  box-shadow: 0 2px 8px rgba(239, 68, 68, 0.2);
}

.modern-simulate-alarm-icon-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.modern-simulate-alarm-icon-btn--active {
  background: #0d9463;
  border-color: #0d9463;
  color: #ffffff;
  animation: pulse-simulate-icon 2s infinite;
}

@keyframes pulse-simulate-icon {
  0%, 100% {
    box-shadow: 0 2px 8px rgba(13, 148, 99, 0.3);
  }
  50% {
    box-shadow: 0 2px 12px rgba(13, 148, 99, 0.5);
  }
}

@media (max-width: 1180px) {
  .overview-stage__detail-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 1100px) {
  .hero-kpis {
    grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
    grid-template-rows: auto;
  }

  .hero-kpi--primary {
    grid-row: auto;
    grid-column: span 2;
  }
}

@media (max-width: 760px) {
  .alerts-panel__head {
    flex-direction: column;
  }

  .hero-kpis {
    min-width: 0;
    grid-template-columns: 1fr;
  }

  .hero-kpi--primary {
    grid-column: auto;
  }
}
</style>
