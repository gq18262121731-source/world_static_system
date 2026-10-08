<script setup lang="ts">
import { Network, Printer, Stethoscope, Zap } from "lucide-vue-next";

const props = defineProps<{
  alarmCount: number;
  offlineCount: number;
}>();

const emit = defineEmits<{
  goAlarms: [];
  goReport: [];
  newTask: [];
  goTopology: [];
}>();
</script>

<template>
  <div class="quick-actions">
    <button type="button" class="qa" @click="emit('goAlarms')">
      <span class="qa__icon qa__icon--warn"><Zap :size="17" /></span>
      <span class="qa__text">
        <strong>处理告警</strong>
        <small>{{ props.alarmCount > 0 ? `${props.alarmCount} 条待确认` : "当前无待确认告警" }}</small>
      </span>
    </button>

    <button type="button" class="qa" @click="emit('newTask')">
      <span class="qa__icon qa__icon--ok"><Stethoscope :size="17" /></span>
      <span class="qa__text">
        <strong>发起随访</strong>
        <small>为重点对象创建回访任务</small>
      </span>
    </button>

    <button type="button" class="qa" @click="emit('goTopology')">
      <span class="qa__icon qa__icon--brand"><Network :size="17" /></span>
      <span class="qa__text">
        <strong>排查设备</strong>
        <small>{{ props.offlineCount > 0 ? `${props.offlineCount} 台离线待处理` : "设备全部在线" }}</small>
      </span>
    </button>

    <button type="button" class="qa" @click="emit('goReport')">
      <span class="qa__icon qa__icon--muted"><Printer :size="17" /></span>
      <span class="qa__text">
        <strong>交接报告</strong>
        <small>查看并导出 A4 归档版</small>
      </span>
    </button>
  </div>
</template>

<style scoped>
.quick-actions {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
  gap: 12px;
}

.qa {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 16px;
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  background: var(--panel-strong);
  box-shadow: var(--shadow-sm);
  cursor: pointer;
  text-align: left;
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.qa:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.qa__icon {
  width: 38px;
  height: 38px;
  border-radius: 11px;
  display: grid;
  place-items: center;
  color: #ffffff;
  flex-shrink: 0;
}

.qa__icon--brand { background: linear-gradient(135deg, var(--brand), var(--brand-2)); }
.qa__icon--ok    { background: linear-gradient(135deg, var(--risk-low), var(--brand-2)); }
.qa__icon--warn  { background: linear-gradient(135deg, var(--risk-medium), var(--risk-high)); }
.qa__icon--muted { background: linear-gradient(135deg, var(--surface-3), var(--text-sub)); }

.qa__text {
  min-width: 0;
}

.qa__text strong {
  display: block;
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-main);
}

.qa__text small {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
