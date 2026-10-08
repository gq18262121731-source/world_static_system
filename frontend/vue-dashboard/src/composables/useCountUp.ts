import { onUnmounted, ref, watch, type Ref } from "vue";

/**
 * 数值 count-up 过渡：目标值变化时用 rAF 缓动逼近，消除数值跳变。
 * 尊重 prefers-reduced-motion：偏好减弱动效时直接落定目标值。
 */
export function useCountUp(
  source: Ref<number | null>,
  options: { durationMs?: number; decimals?: number } = {},
) {
  const durationMs = options.durationMs ?? 900;
  const decimals = options.decimals ?? 0;
  const factor = 10 ** decimals;
  const display = ref<number | null>(null);
  let rafId = 0;

  function settle(value: number) {
    display.value = Math.round(value * factor) / factor;
  }

  watch(
    source,
    (target) => {
      cancelAnimationFrame(rafId);
      if (target == null || !Number.isFinite(target)) {
        display.value = null;
        return;
      }
      const reduced =
        typeof window !== "undefined"
        && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (reduced) {
        settle(target);
        return;
      }
      const from = display.value ?? 0;
      const startAt = performance.now();
      const tick = (now: number) => {
        const progress = Math.min(1, (now - startAt) / durationMs);
        const eased = 1 - (1 - progress) ** 3;
        settle(from + (target - from) * eased);
        if (progress < 1) rafId = requestAnimationFrame(tick);
      };
      rafId = requestAnimationFrame(tick);
    },
    { immediate: true },
  );

  onUnmounted(() => cancelAnimationFrame(rafId));

  return display;
}
