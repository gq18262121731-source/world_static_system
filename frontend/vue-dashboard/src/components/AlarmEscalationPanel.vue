<script setup lang="ts">
import { computed } from "vue";
import type { AlarmRecord, HealthSample } from "../api/client";

type StageTone = "stable" | "warning" | "critical";

const props = defineProps<{
  sample: HealthSample | null;
  trend: HealthSample[];
  focusAlarm: AlarmRecord | null;
}>();

const thresholdItems = [
  { label: "血氧", value: "低于 93%" },
  { label: "体温", value: "高于或等于 37.8°C" },
  { label: "心率", value: "高于 110 bpm 或低于 45 bpm" },
  { label: "SOS", value: "样本中包含 SOS 标记" },
] as const;

function isAbnormal(sample: HealthSample | null) {
  if (!sample) return false;
  return Boolean(
    sample.sos_flag
      || sample.blood_oxygen < 93
      || sample.temperature >= 37.8
      || sample.heart_rate >= 110
      || sample.heart_rate <= 45,
  );
}

const sustainedAbnormal = computed(() => {
  if (props.trend.length < 3) return false;
  return props.trend.slice(-3).every((item) => isAbnormal(item));
});

const activeStage = computed(() => {
  if (props.focusAlarm) return 4;
  if (sustainedAbnormal.value) return 3;
  if (isAbnormal(props.sample)) return 2;
  return 1;
});

const stages = computed(() => [
  { id: 1, label: "正常", description: "指标处于常规观察区间。", active: activeStage.value >= 1 },
  { id: 2, label: "异常", description: "出现单次或短时异常波动。", active: activeStage.value >= 2 },
  { id: 3, label: "持续异常", description: "多个样本连续异常，需要升级关注。", active: activeStage.value >= 3 },
  { id: 4, label: "报警", description: "已触发告警，需立即处置。", active: activeStage.value >= 4 },
]);

const currentStage = computed(() => stages.value[activeStage.value - 1]);

const stageTone = computed<StageTone>(() => {
  if (activeStage.value === 4) return "critical";
  if (activeStage.value === 2 || activeStage.value === 3) return "warning";
  return "stable";
});

const stageSummary = computed(() => {
  if (!props.sample) {
    return "尚未收到实时体征数据，暂时无法判断当前阶段。设备恢复上传后会自动更新。";
  }
  if (props.focusAlarm) {
    return `已触发告警：“${props.focusAlarm.message}”。请先完成确认与处置，再查看健康报告中的跟进建议。`;
  }
  if (sustainedAbnormal.value) {
    return "最近多个样本连续异常，已经从单次波动升级为持续异常，建议立即进入重点观察状态。";
  }
  if (isAbnormal(props.sample)) {
    return "当前出现单次异常样本，建议继续看后续样本是否恢复，避免遗漏持续异常。";
  }
  return "当前体征整体平稳，处于常规观察阶段，保持日常关注即可。";
});

const evidence = computed(() => {
  const rows: string[] = [];
  if (!props.sample) return ["尚未收到实时体征数据，暂无法给出判断依据。"];
  if (props.sample.blood_oxygen < 93) rows.push(`当前血氧 ${props.sample.blood_oxygen}% ，已低于常规观察阈值。`);
  if (props.sample.temperature >= 37.8) rows.push(`当前体温 ${props.sample.temperature.toFixed(1)}°C ，已进入异常观察区间。`);
  if (props.sample.heart_rate >= 110 || props.sample.heart_rate <= 45) rows.push(`当前心率 ${props.sample.heart_rate} bpm ，需要重点关注。`);
  if (props.sample.sos_flag) rows.push("当前样本包含 SOS 标记。");
  if (sustainedAbnormal.value) rows.push("最近连续 3 个样本均表现为异常，已满足持续异常观察条件。");
  if (props.focusAlarm) rows.push(`当前已生成告警：${props.focusAlarm.message}`);
  if (!rows.length) rows.push("当前样本整体平稳，仍处于常规观察阶段。");
  return rows;
});

const alarmDetails = computed(() => {
  if (!props.focusAlarm) return [];
  return [
    { label: "告警类型", value: props.focusAlarm.alarm_type },
    { label: "告警层级", value: props.focusAlarm.alarm_layer },
    { label: "告警等级", value: String(props.focusAlarm.alarm_level) },
    { label: "触发时间", value: new Date(props.focusAlarm.created_at).toLocaleString("zh-CN", { hour12: false }) },
  ];
});

const actionChecklist = computed(() => {
  if (activeStage.value === 4) {
    return [
      "立即电话确认或现场核查老人状况，必要时联系社区值守与急救。",
      "处置完成后在告警队列中确认，避免重复派工。",
      "不要仅凭单次体征恢复就判定风险解除，需持续观察至少 30 分钟。",
    ];
  }
  if (activeStage.value === 3) {
    return [
      "已连续多次异常，建议主动联系老人或家属核实当前状况。",
      "查看健康报告中的关键发现，判断是否需要安排上门复测。",
      "持续观察后续体征，异常不缓解应升级为告警处理。",
    ];
  }
  if (activeStage.value === 2) {
    return [
      "出现单次异常波动，先观察后续几次采样是否自行恢复。",
      "结合健康报告的评估结论，判断是否需要主动联系老人。",
      "若异常重复出现，将自动升级为持续异常状态。",
    ];
  }
  return [
    "当前处于常规观察阶段，按日常节奏关注即可。",
    "出现异常体征时，本面板会自动升级阶段并给出对应处置建议。",
  ];
});
</script>

<template>
  <section class="panel alarm-escalation-panel">
    <div class="alarm-head">
      <div>
        <h2>异常升级状态</h2>
        <p class="panel-subtitle">当前处于哪个阶段、判断依据是什么、下一步该怎么做。</p>
      </div>
      <div class="alarm-head-meta">
        <span class="status-tag" :class="`tone-${stageTone}`">当前阶段 {{ currentStage.label }}</span>
        <span class="meta-pill">{{ focusAlarm ? "已触发告警" : "未触发告警" }}</span>
      </div>
    </div>

    <div class="alarm-overview">
      <article class="alarm-stage-card" :class="`tone-${stageTone}`">
        <p class="section-eyebrow">当前阶段</p>
        <h3>{{ currentStage.label }}</h3>
        <p>{{ stageSummary }}</p>
        <div class="alarm-stage-meta">
          <span class="meta-pill">实时数据 {{ sample ? "正常上传" : "未上传" }}</span>
          <span class="meta-pill">已采集 {{ trend.length }} 次</span>
        </div>
      </article>

      <article class="alarm-detail-card">
        <h3>{{ focusAlarm ? "当前告警信息" : "当前处理建议" }}</h3>
        <div v-if="alarmDetails.length" class="alarm-detail-grid">
          <article v-for="item in alarmDetails" :key="item.label" class="alarm-detail-item">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </article>
        </div>
        <ul class="list-copy compact">
          <li v-for="item in actionChecklist" :key="item">{{ item }}</li>
        </ul>
      </article>
    </div>

    <div class="flow-grid flow-grid--timeline">
      <article v-for="stage in stages" :key="stage.id" class="flow-card" :class="{ active: stage.active, current: stage.id === activeStage }">
        <span class="flow-index">{{ stage.id }}</span>
        <div class="flow-copy">
          <strong>{{ stage.label }}</strong>
          <p>{{ stage.description }}</p>
        </div>
      </article>
    </div>

    <div class="alarm-support-grid">
      <article class="flow-evidence">
        <h3>当前判断依据</h3>
        <ul class="list-copy">
          <li v-for="item in evidence" :key="item">{{ item }}</li>
        </ul>
      </article>

      <article class="flow-evidence">
        <h3>观察阈值</h3>
        <ul class="list-copy compact">
          <li v-for="item in thresholdItems" :key="item.label">{{ item.label }}：{{ item.value }}</li>
        </ul>
      </article>
    </div>
  </section>
</template>

<style scoped>
.alarm-escalation-panel,
.alarm-overview,
.flow-grid,
.alarm-support-grid,
.alarm-detail-grid {
  display: grid;
  gap: 14px;
}

.alarm-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.alarm-head-meta,
.alarm-stage-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.alarm-overview,
.alarm-support-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.alarm-stage-card,
.alarm-detail-card,
.flow-card,
.flow-evidence,
.alarm-detail-item {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  padding: 16px 18px;
}

.alarm-stage-card,
.alarm-detail-card,
.flow-evidence {
  display: grid;
  gap: 12px;
}

.alarm-stage-card h3,
.alarm-detail-card h3,
.flow-evidence h3 {
  margin: 0;
}

.alarm-stage-card p {
  margin: 0;
  color: var(--text-sub);
  line-height: 1.78;
}

.alarm-stage-card.tone-critical {
  border-color: color-mix(in srgb, var(--risk-high) 40%, transparent);
  background: var(--surface-danger);
}

.alarm-stage-card.tone-critical h3 {
  color: var(--risk-high);
}

.alarm-stage-card.tone-warning {
  border-color: color-mix(in srgb, var(--risk-medium) 40%, transparent);
  background: var(--surface-warning);
}

.alarm-stage-card.tone-warning h3 {
  color: var(--risk-medium);
}

.alarm-stage-card.tone-stable {
  border-color: color-mix(in srgb, var(--risk-low) 35%, transparent);
  background: var(--surface-success);
}

.alarm-stage-card.tone-stable h3 {
  color: var(--risk-low);
}

.alarm-detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.alarm-detail-item span {
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 700;
}

.alarm-detail-item strong {
  display: block;
  margin-top: 8px;
  color: var(--text-main);
  line-height: 1.5;
}

.flow-grid--timeline {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.flow-card {
  display: grid;
  gap: 12px;
  opacity: 0.58;
}

.flow-card.active {
  opacity: 1;
}

.flow-card.current {
  border-color: color-mix(in srgb, var(--brand) 45%, transparent);
  background: var(--surface-cyan);
  box-shadow: var(--shadow);
}

.flow-index {
  display: inline-flex;
  width: 34px;
  height: 34px;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: var(--surface-cyan);
  color: var(--brand);
  font-weight: 800;
}

.flow-copy strong {
  display: block;
}

.flow-copy p {
  margin: 8px 0 0;
  color: var(--text-sub);
  line-height: 1.68;
}

@media (max-width: 1100px) {
  .alarm-overview,
  .alarm-support-grid,
  .flow-grid--timeline,
  .alarm-detail-grid {
    grid-template-columns: 1fr;
  }

  .alarm-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
