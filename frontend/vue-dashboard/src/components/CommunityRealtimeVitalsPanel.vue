<script setup lang="ts">
import { LineChart, type LineSeriesOption } from "echarts/charts";
import {
  GraphicComponent,
  GridComponent,
  LegendComponent,
  TooltipComponent,
  type GraphicComponentOption,
  type GridComponentOption,
  type LegendComponentOption,
  type TooltipComponentOption,
} from "echarts/components";
import { type ComposeOption, init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { CommunityDashboardDeviceItem, CommunityDashboardElderItem, HealthSample } from "../api/client";
import BulletBar from "./viz/BulletBar.vue";
import { riskLevelToChinese } from "../utils/riskLevel";

use([CanvasRenderer, GraphicComponent, GridComponent, LegendComponent, LineChart, TooltipComponent]);

type RealtimeOption = ComposeOption<
  GridComponentOption | LegendComponentOption | TooltipComponentOption | GraphicComponentOption | LineSeriesOption
>;

const props = defineProps<{
  elder: CommunityDashboardElderItem | null;
  device: CommunityDashboardDeviceItem | null;
  samples: HealthSample[];
  currentSample?: HealthSample | null;
  awaitingRealtime?: boolean;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

function parseBloodPressure(value?: string | null) {
  if (!value) return { sbp: null, dbp: null };
  const [sbpRaw, dbpRaw] = value.split("/", 2);
  const sbp = Number.parseInt(sbpRaw ?? "", 10);
  const dbp = Number.parseInt(dbpRaw ?? "", 10);
  return {
    sbp: Number.isFinite(sbp) ? sbp : null,
    dbp: Number.isFinite(dbp) ? dbp : null,
  };
}

function hasNumericValue(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

const hasSamples = computed(() => props.samples.length > 0);
const isNoDevice = computed(() => Boolean(props.elder) && !props.elder?.device_mac);
const isPending = computed(() => props.device?.device_status === "pending");
const isOffline = computed(() => props.device?.device_status === "offline");
const isAwaitingRealtime = computed(() => !!props.awaitingRealtime && props.device?.ingest_mode === "serial");
const structuredSummary = computed(() => props.device?.structured_health ?? props.elder?.structured_health ?? null);

const tagGlossary: Record<string, string> = {
  hypertension: "血压偏高",
  hypotension: "血压偏低",
  fever: "体温异常",
  low_spo2: "血氧偏低",
  tachycardia: "心率偏高",
  bradycardia: "心率偏低",
  arrhythmia: "心律不齐",
  fall_detected: "跌倒风险"
};
const localizeTag = (tag: string) => tagGlossary[tag.toLowerCase()] || tag;

const structuredTags = computed(() => structuredSummary.value?.abnormal_tags ?? []);
const currentSample = computed(() => props.currentSample ?? props.samples[props.samples.length - 1] ?? null);
const hasObservedRealtime = computed(() =>
  Boolean(
    currentSample.value
      || hasSamples.value
      || props.device?.latest_timestamp
      || hasNumericValue(props.device?.heart_rate)
      || hasNumericValue(props.device?.blood_oxygen)
      || hasNumericValue(props.device?.temperature)
      || hasNumericValue(props.device?.steps)
      || props.device?.blood_pressure,
  ),
);
const showPendingPlaceholder = computed(() => isPending.value && !hasObservedRealtime.value);
const currentPressure = computed(() => parseBloodPressure(currentSample.value?.blood_pressure));
const showPointSymbols = computed(() => props.samples.length <= 2);

const isLive = computed(
  () => hasSamples.value && !isOffline.value && !isNoDevice.value && !showPendingPlaceholder.value,
);

/* 迷你趋势线：取最近 24 个采样点归一化为 120x24 折线 */
function sparkPoints(values: Array<number | null | undefined>): string {
  const points = values
    .slice(-24)
    .filter((value): value is number => typeof value === "number" && Number.isFinite(value));
  if (points.length < 2) return "";
  const min = Math.min(...points);
  const max = Math.max(...points);
  const span = max - min || 1;
  return points
    .map((value, index) => {
      const x = (index / (points.length - 1)) * 120;
      const y = 21 - ((value - min) / span) * 18;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
}

const chartSeries = computed(() => {
  const labels = props.samples.map((sample) =>
    new Date(sample.timestamp).toLocaleTimeString("zh-CN", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }),
  );
  const pressure = props.samples.map((sample) => parseBloodPressure(sample.blood_pressure));
  return {
    labels,
    heartRate: props.samples.map((sample) => sample.heart_rate),
    spo2: props.samples.map((sample) => sample.blood_oxygen),
    sbp: pressure.map((item) => item.sbp),
    dbp: pressure.map((item) => item.dbp),
    temperature: props.samples.map((sample) => sample.temperature),
  };
});

const temperatureAxisRange = computed(() => {
  const values = chartSeries.value.temperature.filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
  if (!values.length) {
    return { min: 34, max: 42 };
  }
  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const min = Math.max(20, Math.floor(minValue) - 1);
  const max = Math.min(45, Math.max(min + 4, Math.ceil(maxValue) + 1));
  return { min, max };
});

const metricCards = computed(() => {
  const sample = currentSample.value;
  const heartRate = sample?.heart_rate ?? null;
  const spo2 = sample?.blood_oxygen ?? null;
  const temperature = sample?.temperature ?? null;
  const steps = sample?.steps ?? null;
  const { sbp, dbp } = currentPressure.value;

  return [
    {
      key: "hr",
      label: "心率 HR",
      value: heartRate != null ? `${heartRate}` : "--",
      unit: "bpm",
      range: "参考 60–100",
      warn: heartRate != null && (heartRate > 110 || heartRate < 45),
      spark: sparkPoints(chartSeries.value.heartRate),
      bullet: { value: heartRate, low: 60, high: 100, unit: "" },
    },
    {
      key: "spo2",
      label: "血氧 SpO₂",
      value: spo2 != null ? `${spo2}` : "--",
      unit: "%",
      range: "参考 ≥ 94",
      warn: spo2 != null && spo2 < 93,
      spark: sparkPoints(chartSeries.value.spo2),
      bullet: { value: spo2, low: 94, high: 100, unit: "%", upperOpen: true, min: 88, max: 100 },
    },
    {
      key: "bp",
      label: "血压 BP",
      value: sbp !== null && dbp !== null ? `${sbp}/${dbp}` : "--",
      unit: "mmHg",
      range: "参考 < 140/90",
      warn: sbp !== null && sbp >= 140,
      spark: sparkPoints(chartSeries.value.sbp),
      bullet: { value: sbp, low: 90, high: 140, unit: "", min: 80, max: 170 },
    },
    {
      key: "temp",
      label: "体温 TEMP",
      value: temperature != null ? temperature.toFixed(1) : "--",
      unit: "°C",
      range: "参考 36.0–37.2",
      warn: temperature != null && temperature >= 37.8,
      spark: sparkPoints(chartSeries.value.temperature),
      bullet: { value: temperature, low: 36, high: 37.2, unit: "°C", min: 35.4, max: 38.4 },
    },
    {
      key: "steps",
      label: "步数 STEPS",
      value: steps != null ? `${steps}` : "--",
      unit: "步",
      range: "今日累计",
      warn: false,
      spark: "",
      bullet: null,
    },
  ];
});

const scoreText = computed(() => structuredSummary.value?.health_score?.toFixed(1) ?? props.device?.latest_health_score ?? "--");

const panelMeta = computed(() => {
  if (!props.elder) {
    return {
      title: "请选择老人",
      subtitle: "先从上方老人卡片中选中一位监护对象，再查看设备绑定状态和实时数据。",
      badge: "未选择",
    };
  }

  if (isNoDevice.value) {
    return {
      title: props.elder.elder_name,
      subtitle: `${props.elder.apartment} · 当前无设备，需要先在移动端为这位老人绑定手环。`,
      badge: "无设备",
    };
  }

  if (isOffline.value) {
    return {
      title: props.elder.elder_name,
      subtitle: `${props.device?.device_name ?? "T10-WATCH"} · ${props.elder.device_mac} · 设备当前离线，暂时没有新的实时曲线。`,
      badge: "离线",
    };
  }

  if (showPendingPlaceholder.value) {
    return {
      title: props.elder.elder_name,
      subtitle: `${props.device?.device_name ?? "T10-WATCH"} · ${props.elder.device_mac} · 已绑定，等待首个实时包进入。`,
      badge: "待同步",
    };
  }

  if (isAwaitingRealtime.value) {
    return {
      title: props.elder.elder_name,
      subtitle: `${props.device?.device_name ?? "T10-WATCH"} · ${props.elder.device_mac} · 正在切换采集目标，等待新的串口样本。`,
      badge: "接入中",
    };
  }

  return {
    title: props.elder.elder_name,
    subtitle: `${props.device?.device_name ?? "T10-WATCH"} · ${props.elder.device_mac} · ${props.elder.apartment}`,
    badge: riskLevelToChinese(structuredSummary.value?.risk_level ?? props.elder.risk_level),
  };
});

const fallbackTag = computed(() => {
  if (isNoDevice.value) return "当前无设备";
  if (isOffline.value) return "设备离线";
  if (showPendingPlaceholder.value) return "等待首包";
  if (isAwaitingRealtime.value) return "等待新串口样本";
  return "当前没有持续异常标签";
});

const noteText = computed(() => {
  if (structuredSummary.value?.trigger_reasons?.[0]) {
    return structuredSummary.value.trigger_reasons[0];
  }
  if (isNoDevice.value) {
    return "先在移动端为这位老人绑定手环，绑定完成后回到这里点击对应老人即可查看实时曲线。";
  }
  if (isOffline.value) {
    return "这位老人已有设备，但当前处于离线状态，需要先恢复设备连接后才会继续更新。";
  }
  if (showPendingPlaceholder.value) {
    return "设备已绑定，收到首条体征数据后会自动显示实时曲线。";
  }
  if (isAwaitingRealtime.value) {
    return "当前正在切换采集目标，新的串口样本到达后，这里会立刻刷新。";
  }
  return "收到实时数据后会持续更新曲线，没有新数据时会保留上一条有效数据。";
});

const emptyTitle = computed(() => {
  if (!props.elder) return "请选择老人";
  if (isNoDevice.value) return "当前无设备";
  if (isOffline.value) return "设备离线";
  if (showPendingPlaceholder.value) return "等待实时数据";
  if (isAwaitingRealtime.value) return "正在接入实时数据";
  return "暂未收到实时数据";
});

const emptyDescription = computed(() => {
  if (!props.elder) return "先从上方老人卡片中选择一位监护对象。";
  if (isNoDevice.value) return "这位老人还没有绑定手环，所以这里不会显示实时曲线。";
  if (isOffline.value) return "设备恢复在线后，这里会继续展示最新曲线。";
  if (showPendingPlaceholder.value) return "已绑定设备，等待首个实时样本进入。";
  if (isAwaitingRealtime.value) return "串口采集目标已经切换，新包到达后就会开始绘制。";
  if (hasObservedRealtime.value) return "已有最近样本，等待更多数据点后就会继续拉出曲线。";
  return "等待下一次采样进入。";
});

function buildChartOption(): RealtimeOption {
  return {
    backgroundColor: "transparent",
    animation: false,
    animationDuration: 0,
    animationDurationUpdate: 0,
    legend: {
      top: 8,
      left: 10,
      itemWidth: 18,
      itemHeight: 8,
      textStyle: { color: "#4c5e70", fontSize: 13, fontWeight: 600 },
    },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255, 255, 255, 0.98)",
      borderColor: "rgba(22, 33, 46, 0.12)",
      textStyle: { color: "#16212e" },
      extraCssText: "border-radius: 8px; box-shadow: 0 4px 16px rgba(22, 33, 46, 0.08);",
    },
    grid: [
      { left: "5%", top: 58, width: "41%", height: "29%" },
      { left: "55%", top: 58, width: "40%", height: "29%" },
      { left: "5%", top: "58%", width: "41%", height: "29%" },
      { left: "55%", top: "58%", width: "40%", height: "29%" },
    ],
    xAxis: Array.from({ length: 4 }, (_, index) => ({
      type: "category",
      gridIndex: index,
      boundaryGap: false,
      data: chartSeries.value.labels,
      axisLabel: { color: "#64748b", fontSize: 12, margin: 12 },
      axisLine: { lineStyle: { color: "rgba(15, 23, 42, 0.1)" } },
    })),
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        min: 40,
        max: 180,
        splitLine: { lineStyle: { color: "rgba(15, 23, 42, 0.06)", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 1,
        min: 80,
        max: 100,
        splitLine: { lineStyle: { color: "rgba(15, 23, 42, 0.06)", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 2,
        min: 40,
        max: 200,
        splitLine: { lineStyle: { color: "rgba(15, 23, 42, 0.06)", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 12 },
      },
      {
        type: "value",
        gridIndex: 3,
        min: temperatureAxisRange.value.min,
        max: temperatureAxisRange.value.max,
        splitLine: { lineStyle: { color: "rgba(15, 23, 42, 0.06)", type: "dashed" } },
        axisLabel: { color: "#64748b", fontSize: 12 },
      },
    ],
    series: [
      {
        name: "心率",
        type: "line",
        xAxisIndex: 0,
        yAxisIndex: 0,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.heartRate,
        lineStyle: { width: 3, color: "#c53030" },
        areaStyle: { color: "rgba(197, 48, 48, 0.08)" },
      },
      {
        name: "血氧",
        type: "line",
        xAxisIndex: 1,
        yAxisIndex: 1,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.spo2,
        lineStyle: { width: 3, color: "#0e7490" },
        areaStyle: { color: "rgba(14, 116, 144, 0.10)" },
      },
      {
        name: "收缩压",
        type: "line",
        xAxisIndex: 2,
        yAxisIndex: 2,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.sbp,
        lineStyle: { width: 2.5, color: "#6366f1" },
      },
      {
        name: "舒张压",
        type: "line",
        xAxisIndex: 2,
        yAxisIndex: 2,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.dbp,
        lineStyle: { width: 2.5, color: "#a5b4fc" },
      },
      {
        name: "体温",
        type: "line",
        xAxisIndex: 3,
        yAxisIndex: 3,
        smooth: true,
        showSymbol: showPointSymbols.value,
        symbolSize: showPointSymbols.value ? 8 : 0,
        connectNulls: true,
        data: chartSeries.value.temperature,
        lineStyle: { width: 3, color: "#c2620a" },
        areaStyle: { color: "rgba(194, 98, 10, 0.08)" },
      },
    ],
    graphic: [
      { type: "text", left: "23%", top: 30, style: { text: "心率", fill: "rgba(22, 33, 46, 0.06)", fontWeight: 800, fontSize: 46, align: "center" } },
      { type: "text", left: "73%", top: 30, style: { text: "血氧", fill: "rgba(22, 33, 46, 0.06)", fontWeight: 800, fontSize: 46, align: "center" } },
      { type: "text", left: "23%", top: "54%", style: { text: "血压", fill: "rgba(22, 33, 46, 0.06)", fontWeight: 800, fontSize: 46, align: "center" } },
      { type: "text", left: "73%", top: "54%", style: { text: "体温", fill: "rgba(22, 33, 46, 0.06)", fontWeight: 800, fontSize: 46, align: "center" } },
    ],
  };
}

function updateChart() {
  if (!chartRef.value) return;
  chart ??= init(chartRef.value);
  chart.setOption(buildChartOption(), { notMerge: false });
}

function handleResize() {
  chart?.resize();
}

onMounted(() => {
  updateChart();
  window.addEventListener("resize", handleResize);
});

watch(() => [props.samples.length, props.device?.device_status, props.device?.ingest_mode], updateChart);
watch([chartSeries, showPointSymbols, temperatureAxisRange], updateChart);

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <section class="panel realtime-monitor-panel">
    <p class="section-eyebrow">实时监护视图</p>

    <div class="monitor-hero">
      <span class="monitor-avatar" :class="{ 'monitor-avatar--dim': isOffline || isNoDevice || !elder }">
        {{ elder?.elder_name?.slice(0, 1) ?? "—" }}
        <i v-if="isLive" class="monitor-avatar__dot"></i>
      </span>
      <div class="monitor-id">
        <h2>{{ panelMeta.title }}<template v-if="elder?.apartment"> · {{ elder.apartment }}</template></h2>
        <p class="monitor-subtitle">{{ panelMeta.subtitle }}</p>
      </div>
      <div class="monitor-badges">
        <span v-if="isLive" class="live-chip"><i></i>实时采集中</span>
        <span v-else class="monitor-badge">{{ panelMeta.badge }}</span>
        <span class="monitor-badge subtle">模型评分 {{ scoreText }}</span>
      </div>
    </div>

    <div class="monitor-chart-shell">
      <div class="monitor-chart-cap">
        <span>实时曲线 · 心率 / 血氧 / 血压 / 体温</span>
        <span>按采样时间滚动更新</span>
      </div>
      <div class="monitor-chart-box">
        <div ref="chartRef" class="monitor-chart"></div>
        <div v-if="!hasSamples" class="monitor-empty">
          <strong>{{ emptyTitle }}</strong>
          <p>{{ emptyDescription }}</p>
        </div>
      </div>
    </div>

    <div class="monitor-metrics">
      <article
        v-for="item in metricCards"
        :key="item.key"
        class="metric-plate"
        :class="{ 'metric-plate--warn': item.warn }"
      >
        <span class="metric-plate__label">{{ item.label }}</span>
        <strong class="metric-plate__value">{{ item.value }}<small>{{ item.unit }}</small></strong>
        <BulletBar
          v-if="item.bullet"
          :value="item.bullet.value"
          :low="item.bullet.low"
          :high="item.bullet.high"
          :min="item.bullet.min"
          :max="item.bullet.max"
          :unit="item.bullet.unit"
          :upper-open="item.bullet.upperOpen ?? false"
        />
        <span v-else class="metric-plate__range">{{ item.range }}</span>
        <svg v-if="item.spark" class="metric-plate__spark" viewBox="0 0 120 24" preserveAspectRatio="none">
          <polyline pathLength="1" :points="item.spark" />
        </svg>
      </article>
    </div>

    <div class="monitor-context">
      <div class="monitor-chip-row">
        <span v-for="tag in structuredTags" :key="tag" class="signal-chip">{{ localizeTag(tag) }}</span>
        <span v-if="!structuredTags.length" class="signal-chip muted">{{ fallbackTag }}</span>
      </div>
      <p class="monitor-note">{{ noteText }}</p>
    </div>
  </section>
</template>

<style scoped>
.realtime-monitor-panel {
  display: grid;
  width: 100%;
  gap: 14px;
  background: var(--panel-strong);
}

.monitor-hero,
.monitor-badges,
.monitor-chip-row {
  display: flex;
  gap: 12px;
}

.monitor-hero {
  align-items: center;
}

.monitor-avatar {
  position: relative;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, #0e7490, #0891b2);
  color: #ffffff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 0 2px var(--panel-strong), 0 0 0 4px var(--risk-low);
}

.monitor-avatar--dim {
  filter: grayscale(0.6);
  opacity: 0.8;
  box-shadow: 0 0 0 2px var(--panel-strong), 0 0 0 4px var(--surface-2);
}

.monitor-avatar__dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--risk-low);
  border: 2px solid var(--panel-strong);
  animation: monitor-pulse 2.2s infinite;
}

@keyframes monitor-pulse {
  0%   { box-shadow: 0 0 0 0 var(--surface-success); }
  70%  { box-shadow: 0 0 0 7px transparent; }
  100% { box-shadow: 0 0 0 0 transparent; }
}

.monitor-id {
  flex: 1;
  min-width: 0;
}

.monitor-hero h2 {
  margin: 0;
  font-family: var(--font-display);
  font-size: 21.5px;
  font-weight: 700;
  color: var(--text-main);
}

.monitor-subtitle {
  margin: 3px 0 0;
  color: var(--text-muted);
  line-height: 1.55;
  font-size: 13.5px;
  font-family: var(--font-mono);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.monitor-badges {
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  flex-shrink: 0;
}

.live-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--risk-low);
  background: var(--surface-success);
  padding: 5px 12px;
  border-radius: 999px;
  white-space: nowrap;
}

.live-chip i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--risk-low);
  animation: monitor-pulse 1.8s infinite;
}

.monitor-badge {
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--panel-tinted);
  color: var(--text-sub);
  border: 1px solid var(--line);
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.monitor-badge.subtle {
  color: var(--text-muted);
}

/* 图表容器 */
.monitor-chart-shell {
  width: 100%;
  min-width: 0;
}

.monitor-chart-cap {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 12.5px;
  color: var(--text-muted);
  padding: 0 2px 7px;
}

.monitor-chart-box {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  overflow: hidden;
}

.monitor-chart {
  height: min(52vh, 480px);
  min-height: 380px;
  width: 100%;
  display: block;
}

.monitor-empty {
  position: absolute;
  inset: 0;
  display: grid;
  place-content: center;
  gap: 8px;
  padding: 24px;
  text-align: center;
  background: color-mix(in srgb, var(--panel-tinted) 92%, transparent);
}

.monitor-empty strong {
  color: var(--text-main);
  font-size: 18px;
}

.monitor-empty p {
  margin: 0;
  color: var(--text-sub);
  line-height: 1.65;
  font-size: 14px;
  max-width: 460px;
}

/* 体征卡 */
.monitor-metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px;
}

.metric-plate {
  min-width: 0;
  padding: 12px 14px 10px;
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  border: 1px solid var(--line);
  display: grid;
  gap: 3px;
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.metric-plate:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.metric-plate__label {
  color: var(--text-muted);
  font-size: 12.5px;
}

.metric-plate__value {
  color: var(--text-main);
  font-family: var(--font-mono);
  font-size: 24.5px;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.01em;
}

.metric-plate__value small {
  font-size: 12.5px;
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 3px;
}

.metric-plate__range {
  color: var(--text-muted);
  font-size: 11px;
}

.metric-plate__spark {
  width: 100%;
  height: 22px;
  margin-top: 4px;
}

.metric-plate__spark polyline {
  fill: none;
  stroke: var(--brand-2);
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-dasharray: 1;
  animation: plate-spark-draw 700ms var(--ease-enter, cubic-bezier(0.22, 0.8, 0.3, 1)) both;
}

@keyframes plate-spark-draw {
  from { stroke-dashoffset: 1; }
  to { stroke-dashoffset: 0; }
}

.metric-plate--warn .metric-plate__value {
  color: var(--risk-medium);
}

.metric-plate--warn {
  border-color: color-mix(in srgb, var(--risk-medium) 45%, transparent);
  background: var(--surface-warning);
}

.metric-plate--warn .metric-plate__spark polyline {
  stroke: var(--risk-medium);
}

.monitor-context {
  display: grid;
  gap: 8px;
}

.monitor-note {
  margin: 0;
  color: var(--text-sub);
  line-height: 1.6;
  font-size: 14px;
}

.monitor-chip-row {
  flex-wrap: wrap;
}

.signal-chip {
  padding: 5px 12px;
  border-radius: 999px;
  background: var(--surface-danger);
  color: var(--risk-high);
  border: 1px solid color-mix(in srgb, var(--risk-high) 30%, transparent);
  font-size: 13px;
  font-weight: 600;
}

.signal-chip.muted {
  background: var(--panel-tinted);
  color: var(--text-muted);
  border: 1px solid var(--line);
}

@media (max-width: 960px) {
  .monitor-hero {
    flex-wrap: wrap;
  }

  .monitor-badges {
    justify-content: flex-start;
  }

  .monitor-chart {
    min-height: 340px;
    height: 52vh;
  }
}
</style>
