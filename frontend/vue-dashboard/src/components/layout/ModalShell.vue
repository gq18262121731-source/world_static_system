<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";
import { X } from "lucide-vue-next";

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    subtitle?: string;
    /** sm 用于表单，lg 用于报告类长内容 */
    size?: "sm" | "md" | "lg";
  }>(),
  { subtitle: "", size: "md" },
);

const emit = defineEmits<{ close: [] }>();

function onKeydown(event: KeyboardEvent) {
  if (event.key === "Escape") emit("close");
}

/*
 * 打开时锁定 body 滚动，否则背景页会跟着滚。
 * 必须在卸载时兜底恢复，否则组件在打开状态下被销毁会让整页永久无法滚动。
 */
watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener("keydown", onKeydown);
      document.body.style.overflow = "hidden";
    } else {
      document.removeEventListener("keydown", onKeydown);
      document.body.style.overflow = "";
    }
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  document.body.style.overflow = "";
});
</script>

<template>
  <Teleport to="body">
    <Transition name="modal">
      <div
        v-if="open"
        class="modal-mask"
        role="dialog"
        aria-modal="true"
        :aria-label="title"
        @click.self="emit('close')"
      >
        <div class="modal-panel" :class="`modal-panel--${size}`">
          <header class="modal-head">
            <div class="modal-head__copy">
              <strong>{{ title }}</strong>
              <small v-if="subtitle">{{ subtitle }}</small>
            </div>
            <div class="modal-head__extra">
              <slot name="actions" />
              <button type="button" class="modal-close" title="关闭" @click="emit('close')">
                <X :size="17" />
              </button>
            </div>
          </header>

          <div class="modal-body">
            <slot />
          </div>

          <footer v-if="$slots.footer" class="modal-foot">
            <slot name="footer" />
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  padding: 28px;
  background: rgba(22, 33, 46, 0.42);
  backdrop-filter: blur(3px);
}

.modal-panel {
  display: flex;
  flex-direction: column;
  width: 100%;
  max-height: 100%;
  min-height: 0;
  border: 1px solid var(--line);
  border-radius: var(--radius-xl);
  background: var(--panel-strong);
  box-shadow: var(--shadow-lg);
  overflow: hidden;
}

.modal-panel--sm { max-width: 560px; }
.modal-panel--md { max-width: 880px; }
.modal-panel--lg { max-width: 1180px; }

.modal-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 16px 18px;
  border-bottom: 1px solid var(--line);
}

.modal-head__copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.modal-head__copy strong {
  font-family: var(--font-display);
  font-size: var(--fs-3);
  font-weight: 700;
  color: var(--text-main);
}

.modal-head__copy small {
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.modal-head__extra {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.modal-close {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-tinted);
  color: var(--text-sub);
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease;
}

.modal-close:hover {
  border-color: var(--risk-high);
  color: var(--risk-high);
}

.modal-body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 18px;
}

.modal-body::-webkit-scrollbar { width: 8px; }
.modal-body::-webkit-scrollbar-thumb {
  background: var(--surface-2);
  border-radius: 4px;
}

.modal-foot {
  flex-shrink: 0;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 18px;
  border-top: 1px solid var(--line);
  background: var(--panel-tinted);
}

/* 只动 transform/opacity，保持帧率 */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 200ms ease;
}

.modal-enter-active .modal-panel,
.modal-leave-active .modal-panel {
  transition: transform 240ms cubic-bezier(0.22, 0.8, 0.3, 1), opacity 240ms ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-panel,
.modal-leave-to .modal-panel {
  opacity: 0;
  transform: translateY(14px) scale(0.98);
}

@media (max-width: 720px) {
  .modal-mask {
    padding: 12px;
  }
}
</style>
