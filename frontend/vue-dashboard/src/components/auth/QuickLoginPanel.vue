<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { Check, Zap } from "lucide-vue-next";
import type { AuthAccountPreview } from "../../api/client";

defineProps<{
  accounts: AuthAccountPreview[];
  helperText: string;
  selectedAccount: string;
  disabled?: boolean;
}>();

const emit = defineEmits<{
  select: [username: string];
}>();

const BALL_SIZE = 52;
const EDGE_MARGIN = 10;
const POS_STORAGE_KEY = "quick-fab-pos";

const open = ref(false);
const dragging = ref(false);
const pos = ref({ x: 0, y: 0 });

let pressed = false;
let suppressClick = false;
let dragStart = { pointerX: 0, pointerY: 0, ballX: 0, ballY: 0 };

function clampPos(x: number, y: number) {
  return {
    x: Math.min(Math.max(x, EDGE_MARGIN), window.innerWidth - BALL_SIZE - EDGE_MARGIN),
    y: Math.min(Math.max(y, EDGE_MARGIN), window.innerHeight - BALL_SIZE - EDGE_MARGIN),
  };
}

function restorePos() {
  let saved: { x: number; y: number } | null = null;
  try {
    saved = JSON.parse(localStorage.getItem(POS_STORAGE_KEY) ?? "null");
  } catch {
    saved = null;
  }
  const fallback = { x: window.innerWidth - BALL_SIZE - 28, y: window.innerHeight - BALL_SIZE - 28 };
  pos.value = clampPos(saved?.x ?? fallback.x, saved?.y ?? fallback.y);
}

function onWindowResize() {
  pos.value = clampPos(pos.value.x, pos.value.y);
}

onMounted(() => {
  restorePos();
  window.addEventListener("resize", onWindowResize);
});

onUnmounted(() => {
  window.removeEventListener("resize", onWindowResize);
});

function onPointerDown(event: PointerEvent) {
  pressed = true;
  dragging.value = false;
  dragStart = {
    pointerX: event.clientX,
    pointerY: event.clientY,
    ballX: pos.value.x,
    ballY: pos.value.y,
  };
  (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
}

function onPointerMove(event: PointerEvent) {
  if (!pressed) return;
  const dx = event.clientX - dragStart.pointerX;
  const dy = event.clientY - dragStart.pointerY;
  if (!dragging.value && Math.abs(dx) + Math.abs(dy) < 5) return;
  dragging.value = true;
  open.value = false;
  pos.value = clampPos(dragStart.ballX + dx, dragStart.ballY + dy);
}

function onPointerUp() {
  if (!pressed) return;
  pressed = false;
  if (dragging.value) {
    dragging.value = false;
    suppressClick = true;
    localStorage.setItem(POS_STORAGE_KEY, JSON.stringify(pos.value));
  }
}

function onBallClick() {
  if (suppressClick) {
    suppressClick = false;
    return;
  }
  open.value = !open.value;
}

function pick(username: string) {
  emit("select", username);
  open.value = false;
}

/* 弹出方向自适应：球在屏幕上半时向下弹，靠左时左对齐 */
const popDown = computed(() => pos.value.y < 420);
const popLeft = computed(() => pos.value.x < window.innerWidth / 2);
</script>

<template>
  <div class="quick-fab-root" :style="{ left: pos.x + 'px', top: pos.y + 'px' }">
    <!-- 点击外部关闭 -->
    <div v-if="open" class="quick-fab-backdrop" @click="open = false"></div>

    <transition name="quick-pop">
      <article
        v-if="open"
        class="quick-pop"
        :class="{ 'quick-pop--down': popDown, 'quick-pop--left': popLeft }"
        role="dialog"
        aria-label="演示账号快捷登录"
      >
        <header class="quick-pop__head">
          <span class="quick-pop__icon"><Zap :size="16" /></span>
          <div>
            <h3>快速演示</h3>
            <p>{{ helperText }}</p>
          </div>
        </header>

        <div v-if="accounts.length" class="quick-pop__list">
          <button
            v-for="account in accounts"
            :key="account.username"
            type="button"
            class="quick-pop__item"
            :class="{ 'quick-pop__item--active': account.username === selectedAccount }"
            :disabled="disabled"
            @click="pick(account.username)"
          >
            <span class="quick-pop__avatar">{{ account.display_name.slice(0, 1) }}</span>
            <span class="quick-pop__info">
              <b>{{ account.display_name }}</b>
              <i>{{ account.role }} · {{ account.username }}</i>
            </span>
            <Check v-if="account.username === selectedAccount" :size="16" class="quick-pop__check" />
          </button>
        </div>

        <p class="quick-pop__hint">点击账号即回填或切换登录身份 · 按住悬浮球可拖动</p>
      </article>
    </transition>

    <button
      type="button"
      class="quick-fab"
      :class="{ 'quick-fab--open': open, 'quick-fab--dragging': dragging }"
      aria-label="演示账号快捷登录"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @click="onBallClick"
    >
      <Zap :size="20" />
    </button>
  </div>
</template>

<style scoped>
.quick-fab-root {
  position: fixed;
  z-index: 60;
}

.quick-fab-backdrop {
  position: fixed;
  inset: 0;
  background: transparent;
}

/* 悬浮球 */
.quick-fab {
  position: relative;
  width: 52px;
  height: 52px;
  border: 1px solid rgba(255, 255, 255, 0.35);
  border-radius: 50%;
  background: linear-gradient(135deg, #0e7490 0%, #0891b2 100%);
  color: #ffffff;
  cursor: grab;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 24px rgba(8, 50, 69, 0.45);
  transition: transform 180ms ease, box-shadow 180ms ease;
  touch-action: none;
  user-select: none;
}

.quick-fab::after {
  content: '';
  position: absolute;
  inset: -1px;
  border-radius: 50%;
  animation: fabPulse 2.6s ease-out infinite;
  pointer-events: none;
}

@keyframes fabPulse {
  0%   { box-shadow: 0 0 0 0 rgba(8, 145, 178, 0.45); }
  70%  { box-shadow: 0 0 0 12px rgba(8, 145, 178, 0); }
  100% { box-shadow: 0 0 0 0 rgba(8, 145, 178, 0); }
}

.quick-fab:hover {
  transform: translateY(-2px) scale(1.05);
  box-shadow: 0 12px 32px rgba(8, 50, 69, 0.55);
}

.quick-fab--open {
  transform: scale(0.96);
}

.quick-fab--open::after {
  animation: none;
}

.quick-fab--dragging {
  cursor: grabbing;
  transform: scale(1.08);
  transition: none;
}

.quick-fab--dragging::after {
  animation: none;
}

/* 弹出面板：默认向上、右对齐；按位置翻转 */
.quick-pop {
  position: absolute;
  right: 0;
  bottom: 64px;
  width: 300px;
  padding: 16px 16px 13px;
  background: rgba(255, 255, 255, 0.97);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 14px;
  box-shadow: 0 24px 64px rgba(8, 50, 69, 0.40);
  backdrop-filter: blur(14px);
}

.quick-pop--down {
  bottom: auto;
  top: 64px;
}

.quick-pop--left {
  right: auto;
  left: 0;
}

.quick-pop__head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
}

.quick-pop__icon {
  width: 30px;
  height: 30px;
  border-radius: 9px;
  background: rgba(14, 116, 144, 0.10);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #0e7490;
  flex-shrink: 0;
}

.quick-pop__head h3 {
  margin: 0 0 3px 0;
  font-size: 15.5px;
  font-weight: 700;
  color: #16212e;
}

.quick-pop__head p {
  margin: 0;
  font-size: 13px;
  color: #4c5e70;
  line-height: 1.5;
}

.quick-pop__list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  max-height: min(340px, calc(100vh - 260px));
  overflow-y: auto;
  padding-right: 4px;
  scrollbar-width: thin;
  scrollbar-color: rgba(14, 116, 144, 0.35) transparent;
}

.quick-pop__list::-webkit-scrollbar {
  width: 5px;
}

.quick-pop__list::-webkit-scrollbar-thumb {
  background: rgba(14, 116, 144, 0.35);
  border-radius: 99px;
}

.quick-pop__item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: 1px solid #e2e8ee;
  border-radius: 10px;
  background: #f9fafc;
  cursor: pointer;
  text-align: left;
  transition: all 160ms ease;
}

.quick-pop__item:hover:not(:disabled) {
  border-color: #0e7490;
  background: rgba(14, 116, 144, 0.06);
  transform: translateY(-1px);
}

.quick-pop__item--active {
  border-color: #0e7490;
  background: rgba(14, 116, 144, 0.08);
}

.quick-pop__item:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.quick-pop__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, #0e7490, #0891b2);
  color: #ffffff;
  font-size: 14.5px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.quick-pop__info {
  flex: 1;
  min-width: 0;
}

.quick-pop__info b {
  display: block;
  font-size: 14.5px;
  font-weight: 700;
  color: #16212e;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quick-pop__info i {
  display: block;
  font-style: normal;
  font-size: 12.5px;
  color: #8595a7;
  margin-top: 1px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.quick-pop__check {
  color: #0e7490;
  flex-shrink: 0;
}

.quick-pop__hint {
  margin: 11px 2px 0;
  font-size: 12px;
  color: #8595a7;
  line-height: 1.5;
}

/* 弹出动效 */
.quick-pop-enter-active,
.quick-pop-leave-active {
  transition: opacity 180ms ease, transform 180ms ease;
}

.quick-pop-enter-from,
.quick-pop-leave-to {
  opacity: 0;
  transform: translateY(10px) scale(0.96);
}

@media (max-width: 640px) {
  .quick-pop {
    width: min(300px, calc(100vw - 48px));
  }
}
</style>
