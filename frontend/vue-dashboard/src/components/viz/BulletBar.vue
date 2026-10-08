<script setup lang="ts">
import { computed } from "vue";

/**
 * 参考区间定位条：把实测值放到「正常区间」的刻度上，
 * 比单独一个数字更容易判断"离边界还有多远"。
 */
const props = withDefaults(
  defineProps<{
    value: number | null;
    /** 正常区间下界 / 上界 */
    low: number;
    high: number;
    /** 轴的显示范围，缺省时按区间外扩 40% */
    min?: number;
    max?: number;
    unit?: string;
    /** 单边阈值指标（如血氧只有下界）时隐藏上界刻度 */
    upperOpen?: boolean;
  }>(),
  { upperOpen: false },
);

const axis = computed(() => {
  const pad = (props.high - props.low) * 0.4 || 1;
  const min = props.min ?? props.low - pad;
  const max = props.max ?? props.high + pad;
  return { min, max, span: max - min || 1 };
});

function toPercent(value: number) {
  const ratio = (value - axis.value.min) / axis.value.span;
  return Math.min(100, Math.max(0, ratio * 100));
}

const bandStyle = computed(() => ({
  left: `${toPercent(props.low)}%`,
  width: `${Math.max(2, toPercent(props.high) - toPercent(props.low))}%`,
}));

const markerPercent = computed(() =>
  props.value == null || !Number.isFinite(props.value) ? null : toPercent(props.value),
);

const state = computed<"normal" | "low" | "high" | "unknown">(() => {
  if (props.value == null || !Number.isFinite(props.value)) return "unknown";
  if (props.value < props.low) return "low";
  if (!props.upperOpen && props.value > props.high) return "high";
  return "normal";
});

const rangeLabel = computed(() => {
  const unit = props.unit ?? "";
  if (props.upperOpen) return `参考 ≥ ${props.low}${unit}`;
  return `参考 ${props.low}–${props.high}${unit}`;
});
</script>

<template>
  <div class="bullet" :class="`bullet--${state}`">
    <div class="bullet__track">
      <span class="bullet__band" :style="bandStyle"></span>
      <span
        v-if="markerPercent != null"
        class="bullet__marker"
        :style="{ left: `${markerPercent}%` }"
      ></span>
    </div>
    <span class="bullet__range">{{ rangeLabel }}</span>
  </div>
</template>

<style scoped>
.bullet {
  display: grid;
  gap: 4px;
  --marker: var(--risk-low);
}

.bullet--low,
.bullet--high { --marker: var(--risk-medium); }
.bullet--unknown { --marker: var(--surface-3); }

.bullet__track {
  position: relative;
  height: 6px;
  border-radius: 99px;
  background: var(--surface-0);
  overflow: hidden;
}

.bullet__band {
  position: absolute;
  top: 0;
  bottom: 0;
  border-radius: 99px;
  background: var(--surface-success);
}

.bullet__marker {
  position: absolute;
  top: -2px;
  width: 3px;
  height: 10px;
  border-radius: 2px;
  background: var(--marker);
  transform: translateX(-50%);
  transition: left 600ms cubic-bezier(0.22, 0.8, 0.3, 1);
  box-shadow: 0 0 0 2px var(--panel-strong);
}

.bullet__range {
  font-size: 11px;
  color: var(--text-muted);
}

.bullet--low .bullet__range,
.bullet--high .bullet__range {
  color: var(--risk-medium);
  font-weight: 600;
}
</style>
