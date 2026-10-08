<script setup lang="ts">
import type { CommunityDashboardElderItem } from "../api/client";

type AlertItem = {
  alarm_id: string;
  alarm_type: string;
  alarm_level: number;
  acknowledged: boolean;
  message: string;
  created_at: string;
  device_mac: string;
  elder_name?: string | null;
};

const props = defineProps<{
  alerts: AlertItem[];
  elders: CommunityDashboardElderItem[];
}>();

const emit = defineEmits<{
  /** 选中告警对应的老人，由页面负责切换焦点并关闭弹窗 */
  locate: [elderId: string];
}>();

function alertLevel(item: AlertItem) {
  if (item.acknowledged) return { dot: "tl-dot--ok", chip: "已处理", chipCls: "tl-lv--ok" };
  if (item.alarm_type === "sos" || item.alarm_level <= 1 || /sos|求助|紧急/i.test(item.message)) {
    return { dot: "tl-dot--danger", chip: "P0", chipCls: "tl-lv--p0" };
  }
  if (item.alarm_level === 2) return { dot: "tl-dot--warn", chip: "P1", chipCls: "tl-lv--p1" };
  return { dot: "tl-dot--warn", chip: "P2", chipCls: "tl-lv--p2" };
}

function linkedElder(deviceMac: string) {
  return props.elders.find((item) => item.device_mac === deviceMac) ?? null;
}

function timeLabel(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    hour12: false,
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>

<template>
  <div class="alert-timeline">
    <article v-for="item in props.alerts" :key="item.alarm_id" class="tl-item">
      <span class="tl-dot" :class="alertLevel(item).dot"></span>
      <div class="tl-body">
        <div class="tl-head">
          <strong>{{ item.elder_name ?? item.device_mac }}</strong>
          <span class="tl-lv" :class="alertLevel(item).chipCls">{{ alertLevel(item).chip }}</span>
          <em>{{ timeLabel(item.created_at) }}</em>
        </div>
        <p>{{ item.message }}</p>
        <div v-if="linkedElder(item.device_mac)" class="tl-act">
          <button type="button" @click="emit('locate', linkedElder(item.device_mac)!.elder_id)">
            查看对象
          </button>
        </div>
      </div>
    </article>

    <p v-if="!props.alerts.length" class="tl-empty">当前没有告警记录。</p>
  </div>
</template>

<style scoped>
.alert-timeline {
  display: grid;
  gap: 4px;
}

.tl-item {
  display: flex;
  gap: 12px;
  padding: 12px 2px;
  border-bottom: 1px solid var(--line);
}

.tl-item:last-of-type {
  border-bottom: none;
}

.tl-dot {
  flex-shrink: 0;
  width: 9px;
  height: 9px;
  margin-top: 6px;
  border-radius: 999px;
  background: var(--surface-2);
}

.tl-dot--ok { background: var(--risk-low); }
.tl-dot--warn { background: var(--risk-medium); }
.tl-dot--danger { background: var(--risk-high); }

.tl-body {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 4px;
}

.tl-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 9px;
}

.tl-head strong {
  font-size: var(--fs-2);
  font-weight: 700;
  color: var(--text-main);
}

.tl-head em {
  margin-left: auto;
  font-style: normal;
  font-family: var(--font-mono);
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.tl-lv {
  padding: 2px 9px;
  border-radius: 999px;
  font-size: var(--fs-0);
  font-weight: 700;
  white-space: nowrap;
}

.tl-lv--ok { color: var(--risk-low); background: var(--surface-success); }
.tl-lv--p0 { color: var(--risk-high); background: var(--surface-danger); }
.tl-lv--p1 { color: var(--risk-medium); background: var(--surface-warning); }
.tl-lv--p2 { color: var(--text-sub); background: var(--surface-soft); }

.tl-body p {
  margin: 0;
  font-size: var(--fs-2);
  color: var(--text-sub);
  line-height: 1.6;
}

.tl-act button {
  padding: 4px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-tinted);
  color: var(--brand);
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
}

.tl-act button:hover {
  border-color: var(--brand);
}

.tl-empty {
  margin: 0;
  padding: 18px 0;
  text-align: center;
  font-size: var(--fs-2);
  color: var(--text-muted);
}
</style>
