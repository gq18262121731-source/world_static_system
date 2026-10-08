<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    values: number[];
    /** 语义色：跟随趋势方向自动着色，或强制指定 */
    tone?: "auto" | "brand" | "ok" | "warn" | "danger" | "muted";
    /** 上升是否为好事（健康分上升好，告警数上升坏） */
    riseIsGood?: boolean;
    height?: number;
    showArea?: boolean;
    showLastDot?: boolean;
  }>(),
  {
    tone: "auto",
    riseIsGood: true,
    height: 26,
    showArea: true,
    showLastDot: true,
  },
);

/** 采样上限 30 点：超过则等距抽样，避免密集折线糊成一团 */
const MAX_POINTS = 30;
const VIEW_W = 100;
const VIEW_H = 32;

const series = computed(() => {
  const clean = props.values.filter((value) => Number.isFinite(value));
  if (clean.length <= MAX_POINTS) return clean;
  const step = clean.length / MAX_POINTS;
  return Array.from({ length: MAX_POINTS }, (_, index) => clean[Math.floor(index * step)]);
});

const geometry = computed(() => {
  const data = series.value;
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const stepX = VIEW_W / (data.length - 1);

  const points = data.map((value, index) => {
    const x = index * stepX;
    // 上下留 3 单位边距，避免线贴边被裁
    const y = VIEW_H - 3 - ((value - min) / span) * (VIEW_H - 6);
    return { x, y };
  });

  return {
    line: points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" "),
    area:
      `0,${VIEW_H} `
      + points.map((point) => `${point.x.toFixed(2)},${point.y.toFixed(2)}`).join(" ")
      + ` ${VIEW_W},${VIEW_H}`,
    last: points[points.length - 1],
  };
});

const resolvedTone = computed(() => {
  if (props.tone !== "auto") return props.tone;
  const data = series.value;
  if (data.length < 2) return "muted";
  const delta = data[data.length - 1] - data[0];
  if (Math.abs(delta) < 1e-6) return "brand";
  const rising = delta > 0;
  return rising === props.riseIsGood ? "ok" : "warn";
});
</script>

<template>
  <svg
    v-if="geometry"
    class="mini-spark"
    :class="`mini-spark--${resolvedTone}`"
    :style="{ height: `${props.height}px` }"
    :viewBox="`0 0 ${VIEW_W} ${VIEW_H}`"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <polygon v-if="props.showArea" class="mini-spark__area" :points="geometry.area" />
    <polyline class="mini-spark__line" pathLength="1" :points="geometry.line" />
    <circle
      v-if="props.showLastDot"
      class="mini-spark__dot"
      :cx="geometry.last.x"
      :cy="geometry.last.y"
      r="2"
    />
  </svg>
  <span v-else class="mini-spark mini-spark--empty" :style="{ height: `${props.height}px` }"></span>
</template>

<style scoped>
.mini-spark {
  display: block;
  width: 100%;
  overflow: visible;
  --spark: var(--brand-2);
}

.mini-spark--brand { --spark: var(--brand-2); }
.mini-spark--ok { --spark: var(--risk-low); }
.mini-spark--warn { --spark: var(--risk-medium); }
.mini-spark--danger { --spark: var(--risk-high); }
.mini-spark--muted { --spark: var(--surface-3); }

.mini-spark__line {
  fill: none;
  stroke: var(--spark);
  stroke-width: 1.6;
  stroke-linecap: round;
  stroke-linejoin: round;
  vector-effect: non-scaling-stroke;
  /* pathLength 归一化后 dasharray 用 0–1 表达，与实际点数无关 */
  pathLength: 1;
  stroke-dasharray: 1;
  animation: spark-draw 760ms var(--ease-enter, cubic-bezier(0.22, 0.8, 0.3, 1)) both;
}

.mini-spark__area {
  fill: var(--spark);
  opacity: 0.12;
  stroke: none;
  animation: spark-fade 900ms ease both;
}

.mini-spark__dot {
  fill: var(--spark);
  vector-effect: non-scaling-stroke;
  animation: spark-pop 320ms ease 700ms both;
}

@keyframes spark-draw {
  from { stroke-dashoffset: 1; }
  to { stroke-dashoffset: 0; }
}

@keyframes spark-fade {
  from { opacity: 0; }
  to { opacity: 0.12; }
}

@keyframes spark-pop {
  from { opacity: 0; transform: scale(0.4); }
  to { opacity: 1; transform: scale(1); }
}

.mini-spark--empty {
  border-bottom: 1px dashed var(--line);
}
</style>
