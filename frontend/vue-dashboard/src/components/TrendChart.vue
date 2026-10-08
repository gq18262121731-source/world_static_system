<script setup lang="ts">
import { BarChart, LineChart } from "echarts/charts";
import {
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  type DataZoomComponentOption,
  type GridComponentOption,
  type LegendComponentOption,
  type TooltipComponentOption,
} from "echarts/components";
import { type BarSeriesOption, type LineSeriesOption } from "echarts/charts";
import { type ComposeOption, init, use, type ECharts } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import type { HealthSample } from "../api/client";

use([
  BarChart,
  CanvasRenderer,
  DataZoomComponent,
  GridComponent,
  LegendComponent,
  LineChart,
  MarkLineComponent,
  TooltipComponent,
]);

type TrendChartOption = ComposeOption<
  | BarSeriesOption
  | LineSeriesOption
  | DataZoomComponentOption
  | GridComponentOption
  | LegendComponentOption
  | TooltipComponentOption
>;

const props = defineProps<{
  deviceMac: string;
  samples: HealthSample[];
  windowMinutes: number;
}>();

const emit = defineEmits<{
  (event: "change-window", minutes: number): void;
}>();

const chartRef = ref<HTMLDivElement | null>(null);
let chart: ECharts | null = null;

const trendMetrics = computed(() => {
  const first = props.samples[0];
  const last = props.samples[props.samples.length - 1];

  if (!first || !last) {
    return [
      { label: "心率变化", value: "--" },
      { label: "血氧变化", value: "--" },
      { label: "体温变化", value: "--" },
    ];
  }

  return [
    {
      label: "心率变化",
      value: `${last.heart_rate - first.heart_rate >= 0 ? "+" : ""}${last.heart_rate - first.heart_rate} bpm`,
    },
    {
      label: "血氧变化",
      value: `${last.blood_oxygen - first.blood_oxygen >= 0 ? "+" : ""}${last.blood_oxygen - first.blood_oxygen}%`,
    },
    {
      label: "体温变化",
      value: `${last.temperature - first.temperature >= 0 ? "+" : ""}${(last.temperature - first.temperature).toFixed(1)}°C`,
    },
  ];
});

function renderChart() {
  if (!chartRef.value) return;

  chart ??= init(chartRef.value);

  const option: TrendChartOption = {
    backgroundColor: "transparent",
    animationDuration: 600,
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(22, 33, 46, 0.95)",
      borderColor: "rgba(8, 145, 178, 0.30)",
      textStyle: { color: "#eaf3f6" },
    },
    legend: {
      top: 4,
      textStyle: { color: "#4c5e70" },
    },
    grid: { left: 42, right: 72, top: 52, bottom: 42 },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: props.samples.map((sample) =>
        new Date(sample.timestamp).toLocaleTimeString("zh-CN", {
          hour12: false,
          hour: "2-digit",
          minute: "2-digit",
        }),
      ),
      axisLine: { lineStyle: { color: "rgba(22, 33, 46, 0.18)" } },
      axisLabel: { color: "#8595a7" },
    },
    yAxis: [
      {
        type: "value",
        name: "心率",
        min: 40,
        max: 180,
        axisLabel: { color: "#8595a7" },
        splitLine: { lineStyle: { color: "rgba(22, 33, 46, 0.08)" } },
      },
      {
        type: "value",
        name: "体温",
        min: 34,
        max: 42,
        position: "right",
        axisLabel: { color: "#8595a7" },
      },
      {
        type: "value",
        name: "血氧 / 评分",
        min: 0,
        max: 100,
        position: "right",
        offset: 54,
        axisLabel: { color: "#8595a7" },
      },
    ],
    dataZoom: [
      { type: "inside" },
      {
        type: "slider",
        height: 18,
        bottom: 10,
        borderColor: "transparent",
        backgroundColor: "rgba(14, 116, 144, 0.08)",
        fillerColor: "rgba(8, 145, 178, 0.16)",
      },
    ],
    series: [
      {
        name: "心率",
        type: "line",
        smooth: true,
        symbol: "none",
        data: props.samples.map((sample) => sample.heart_rate),
        lineStyle: { width: 3, color: "#0e7490" },
        areaStyle: { color: "rgba(14, 116, 144, 0.12)" },
        markLine: {
          symbol: "none",
          lineStyle: { color: "rgba(194, 98, 10, 0.5)" },
          data: [{ yAxis: 110, label: { formatter: "关注阈值" } }],
        },
      },
      {
        name: "体温",
        type: "line",
        smooth: true,
        yAxisIndex: 1,
        symbol: "none",
        data: props.samples.map((sample) => sample.temperature),
        lineStyle: { width: 3, color: "#c2620a" },
        areaStyle: { color: "rgba(194, 98, 10, 0.10)" },
      },
      {
        name: "血氧",
        type: "line",
        smooth: true,
        yAxisIndex: 2,
        symbol: "none",
        data: props.samples.map((sample) => sample.blood_oxygen),
        lineStyle: { width: 2, color: "#0d9463" },
      },
      {
        name: "健康评分",
        type: "bar",
        yAxisIndex: 2,
        barMaxWidth: 10,
        data: props.samples.map((sample) => sample.health_score ?? 0),
        itemStyle: { color: "rgba(13, 148, 99, 0.35)", borderRadius: [10, 10, 0, 0] },
      },
    ],
  };

  chart.setOption(option, { notMerge: true });
  chart.resize();
}

function handleResize() {
  chart?.resize();
}

onMounted(() => {
  renderChart();
  window.addEventListener("resize", handleResize);
});

watch(() => props.samples, renderChart, { deep: true });
watch(() => props.windowMinutes, renderChart);

onUnmounted(() => {
  window.removeEventListener("resize", handleResize);
  chart?.dispose();
});
</script>

<template>
  <section class="panel trend-panel">
    <div class="panel-head">
      <div>
        <h2>设备趋势图</h2>
        <p class="panel-subtitle">按时间窗查看单台设备最近一段时间的心率、体温、血氧和健康评分变化。</p>
      </div>
      <span>{{ deviceMac || "请选择设备" }}</span>
    </div>
    <div class="trend-toolbar">
      <div class="trend-window-row">
        <button class="filter-chip" :class="{ active: windowMinutes === 60 }" @click="emit('change-window', 60)">1 小时</button>
        <button class="filter-chip" :class="{ active: windowMinutes === 180 }" @click="emit('change-window', 180)">3 小时</button>
        <button class="filter-chip" :class="{ active: windowMinutes === 720 }" @click="emit('change-window', 720)">12 小时</button>
      </div>
      <div class="trend-kpis">
        <span v-for="item in trendMetrics" :key="item.label">{{ item.label }} {{ item.value }}</span>
      </div>
    </div>
    <div ref="chartRef" class="trend-canvas"></div>
  </section>
</template>
