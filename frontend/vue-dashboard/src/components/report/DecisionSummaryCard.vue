<script setup lang="ts">
import { computed } from "vue";

type SummaryMetric = {
  label: string;
  value: string;
  note: string;
};

type SummaryStatus = "stable" | "attention" | "high";

const props = defineProps<{
  title: string;
  summaryLine: string;
  spokenConclusion: string;
  generatedAt: string;
  status: SummaryStatus;
  urgentMatters: string[];
  metrics: SummaryMetric[];
}>();

function statusCopy(status: SummaryStatus) {
  if (status === "high") {
    return { badge: "高风险", headline: "当前交接优先处理高风险对象与异常链路" };
  }
  if (status === "attention") {
    return { badge: "注意", headline: "整体可控，但需要跟进重点对象与告警波动" };
  }
  return { badge: "稳定", headline: "整体运行平稳，按常规巡检与观察节奏推进" };
}

const statusMeta = computed(() => statusCopy(props.status));
</script>

<template>
  <section class="decision-summary-card" :data-status="status">
    <div class="decision-summary-card__surface">
      <div class="decision-summary-card__header">
        <div>
          <p class="decision-summary-card__eyebrow">Shift Command Brief</p>
          <h2>{{ title }}</h2>
          <p class="decision-summary-card__headline">{{ statusMeta.headline }}</p>
        </div>
        <div class="decision-summary-card__status">
          <span class="decision-summary-card__badge">{{ statusMeta.badge }}</span>
          <small>生成于 {{ generatedAt }}</small>
        </div>
      </div>

      <div class="decision-summary-card__grid">
        <div class="decision-summary-card__summary">
          <p class="decision-summary-card__label">一句话结论</p>
          <strong>{{ spokenConclusion }}</strong>
          <p>{{ summaryLine }}</p>
        </div>

        <div class="decision-summary-card__metrics">
          <article v-for="item in metrics" :key="item.label" class="decision-metric">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.note }}</small>
          </article>
        </div>
      </div>

      <div class="decision-summary-card__urgent">
        <p class="decision-summary-card__label">当前最紧急事项</p>
        <ol>
          <li v-for="item in urgentMatters" :key="item">{{ item }}</li>
        </ol>
      </div>
    </div>
  </section>
</template>

<style scoped>
.decision-summary-card {
  position: relative;
  overflow: hidden;
  border-radius: var(--radius-lg);
  background: var(--panel-strong);
  border: 1px solid var(--line);
  border-top: 3px solid var(--brand);
  color: var(--text-main);
  box-shadow: var(--shadow);
}

.decision-summary-card[data-status="high"] {
  border-top-color: var(--risk-high);
}

.decision-summary-card[data-status="attention"] {
  border-top-color: var(--risk-medium);
}

.decision-summary-card__surface,
.decision-summary-card__grid,
.decision-summary-card__metrics {
  display: grid;
  gap: 20px;
}

.decision-summary-card__surface {
  padding: clamp(22px, 3vw, 30px);
}

.decision-summary-card__header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-start;
}

.decision-summary-card__eyebrow,
.decision-summary-card__label {
  margin: 0 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  font-size: 0.7rem;
  font-weight: 800;
  color: var(--brand);
}

.decision-summary-card h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: clamp(1.5rem, 2.4vw, 2rem);
  letter-spacing: -0.03em;
  color: var(--text-main);
}

.decision-summary-card__headline {
  margin: 8px 0 0;
  color: var(--text-sub);
  font-size: 0.94rem;
  line-height: 1.7;
}

.decision-summary-card__status {
  display: grid;
  justify-items: end;
  gap: 8px;
  text-align: right;
}

.decision-summary-card__badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: var(--surface-cyan);
  color: var(--brand);
  font-size: 0.9rem;
  font-weight: 800;
}

.decision-summary-card[data-status="high"] .decision-summary-card__badge {
  background: var(--surface-danger);
  border-color: color-mix(in srgb, var(--risk-high) 40%, transparent);
  color: var(--risk-high);
}

.decision-summary-card[data-status="attention"] .decision-summary-card__badge {
  background: var(--surface-warning);
  border-color: color-mix(in srgb, var(--risk-medium) 40%, transparent);
  color: var(--risk-medium);
}

.decision-summary-card__status small {
  color: var(--text-muted);
}

.decision-summary-card__grid {
  grid-template-columns: minmax(0, 1.25fr) minmax(340px, 0.95fr);
  align-items: start;
}

.decision-summary-card__summary strong {
  display: block;
  margin-bottom: 10px;
  font-size: clamp(1.02rem, 1.6vw, 1.3rem);
  line-height: 1.55;
  letter-spacing: -0.02em;
  color: var(--text-main);
}

.decision-summary-card__summary p:last-child {
  margin: 0;
  color: var(--text-sub);
  line-height: 1.75;
}

.decision-summary-card__metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.decision-metric {
  display: grid;
  gap: 7px;
  padding: 15px 16px;
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  border: 1px solid var(--line);
}

.decision-metric span,
.decision-metric small {
  color: var(--text-muted);
  font-size: 0.76rem;
}

.decision-metric strong {
  font-family: var(--font-mono);
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--text-main);
}

.decision-summary-card__urgent {
  padding-top: 8px;
  border-top: 1px solid var(--line);
}

.decision-summary-card__urgent ol {
  margin: 0;
  padding-left: 22px;
  display: grid;
  gap: 9px;
  line-height: 1.7;
  color: var(--text-sub);
}

@media (max-width: 1080px) {
  .decision-summary-card__grid {
    grid-template-columns: 1fr;
  }

  .decision-summary-card__metrics {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .decision-summary-card__header {
    flex-direction: column;
  }

  .decision-summary-card__status {
    justify-items: start;
    text-align: left;
  }
}
</style>
