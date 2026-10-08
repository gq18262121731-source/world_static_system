<script setup lang="ts">
import { computed } from "vue";
import { ChevronLeft, ChevronRight } from "lucide-vue-next";
import type { CommunityDashboardElderItem } from "../api/client";
import { riskLevelToChinese } from "../utils/riskLevel";
import BulletBar from "./viz/BulletBar.vue";

const props = defineProps<{
  elders: CommunityDashboardElderItem[];
  selectedElderId: string;
}>();

const emit = defineEmits<{
  select: [elderId: string];
}>();

type CardTone = "sos" | "no-device" | "offline" | "pending" | "risk-high" | "risk-medium" | "risk-low";

function elderHasObservedRealtime(elder: CommunityDashboardElderItem) {
  return Boolean(
    elder.latest_timestamp
      || elder.heart_rate != null
      || elder.blood_oxygen != null
      || elder.blood_pressure
      || elder.temperature != null
      || elder.latest_health_score != null,
  );
}

function elderHasActiveSos(elder: CommunityDashboardElderItem) {
  return elder.sos_active === true || Boolean(elder.active_sos_alarm_id);
}

function elderTone(elder: CommunityDashboardElderItem): CardTone {
  if (elderHasActiveSos(elder)) return "sos";
  if (!elder.device_mac || elder.device_status === "no_device") return "no-device";
  if (elder.device_status === "offline") return "offline";
  if (elder.device_status === "pending" && !elderHasObservedRealtime(elder)) return "pending";
  if (elder.risk_level === "high") return "risk-high";
  if (elder.risk_level === "medium") return "risk-medium";
  return "risk-low";
}

function elderLabel(elder: CommunityDashboardElderItem): string {
  if (elderHasActiveSos(elder)) return "告警中";
  if (!elder.device_mac || elder.device_status === "no_device") return "无设备";
  if (elder.device_status === "offline") return "离线";
  if (elder.device_status === "pending" && !elderHasObservedRealtime(elder)) return "待同步";
  return "在线";
}

function elderMeta(elder: CommunityDashboardElderItem): string {
  if (!elder.device_mac || elder.device_status === "no_device") {
    return `${elder.apartment} · 等待移动端绑定手环`;
  }
  if (elder.device_status === "offline") {
    return `${elder.apartment} · 设备暂时离线`;
  }
  if (elder.device_status === "pending" && !elderHasObservedRealtime(elder)) {
    return `${elder.apartment} · 已绑定，等待首包`;
  }
  return `${elder.apartment} · 风险 ${riskLevelToChinese(elder.structured_health?.risk_level ?? elder.risk_level)}`;
}

/** 体征越界着色：阈值口径与下方"需关注"快捷条保持一致 */
function vitalTone(kind: "hr" | "spo2" | "temp", value: number | null | undefined) {
  if (value == null || !Number.isFinite(value)) return "";
  if (kind === "hr") return value > 110 || value < 45 ? "focus-vt--bad" : "";
  if (kind === "spo2") return value < 93 ? "focus-vt--bad" : value < 95 ? "focus-vt--warn" : "";
  return value >= 37.8 ? "focus-vt--bad" : value >= 37.3 ? "focus-vt--warn" : "";
}

const noDeviceCount = computed(() => props.elders.filter((elder) => !elder.device_mac || elder.device_status === "no_device").length);
const offlineCount = computed(() => props.elders.filter((elder) => elder.device_status === "offline").length);

/* ---------- 单对象展示 + 选择切换 ---------- */
const focusElder = computed<CommunityDashboardElderItem | null>(
  () =>
    props.elders.find((elder) => elder.elder_id === props.selectedElderId)
    ?? props.elders[0]
    ?? null,
);

const focusIndex = computed(() =>
  props.elders.findIndex((elder) => elder.elder_id === focusElder.value?.elder_id),
);

function step(delta: number) {
  if (!props.elders.length) return;
  const next = (focusIndex.value + delta + props.elders.length) % props.elders.length;
  emit("select", props.elders[next].elder_id);
}

/** 下拉选择：v-model 直接改 prop 不合法，转成事件上抛 */
function onPick(event: Event) {
  const value = (event.target as HTMLSelectElement).value;
  if (value) emit("select", value);
}

/*
 * 异常对象快捷条：只展示一张卡后，值守看不到其余对象，SOS 与体征越界必须
 * 主动浮出来，否则要翻下拉框才能发现。判定口径与卡片着色保持一致。
 */
type AttentionReason = { elder: CommunityDashboardElderItem; text: string; tone: "sos" | "bad" | "warn" };

const attentionElders = computed<AttentionReason[]>(() => {
  const rows: AttentionReason[] = [];
  for (const elder of props.elders) {
    if (elder.elder_id === focusElder.value?.elder_id) continue;

    if (elderHasActiveSos(elder)) {
      rows.push({ elder, text: "SOS 求助", tone: "sos" });
      continue;
    }
    if (elder.blood_oxygen != null && elder.blood_oxygen < 93) {
      rows.push({ elder, text: `血氧 ${elder.blood_oxygen}%`, tone: "bad" });
      continue;
    }
    if (elder.temperature != null && elder.temperature >= 37.8) {
      rows.push({ elder, text: `体温 ${elder.temperature.toFixed(1)}°C`, tone: "bad" });
      continue;
    }
    if (elder.heart_rate != null && (elder.heart_rate > 110 || elder.heart_rate < 45)) {
      rows.push({ elder, text: `心率 ${elder.heart_rate}`, tone: "bad" });
      continue;
    }
    if (elder.risk_level === "high" && elderHasObservedRealtime(elder)) {
      rows.push({ elder, text: "高风险", tone: "bad" });
      continue;
    }
    if (elder.blood_oxygen != null && elder.blood_oxygen < 95) {
      rows.push({ elder, text: `血氧 ${elder.blood_oxygen}%`, tone: "warn" });
      continue;
    }
    if (elder.device_status === "offline") {
      rows.push({ elder, text: "设备离线", tone: "warn" });
    }
  }
  // SOS 与危险值排在前面
  const weight = { sos: 0, bad: 1, warn: 2 } as const;
  return rows.sort((left, right) => weight[left.tone] - weight[right.tone]);
});
</script>

<template>
  <section class="device-rail">
    <div class="device-rail__head">
      <div>
        <p class="section-eyebrow">社区监护总览</p>
        <h2>老人监护对象</h2>
      </div>
      <small>切换对象后，下方实时监护视图会同步加载其体征曲线。</small>
    </div>

    <div class="device-rail__meta">
      <span class="summary-badge">老人 {{ elders.length }}</span>
      <span class="summary-badge">无设备 {{ noDeviceCount }}</span>
      <span class="summary-badge">离线 {{ offlineCount }}</span>
    </div>

    <!-- 对象选择器 -->
    <div class="rail-picker">
      <label class="rail-picker__field">
        <span>当前对象</span>
        <select :value="focusElder?.elder_id ?? ''" @change="onPick">
          <option v-for="elder in elders" :key="elder.elder_id" :value="elder.elder_id">
            {{ elder.elder_name }} · {{ elder.apartment }} · {{ elderLabel(elder) }}
          </option>
        </select>
      </label>

      <div class="rail-picker__nav">
        <button type="button" :disabled="elders.length < 2" title="上一位" @click="step(-1)">
          <ChevronLeft :size="16" />
        </button>
        <span class="rail-picker__count">{{ focusIndex + 1 }} / {{ elders.length }}</span>
        <button type="button" :disabled="elders.length < 2" title="下一位" @click="step(1)">
          <ChevronRight :size="16" />
        </button>
      </div>
    </div>

    <!-- 选中对象详情卡 -->
    <article v-if="focusElder" class="focus-card" :class="elderTone(focusElder)">
      <header class="focus-card__top">
        <span class="focus-card__avatar">
          {{ focusElder.elder_name.slice(0, 1) }}
          <i
            class="focus-card__dot"
            :class="{ 'focus-card__dot--live': elderLabel(focusElder) === '在线' || elderHasActiveSos(focusElder) }"
          ></i>
        </span>
        <span class="focus-card__id">
          <strong>{{ focusElder.elder_name }}</strong>
          <small>{{ elderMeta(focusElder) }}</small>
        </span>
        <span class="focus-card__state">{{ elderLabel(focusElder) }}</span>
      </header>

      <div class="focus-card__vitals">
        <div class="focus-vt" :class="vitalTone('hr', focusElder.heart_rate)">
          <span class="focus-vt__label">心率</span>
          <strong class="focus-vt__value">{{ focusElder.heart_rate ?? "--" }}<small>bpm</small></strong>
          <BulletBar :value="focusElder.heart_rate ?? null" :low="60" :high="100" />
        </div>
        <div class="focus-vt" :class="vitalTone('spo2', focusElder.blood_oxygen)">
          <span class="focus-vt__label">血氧</span>
          <strong class="focus-vt__value">{{ focusElder.blood_oxygen ?? "--" }}<small>%</small></strong>
          <BulletBar
            :value="focusElder.blood_oxygen ?? null"
            :low="94"
            :high="100"
            :min="88"
            :max="100"
            unit="%"
            upper-open
          />
        </div>
        <div class="focus-vt" :class="vitalTone('temp', focusElder.temperature)">
          <span class="focus-vt__label">体温</span>
          <strong class="focus-vt__value">
            {{ focusElder.temperature != null ? focusElder.temperature.toFixed(1) : "--" }}<small>°C</small>
          </strong>
          <BulletBar
            :value="focusElder.temperature ?? null"
            :low="36"
            :high="37.2"
            :min="35.4"
            :max="38.4"
            unit="°C"
          />
        </div>
        <div class="focus-vt">
          <span class="focus-vt__label">血压</span>
          <strong class="focus-vt__value">{{ focusElder.blood_pressure ?? "--" }}<small>mmHg</small></strong>
          <span class="focus-vt__range">参考 &lt; 140/90</span>
        </div>
      </div>

      <footer class="focus-card__foot">
        <template v-if="focusElder.latest_health_score != null">
          <span class="focus-card__foot-label">健康分</span>
          <span class="focus-card__bar">
            <i :style="{ width: `${Math.min(Math.max(focusElder.latest_health_score, 0), 100)}%` }"></i>
          </span>
          <b class="focus-card__score">{{ Math.round(focusElder.latest_health_score) }}</b>
        </template>
        <span v-else class="focus-card__pending">等待首条体征数据后计算健康分</span>
      </footer>
    </article>

    <!-- 异常对象快捷条：仅在有需要关注的对象时出现 -->
    <div v-if="attentionElders.length" class="rail-attention">
      <span class="rail-attention__label">需关注</span>
      <button
        v-for="row in attentionElders"
        :key="row.elder.elder_id"
        type="button"
        class="rail-attention__chip"
        :class="`rail-attention__chip--${row.tone}`"
        :title="`切换到 ${row.elder.elder_name}`"
        @click="emit('select', row.elder.elder_id)"
      >
        {{ row.elder.elder_name }} · {{ row.text }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.device-rail {
  display: grid;
  gap: 18px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 24px;
  padding: 24px;
  box-shadow: 0 4px 16px rgba(15, 23, 42, 0.04);
}

.device-rail__head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding-bottom: 16px;
  border-bottom: 1px solid #e2e8f0;
}

.device-rail__head h2 {
  margin: 0;
  color: #0f172a;
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.device-rail__head small {
  color: #64748b;
  font-size: 0.88rem;
  line-height: 1.6;
  max-width: 480px;
}

.device-rail__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

/* ---------- 对象选择器 ---------- */
.rail-picker {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 12px 16px;
}

.rail-picker__field {
  flex: 1 1 260px;
  min-width: 0;
  display: grid;
  gap: 5px;
}

.rail-picker__field > span {
  font-size: var(--fs-0);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.rail-picker__field select {
  width: 100%;
  height: 38px;
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-strong);
  color: var(--text-main);
  font-size: var(--fs-2);
  font-family: inherit;
  cursor: pointer;
  outline: none;
}

.rail-picker__field select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

.rail-picker__nav {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.rail-picker__nav button {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-strong);
  color: var(--text-sub);
  cursor: pointer;
  transition: border-color 150ms ease, color 150ms ease;
}

.rail-picker__nav button:hover:not(:disabled) {
  border-color: var(--brand);
  color: var(--brand);
}

.rail-picker__nav button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.rail-picker__count {
  min-width: 54px;
  text-align: center;
  font-family: var(--font-mono);
  font-size: var(--fs-1);
  color: var(--text-muted);
}

/* ---------- 选中对象详情卡 ---------- */
.focus-card {
  --status: var(--risk-low);
  --status-soft: var(--surface-success);
  position: relative;
  display: grid;
  gap: 16px;
  padding: 20px 22px;
  border: 1px solid var(--line);
  border-left: 3px solid var(--status);
  border-radius: var(--radius-xl);
  background: var(--panel-strong);
  box-shadow: var(--shadow-sm);
}

.focus-card__top {
  display: flex;
  align-items: center;
  gap: 14px;
}

.focus-card__avatar {
  position: relative;
  flex-shrink: 0;
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: var(--status-soft);
  color: var(--status);
  font-size: var(--fs-3);
  font-weight: 700;
}

.focus-card__dot {
  position: absolute;
  right: 1px;
  bottom: 1px;
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: var(--surface-3);
  box-shadow: 0 0 0 2px var(--panel-strong);
}

.focus-card__dot--live {
  background: var(--status);
}

.focus-card__id {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 3px;
}

.focus-card__id strong {
  font-size: var(--fs-4);
  font-weight: 700;
  color: var(--text-main);
  letter-spacing: -0.01em;
}

.focus-card__id small {
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.focus-card__state {
  flex-shrink: 0;
  padding: 5px 13px;
  border-radius: 999px;
  background: var(--status-soft);
  color: var(--status);
  font-size: var(--fs-1);
  font-weight: 700;
  white-space: nowrap;
}

.focus-card__vitals {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.focus-vt {
  display: grid;
  gap: 6px;
  padding: 13px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  min-width: 0;
}

.focus-vt__label {
  font-size: var(--fs-1);
  color: var(--text-sub);
}

.focus-vt__value {
  font-family: var(--font-mono);
  font-size: var(--fs-4);
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.15;
}

.focus-vt__value small {
  margin-left: 3px;
  font-family: var(--font-main);
  font-size: var(--fs-1);
  font-weight: 600;
  color: var(--text-muted);
}

.focus-vt__range {
  font-size: var(--fs-0);
  color: var(--text-muted);
}

.focus-vt--warn {
  border-color: color-mix(in srgb, var(--risk-medium) 45%, transparent);
  background: var(--surface-warning);
}

.focus-vt--warn .focus-vt__value { color: var(--risk-medium); }

.focus-vt--bad {
  border-color: color-mix(in srgb, var(--risk-high) 45%, transparent);
  background: var(--surface-danger);
}

.focus-vt--bad .focus-vt__value { color: var(--risk-high); }

.focus-card__foot {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}

.focus-card__foot-label {
  font-size: var(--fs-1);
  color: var(--text-sub);
  flex-shrink: 0;
}

.focus-card__bar {
  flex: 1;
  height: 7px;
  border-radius: 999px;
  background: var(--surface-0);
  overflow: hidden;
}

.focus-card__bar i {
  display: block;
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--brand), var(--brand-2));
  transition: width 600ms cubic-bezier(0.22, 0.8, 0.3, 1);
}

.focus-card__score {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: var(--fs-3);
  font-weight: 700;
  color: var(--text-main);
}

.focus-card__pending {
  font-size: var(--fs-1);
  color: var(--text-muted);
}

/* ---------- 异常对象快捷条 ---------- */
.rail-attention {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  padding-top: 14px;
  border-top: 1px solid var(--line);
}

.rail-attention__label {
  font-size: var(--fs-0);
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--text-muted);
  margin-right: 2px;
}

.rail-attention__chip {
  padding: 5px 12px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-tinted);
  color: var(--text-sub);
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 150ms ease, border-color 150ms ease;
}

.rail-attention__chip:hover {
  transform: translateY(-1px);
}

.rail-attention__chip--warn {
  border-color: color-mix(in srgb, var(--risk-medium) 40%, transparent);
  background: var(--surface-warning);
  color: var(--risk-medium);
}

.rail-attention__chip--bad {
  border-color: color-mix(in srgb, var(--risk-high) 40%, transparent);
  background: var(--surface-danger);
  color: var(--risk-high);
}

.rail-attention__chip--sos {
  border-color: var(--risk-high);
  background: var(--surface-danger);
  color: var(--risk-high);
  animation: pulse-state 1.6s infinite;
}

/* ---------- 状态色调（由 elderTone 施加到 .focus-card） ---------- */
.risk-low {
  --status: var(--risk-low);
  --status-soft: var(--surface-success);
}

.risk-medium,
.pending {
  --status: var(--risk-medium);
  --status-soft: var(--surface-warning);
}

.risk-high,
.sos {
  --status: var(--risk-high);
  --status-soft: var(--surface-danger);
}

.offline,
.no-device {
  --status: var(--surface-3);
  --status-soft: var(--surface-soft);
}

.no-device {
  border-style: dashed;
}

.sos {
  animation: pulse-sos 2s infinite;
}

.sos .focus-card__state {
  animation: pulse-state 2s infinite;
}

@keyframes pulse-sos {
  0%, 100% {
    box-shadow: 0 0 0 3px rgba(197, 48, 48, 0.10), 0 8px 20px rgba(197, 48, 48, 0.18);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(197, 48, 48, 0.16), 0 12px 28px rgba(197, 48, 48, 0.28);
  }
}

@keyframes pulse-state {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.05); }
}

@media (max-width: 960px) {
  .device-rail {
    padding: 20px;
  }

  .device-rail__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .focus-card__vitals {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .device-rail {
    padding: 16px;
  }

  .focus-card__vitals {
    grid-template-columns: 1fr;
  }

  .rail-picker__nav {
    width: 100%;
    justify-content: space-between;
  }
}
</style>
