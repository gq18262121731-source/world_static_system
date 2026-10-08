<script setup lang="ts">
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    /** 变化量，正数为上升 */
    delta: number | null;
    /** 上升是否为好事 */
    riseIsGood?: boolean;
    unit?: string;
    decimals?: number;
    /** 变化量绝对值小于该值时视为持平 */
    flatThreshold?: number;
  }>(),
  { riseIsGood: true, unit: "", decimals: 0, flatThreshold: 0.05 },
);

const tone = computed(() => {
  if (props.delta == null || !Number.isFinite(props.delta)) return "unknown";
  if (Math.abs(props.delta) < props.flatThreshold) return "flat";
  return props.delta > 0 === props.riseIsGood ? "good" : "bad";
});

const label = computed(() => {
  if (props.delta == null || !Number.isFinite(props.delta)) return "--";
  if (tone.value === "flat") return "持平";
  const arrow = props.delta > 0 ? "▲" : "▼";
  return `${arrow} ${Math.abs(props.delta).toFixed(props.decimals)}${props.unit}`;
});
</script>

<template>
  <span class="delta-chip" :class="`delta-chip--${tone}`">{{ label }}</span>
</template>

<style scoped>
.delta-chip {
  display: inline-flex;
  align-items: center;
  font-size: 12.5px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 999px;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.delta-chip--good { color: var(--risk-low); background: var(--surface-success); }
.delta-chip--bad { color: var(--risk-high); background: var(--surface-danger); }
.delta-chip--flat,
.delta-chip--unknown { color: var(--text-muted); background: var(--surface-soft); }
</style>
