<script setup lang="ts">
import { computed } from "vue";
import type {
  AgentDeviceHealthReport,
  CareHealthEvaluationSummary,
  CareHealthReportSummary,
} from "../api/client";

type RiskTone = "stable" | "warning" | "critical" | "neutral";

const props = defineProps<{
  isBound: boolean;
  subjectName: string;
  deviceMac: string;
  evaluation: CareHealthEvaluationSummary | null;
  reportSummary: CareHealthReportSummary | null;
  generatedReport: AgentDeviceHealthReport | null;
  reportLoading: boolean;
  reportError: string;
}>();

const metricLabelMap: Record<string, { label: string; unit?: string; digits?: number }> = {
  heart_rate: { label: "心率", unit: "bpm" },
  blood_oxygen: { label: "血氧", unit: "%" },
  temperature: { label: "体温", unit: "°C", digits: 1 },
  health_score: { label: "健康评分", unit: "分" },
  battery: { label: "设备电量", unit: "%" },
  steps: { label: "步数", unit: "步" },
  ambient_temperature: { label: "环境温度", unit: "°C", digits: 1 },
  surface_temperature: { label: "表面温度", unit: "°C", digits: 1 },
};

function normalizeRisk(level?: string | null): { label: string; tone: RiskTone; note: string } {
  const source = (level ?? "").toLowerCase();
  if (source.includes("high") || source.includes("高")) {
    return { label: "高风险", tone: "critical", note: "建议优先查看建议动作和异常升级阶段。" };
  }
  if (source.includes("medium") || source.includes("mid") || source.includes("中")) {
    return { label: "中风险", tone: "warning", note: "当前存在波动，建议结合趋势和报告继续观察。" };
  }
  if (source.includes("low") || source.includes("低")) {
    return { label: "低风险", tone: "stable", note: "当前整体平稳，可维持常规关注。" };
  }
  return { label: level || "待评估", tone: "neutral", note: "监测数据积累中，暂不足以给出风险判断。" };
}

function formatMetric(value?: number | null, digits = 0) {
  if (value === null || value === undefined) return "--";
  return digits > 0 ? value.toFixed(digits) : String(Math.round(value * 10) / 10);
}

const scoreValue = computed(() => {
  const generated = props.generatedReport?.metrics?.health_score?.latest;
  if (generated !== undefined && generated !== null) return generated;
  return props.evaluation?.latest_health_score ?? props.reportSummary?.latest_health_score ?? null;
});

const activeRiskLevel = computed(
  () => props.generatedReport?.risk_level || props.evaluation?.risk_level || props.reportSummary?.risk_level || "",
);

const riskState = computed(() => normalizeRisk(activeRiskLevel.value));

const reportRecommendations = computed(() => {
  if (props.generatedReport?.recommendations?.length) return props.generatedReport.recommendations;
  return props.reportSummary?.recommendations ?? [];
});

const notableEvents = computed(() => {
  if (props.generatedReport?.key_findings?.length) return props.generatedReport.key_findings;
  return props.reportSummary?.notable_events ?? [];
});

const riskFlags = computed(() => props.generatedReport?.risk_flags ?? props.evaluation?.risk_flags ?? []);

const reportMeta = computed(() => {
  if (!props.generatedReport) return [];
  return [
    { label: "时间窗口", value: `${props.generatedReport.period.duration_minutes} 分钟` },
    { label: "样本数量", value: String(props.generatedReport.period.sample_count) },
    { label: "生成时间", value: new Date(props.generatedReport.generated_at).toLocaleString("zh-CN", { hour12: false }) },
  ];
});

const reportSummaryText = computed(() => {
  if (props.generatedReport?.summary) return props.generatedReport.summary;
  if (props.reportSummary) {
    return `已积累 ${props.reportSummary.sample_count} 条监测样本，历史评估风险等级为 ${normalizeRisk(props.reportSummary.risk_level).label}。可生成最近 24 小时报告查看最新结论。`;
  }
  if (props.evaluation) {
    return `当前风险等级为 ${normalizeRisk(props.evaluation.risk_level).label}。可生成最近 24 小时报告，查看完整结论、跟进建议与指标明细。`;
  }
  return "尚未生成健康报告。";
});

const reportCtaCopy = computed(() => {
  if (props.reportLoading) return "正在分析最近 24 小时的监测数据，请稍候。";
  if (props.generatedReport) return "报告已生成。如需查看更新后的结论，可再次生成。";
  if (props.reportSummary) return "已有历史报告，可生成新报告查看最新结论。";
  return "点击“生成报告”后，这里会展示时间范围、样本量和生成时间。";
});


const overviewCards = computed(() => [
  {
    label: "健康评分",
    value: scoreValue.value !== null && scoreValue.value !== undefined ? String(Math.round(scoreValue.value)) : "--",
    note: "综合最新监测数据评定",
    emphasis: true,
  },
  {
    label: "风险等级",
    value: riskState.value.label,
    note: riskState.value.note,
    emphasis: false,
  },
  {
    label: "样本数量",
    value: String(props.generatedReport?.period.sample_count ?? props.reportSummary?.sample_count ?? "--"),
    note: "本次报告时间范围内的监测样本数",
    emphasis: false,
  },
  {
    label: "建议动作",
    value: reportRecommendations.value.length ? String(reportRecommendations.value.length) : "--",
    note: "需要跟进执行的照护动作",
    emphasis: false,
  },
]);

const metricEntries = computed(() => {
  if (!props.generatedReport?.metrics) return [];
  return Object.entries(props.generatedReport.metrics).map(([key, value]) => {
    const config = metricLabelMap[key] ?? { label: key.replace(/_/g, " "), unit: "" };
    const digits = config.digits ?? 0;
    return {
      key,
      label: config.label,
      unit: config.unit ?? "",
      latest: formatMetric(value.latest, digits),
      average: formatMetric(value.average, digits),
      min: formatMetric(value.min, digits),
      max: formatMetric(value.max, digits),
      trend: value.trend ?? "稳定",
    };
  });
});
</script>

<template>
  <section class="panel health-evaluation-panel">
    <div class="evaluation-head">
      <div>
        <h2>健康评估与报告</h2>
        <p class="panel-subtitle">基于最近监测数据的健康评估结论与跟进建议。</p>
      </div>
      <div class="evaluation-head-meta">
        <span class="status-tag" :class="`tone-${riskState.tone}`">{{ riskState.label }}</span>
        <span class="meta-pill">{{ deviceMac || "未选择设备" }}</span>
      </div>
    </div>

    <div v-if="!isBound" class="state-block state-empty">
      <strong>当前未绑定设备</strong>
      <p>未绑定状态下仅提供基础建议。绑定设备后，这里会展示健康评分、风险等级、报告摘要和建议动作。</p>
    </div>

    <template v-else>
      <div class="evaluation-hero">
        <article class="evaluation-summary-card">
          <p class="section-eyebrow">评估总结</p>
          <h3>{{ subjectName || "待选择" }}</h3>
          <p class="report-summary">{{ reportSummaryText }}</p>
          <div class="evaluation-tags">
            <span class="meta-pill">对象 {{ subjectName || "待选择" }}</span>
            <span class="meta-pill">设备 {{ deviceMac || "未选择设备" }}</span>
            <span class="meta-pill">{{ generatedReport ? "已生成最新报告" : reportSummary ? "已有历史摘要" : "等待报告生成" }}</span>
          </div>
        </article>

        <article class="evaluation-risk-card" :class="`tone-${riskState.tone}`">
          <span>风险等级</span>
          <strong>{{ riskState.label }}</strong>
          <p>{{ riskState.note }}</p>
          <div v-if="riskFlags.length" class="evaluation-flags">
            <span v-for="flag in riskFlags" :key="flag" class="risk-pill risk-medium">{{ flag }}</span>
          </div>
        </article>
      </div>

      <div class="health-score-grid overview-grid">
        <article v-for="card in overviewCards" :key="card.label" class="score-card" :class="{ emphasis: card.emphasis }">
          <span>{{ card.label }}</span>
          <strong>{{ card.value }}</strong>
          <p>{{ card.note }}</p>
        </article>
      </div>

      <div class="evaluation-two-col">
        <article class="report-card report-card--action">
          <div class="report-head">
            <div>
              <h3>报告生成</h3>
              <p class="panel-subtitle">{{ reportCtaCopy }}</p>
            </div>
            <button type="button" class="primary-btn" :disabled="reportLoading || !deviceMac" @click="$emit('generate-report')">
              {{ reportLoading ? "生成中..." : "生成报告" }}
            </button>
          </div>
          <div v-if="reportLoading && !generatedReport" class="state-block state-loading">
            <strong>报告生成中</strong>
            <p>正在汇总最近 24 小时的体征数据、风险信号与跟进建议。</p>
          </div>
          <div v-else-if="reportMeta.length" class="meta-grid">
            <article v-for="item in reportMeta" :key="item.label" class="meta-card">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
          <div v-else class="state-block state-empty">
            <strong>还没有最新报告</strong>
            <p>点击“生成报告”后，这里会展示时间窗口、样本量和生成时间。</p>
          </div>
          <p v-if="reportError" class="feedback-banner feedback-error">{{ reportError }}</p>
        </article>

        <article class="report-card">
          <h3>建议动作</h3>
          <ul v-if="reportRecommendations.length" class="list-copy">
            <li v-for="item in reportRecommendations" :key="item">{{ item }}</li>
          </ul>
          <div v-else class="state-block state-empty">
          <strong>暂无跟进建议</strong>
          <p>生成报告后，这里会列出需要值守或家属执行的具体动作。</p>
          </div>
        </article>
      </div>

      <article class="report-card">
        <h3>关键发现</h3>
        <ul v-if="notableEvents.length" class="list-copy">
          <li v-for="item in notableEvents" :key="item">{{ item }}</li>
        </ul>
        <div v-else class="state-block state-empty">
          <strong>暂无关键发现</strong>
          <p>生成报告后，这里会提炼期间的异常、波动与恢复情况。</p>
        </div>
      </article>

      <article class="report-card">
        <div class="report-head">
          <div>
            <h3>指标摘要</h3>
            <p class="panel-subtitle">各项指标的最新值、均值与波动区间。</p>
          </div>
        </div>
        <div v-if="metricEntries.length" class="metric-report-grid">
          <article v-for="item in metricEntries" :key="item.key" class="metric-report-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.latest }}<small v-if="item.unit">{{ item.unit }}</small></strong>
            <p>均值 {{ item.average }}{{ item.unit }}</p>
            <p>最低 {{ item.min }}{{ item.unit }} / 最高 {{ item.max }}{{ item.unit }}</p>
            <p>趋势 {{ item.trend }}</p>
          </article>
        </div>
        <div v-else class="state-block state-empty">
          <strong>暂无指标明细</strong>
          <p>生成报告后，这里会显示各项体征指标的统计结果。</p>
        </div>
      </article>
    </template>
  </section>
</template>

<style scoped>
.health-evaluation-panel,
.evaluation-hero,
.evaluation-two-col,
.overview-grid,
.metric-report-grid {
  display: grid;
  gap: 14px;
}

.evaluation-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.evaluation-head-meta,
.evaluation-tags,
.evaluation-flags,
.meta-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.evaluation-hero {
  grid-template-columns: minmax(0, 1.35fr) 280px;
}

.overview-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.evaluation-summary-card,
.evaluation-risk-card,
.score-card,
.report-card,
.meta-card,
.metric-report-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  padding: 16px 18px;
}

.evaluation-summary-card,
.report-card {
  display: grid;
  gap: 14px;
}

.evaluation-summary-card h3 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 1.34rem;
  letter-spacing: -0.03em;
}

.evaluation-risk-card {
  display: grid;
  align-content: flex-start;
  gap: 10px;
}

.evaluation-risk-card span {
  color: var(--text-sub);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.evaluation-risk-card strong {
  font-size: 2rem;
  line-height: 1.06;
}

.evaluation-risk-card p,
.score-card p,
.metric-report-card p,
.report-summary {
  margin: 0;
  color: var(--text-sub);
  line-height: 1.76;
}

.evaluation-risk-card.tone-critical {
  border-color: color-mix(in srgb, var(--risk-high) 40%, transparent);
  background: var(--surface-danger);
}

.evaluation-risk-card.tone-critical strong {
  color: var(--risk-high);
}

.evaluation-risk-card.tone-warning {
  border-color: color-mix(in srgb, var(--risk-medium) 40%, transparent);
  background: var(--surface-warning);
}

.evaluation-risk-card.tone-warning strong {
  color: var(--risk-medium);
}

.evaluation-risk-card.tone-stable {
  border-color: color-mix(in srgb, var(--risk-low) 35%, transparent);
  background: var(--surface-success);
}

.evaluation-risk-card.tone-stable strong {
  color: var(--risk-low);
}

.score-card {
  display: grid;
  gap: 10px;
}

.score-card span,
.meta-card span,
.metric-report-card span {
  color: var(--text-sub);
  font-size: 0.8rem;
  font-weight: 700;
}

.score-card strong,
.meta-card strong,
.metric-report-card strong {
  display: block;
  color: var(--text-main);
  font-size: 1.55rem;
  line-height: 1.1;
}

.score-card.emphasis {
  border-color: color-mix(in srgb, var(--brand) 40%, transparent);
  background: var(--surface-cyan);
}

.score-card.emphasis strong {
  color: var(--brand);
}

.report-head {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.report-head .primary-btn {
  flex-shrink: 0;
  white-space: nowrap;
}

.report-card h3 {
  margin: 0;
}

.meta-grid {
  margin-top: 2px;
}

.meta-card {
  min-width: 160px;
}

.metric-report-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.metric-report-card small {
  font-size: 0.84rem;
  color: var(--text-muted);
}

@media (max-width: 1100px) {
  .evaluation-hero,
  .evaluation-two-col,
  .overview-grid,
  .metric-report-grid {
    grid-template-columns: 1fr;
  }

  .report-head,
  .evaluation-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
