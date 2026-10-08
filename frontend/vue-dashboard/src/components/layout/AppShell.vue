<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { api, type AlarmRecord, type SessionUser } from "../../api/client";
import { focusCommunityWorkspaceDevice } from "../../composables/useCommunityWorkspace";
import type { PageKey } from "../../composables/useHashRouting";
import { useOverviewModals } from "../../composables/useOverviewModals";
import CommunitySosOverlay from "./CommunitySosOverlay.vue";
import FallAlertOverlay from "./FallAlertOverlay.vue";
import FamilyNav from "./FamilyNav.vue";
import GlobalHeader from "./GlobalHeader.vue";
import PrimaryNav from "./PrimaryNav.vue";
import ToolEntryMenu from "./ToolEntryMenu.vue";

const props = defineProps<{
  sessionUser: SessionUser;
  activePage: PageKey;
  allowedPages: PageKey[];
  canAccessDebug: boolean;
}>();

const emit = defineEmits<{
  logout: [];
  navigate: [page: PageKey];
}>();

/** 需要撑满可用高度、自己管内部滚动的页面（聊天式布局） */
const FILL_HEIGHT_PAGES: PageKey[] = ["agent"];

const overviewModals = useOverviewModals();

const activeAlarmCount = ref(0);
const activeRealtimeAlarms = ref<AlarmRecord[]>([]);
const simulatedAlarms = ref<AlarmRecord[]>([]);
const acknowledgingSos = ref(false);
const acknowledgingFall = ref(false);
const manuallyAcknowledging = ref(false);
const isCommunityWorkspace = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin",
);
const hasWorkspaceSidebar = computed(
  () => isCommunityWorkspace.value || props.sessionUser.role === "family",
);
const activeSosAlarms = computed(() =>
  activeRealtimeAlarms.value
    .filter((alarm) => !alarm.acknowledged && isRealSosAlarm(alarm))
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()),
);
const primarySosAlarm = computed(() => activeSosAlarms.value[0] ?? null);
const additionalSosCount = computed(() => Math.max(0, activeSosAlarms.value.length - 1));
const activeFallAlarms = computed(() =>
  activeRealtimeAlarms.value
    .filter((alarm) => !alarm.acknowledged && isFallAlarm(alarm))
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime()),
);
const primaryFallAlarm = computed(() => activeFallAlarms.value[0] ?? null);
const additionalFallCount = computed(() => Math.max(0, activeFallAlarms.value.length - 1));

let refreshTimer: number | null = null;
let alarmChannel: WebSocket | null = null;
let lastPresentedAlarmId = "";
let sosAudioElement: HTMLAudioElement | null = null;
let unlockAudioListenerBound = false;
let unlockAudioHandler: (() => void) | null = null;

function isRealSosAlarm(alarm: AlarmRecord) {
  return alarm.alarm_type === "sos" && !alarm.acknowledged && Boolean(alarm.metadata?.is_real_device);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function isFallAlarm(alarm: AlarmRecord) {
  if (!["fall_detected", "fall_injury_risk", "video_fall"].includes(alarm.alarm_type)) {
    return false;
  }
  const metadata = asRecord(alarm.metadata);
  return Boolean(asRecord(metadata?.event) || asRecord(metadata?.raw_event) || metadata);
}

function ensureSosAudioElement() {
  if (typeof window === "undefined") return null;
  if (!sosAudioElement) {
    const element = new Audio("/sounds/sos_alarm.ogg");
    element.loop = true;
    element.preload = "auto";
    element.volume = 1;
    sosAudioElement = element;
  }
  return sosAudioElement;
}

async function startSosToneLoop() {
  const audio = ensureSosAudioElement();
  if (!audio) return;
  if (!audio.paused) return;
  audio.currentTime = 0;
  try {
    await audio.play();
  } catch {
    // autoplay may be blocked before first interaction
  }
}

function stopSosToneLoop() {
  if (!sosAudioElement) return;
  sosAudioElement.pause();
  sosAudioElement.currentTime = 0;
}

function unlockSosAudio() {
  const audio = ensureSosAudioElement();
  if (!audio) return;
  void audio.play()
    .then(() => {
      audio.pause();
      audio.currentTime = 0;
    })
    .catch(() => undefined);
}

function bindAudioUnlockListeners() {
  if (typeof window === "undefined" || unlockAudioListenerBound) return;
  unlockAudioListenerBound = true;
  unlockAudioHandler = () => {
    unlockSosAudio();
    if (unlockAudioHandler) {
      window.removeEventListener("pointerdown", unlockAudioHandler);
      window.removeEventListener("keydown", unlockAudioHandler);
      window.removeEventListener("touchstart", unlockAudioHandler);
    }
    unlockAudioListenerBound = false;
    unlockAudioHandler = null;
  };
  window.addEventListener("pointerdown", unlockAudioHandler, { once: true, passive: true });
  window.addEventListener("keydown", unlockAudioHandler, { once: true });
  window.addEventListener("touchstart", unlockAudioHandler, { once: true, passive: true });
}

function syncAlarmState(alarms: AlarmRecord[]) {
  const realAlarms = alarms.filter((alarm) => !alarm.id.startsWith("sim_"));
  const allAlarms = [...realAlarms, ...simulatedAlarms.value];
  activeRealtimeAlarms.value = allAlarms
    .filter((alarm) => !alarm.acknowledged)
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  activeAlarmCount.value = activeRealtimeAlarms.value.length;
  presentPrimaryAlarm();
}

function upsertAlarm(alarm: AlarmRecord) {
  const next = [...activeRealtimeAlarms.value];
  const index = next.findIndex((item) => item.id === alarm.id);
  if (alarm.acknowledged) {
    if (index >= 0) next.splice(index, 1);
  } else if (index >= 0) {
    next.splice(index, 1, alarm);
  } else {
    next.push(alarm);
  }
  syncAlarmState(next);
}

function presentPrimaryAlarm() {
  const current = primarySosAlarm.value ?? primaryFallAlarm.value;
  if (!isCommunityWorkspace.value || !current) {
    return;
  }
  if (lastPresentedAlarmId !== current.id) {
    lastPresentedAlarmId = current.id;
    focusCommunityWorkspaceDevice(current.device_mac);
    if (props.activePage !== "overview") {
      emit("navigate", "overview");
    }
  }
}

/**
 * 顶栏铃铛：切到总览页并弹出告警队列。
 * 告警面板已改为弹窗，不再滚动定位；延时是等页面切换挂载完成后再开弹窗。
 */
function focusAlarmSection() {
  if (props.activePage !== "overview" && props.allowedPages.includes("overview")) {
    emit("navigate", "overview");
    window.setTimeout(() => overviewModals.openAlerts(), 260);
    return;
  }
  overviewModals.openAlerts();
}

function stopAlarmRuntime() {
  stopSosToneLoop();
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
  alarmChannel?.close();
  alarmChannel = null;
}

async function refreshAlarmState() {
  const alarms = await api.listAlarms().catch(() => [] as AlarmRecord[]);
  syncAlarmState(alarms);
}

function connectAlarmSocket() {
  alarmChannel?.close();
  alarmChannel = null;
  if (!isCommunityWorkspace.value) return;

  alarmChannel = api.alarmSocket();
  alarmChannel.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as AlarmRecord | { type?: string; queue?: Array<{ alarm?: AlarmRecord }> };
      if ("type" in payload && payload.type === "alarm_queue") {
        const alarms = Array.isArray(payload.queue)
          ? payload.queue
              .map((item) => item.alarm)
              .filter((item): item is AlarmRecord => Boolean(item))
          : [];
        syncAlarmState(alarms);
        return;
      }
      upsertAlarm(payload as AlarmRecord);
    } catch {
      // ignore malformed websocket payloads
    }
  };
  alarmChannel.onclose = () => {
    alarmChannel = null;
    setTimeout(() => {
      if (isCommunityWorkspace.value) connectAlarmSocket();
    }, 2000);
  };
}

function startAlarmRuntime() {
  stopAlarmRuntime();
  void refreshAlarmState();
  connectAlarmSocket();
  refreshTimer = window.setInterval(() => {
    void refreshAlarmState();
  }, 5000);
}

function handleSOSSimulation(event: CustomEvent) {
  if (!isCommunityWorkspace.value) return;
  const mockAlarm = event.detail as AlarmRecord;
  simulatedAlarms.value.push(mockAlarm);
  const realAlarms = activeRealtimeAlarms.value.filter((alarm) => !alarm.id.startsWith("sim_"));
  const allAlarms = [...realAlarms, ...simulatedAlarms.value];
  activeRealtimeAlarms.value = allAlarms
    .filter((alarm) => !alarm.acknowledged)
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
  activeAlarmCount.value = activeRealtimeAlarms.value.length;
  presentPrimaryAlarm();
}

watch(() => props.sessionUser.id, () => {
  startAlarmRuntime();
});

onMounted(() => {
  bindAudioUnlockListeners();
  startAlarmRuntime();
  window.addEventListener("sos-simulation", handleSOSSimulation as EventListener);
});

onUnmounted(() => {
  stopAlarmRuntime();
  if (unlockAudioListenerBound && unlockAudioHandler) {
    window.removeEventListener("pointerdown", unlockAudioHandler);
    window.removeEventListener("keydown", unlockAudioHandler);
    window.removeEventListener("touchstart", unlockAudioHandler);
  }
  unlockAudioListenerBound = false;
  unlockAudioHandler = null;
  if (sosAudioElement) {
    sosAudioElement.pause();
    sosAudioElement.src = "";
  }
  sosAudioElement = null;
});

async function acknowledgePrimarySos() {
  const current = primarySosAlarm.value;
  if (!current) return;
  manuallyAcknowledging.value = true;
  acknowledgingSos.value = true;
  stopSosToneLoop();
  try {
    if (current.id.startsWith("sim_")) {
      simulatedAlarms.value = simulatedAlarms.value.filter((alarm) => alarm.id !== current.id);
      const realAlarms = activeRealtimeAlarms.value.filter((alarm) => !alarm.id.startsWith("sim_"));
      const allAlarms = [...realAlarms, ...simulatedAlarms.value];
      activeRealtimeAlarms.value = allAlarms
        .filter((alarm) => !alarm.acknowledged)
        .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime());
      activeAlarmCount.value = activeRealtimeAlarms.value.length;
    } else {
      await api.ackAlarm(current.id);
      await refreshAlarmState();
    }
    lastPresentedAlarmId = "";
  } finally {
    acknowledgingSos.value = false;
    setTimeout(() => {
      manuallyAcknowledging.value = false;
    }, 100);
  }
}

async function acknowledgePrimaryFall() {
  const current = primaryFallAlarm.value;
  if (!current) return;
  acknowledgingFall.value = true;
  try {
    await api.ackAlarm(current.id);
    await refreshAlarmState();
    lastPresentedAlarmId = "";
  } finally {
    acknowledgingFall.value = false;
  }
}

watch(
  [primarySosAlarm, isCommunityWorkspace],
  ([alarm, canRing], [oldAlarm]) => {
    if (manuallyAcknowledging.value) {
      return;
    }
    if (!canRing || !alarm) {
      stopSosToneLoop();
      return;
    }
    if (!oldAlarm || alarm.id !== oldAlarm.id) {
      void startSosToneLoop();
    }
  },
  { immediate: true },
);
</script>

<template>
  <main class="app-shell" :class="{ 'app-shell--workspace': hasWorkspaceSidebar }">
    <aside v-if="hasWorkspaceSidebar" class="workspace-sidebar">
      <template v-if="isCommunityWorkspace">
        <PrimaryNav
          v-if="allowedPages.length"
          :active-page="activePage"
          :allowed-pages="allowedPages"
          :session-user="sessionUser"
          @navigate="emit('navigate', $event)"
        />

        <div class="workspace-sidebar__footer">
          <ToolEntryMenu
            v-if="canAccessDebug"
            :active-page="activePage"
            :can-access-debug="canAccessDebug"
            @navigate="emit('navigate', $event)"
          />
          <span class="workspace-sidebar__version">v2.4.1</span>
        </div>
      </template>

      <template v-else>
        <FamilyNav :session-user="sessionUser" />
        <div class="workspace-sidebar__footer">
          <span class="workspace-sidebar__version">v2.4.1</span>
        </div>
      </template>
    </aside>

    <div class="workspace-stage">
      <GlobalHeader
        :session-user="sessionUser"
        :active-alarm-count="activeAlarmCount"
        @logout="emit('logout')"
        @focus-alarms="focusAlarmSection"
      />

      <div
        v-if="!hasWorkspaceSidebar && allowedPages.length"
        class="app-shell__controls"
      >
        <PrimaryNav
          :active-page="activePage"
          :allowed-pages="allowedPages"
          @navigate="emit('navigate', $event)"
        />
        <ToolEntryMenu
          v-if="canAccessDebug"
          :active-page="activePage"
          :can-access-debug="canAccessDebug"
          @navigate="emit('navigate', $event)"
        />
      </div>

      <div
        class="app-shell__content"
        :class="{ 'app-shell__content--fill': FILL_HEIGHT_PAGES.includes(activePage) }"
      >
        <slot />
      </div>
    </div>

    <CommunitySosOverlay
      v-if="isCommunityWorkspace"
      :alarm="primarySosAlarm"
      :additional-count="additionalSosCount"
      :acknowledging="acknowledgingSos"
      @acknowledge="acknowledgePrimarySos"
    />
    <FallAlertOverlay
      v-if="isCommunityWorkspace && !primarySosAlarm"
      :alarm="primaryFallAlarm"
      :additional-count="additionalFallCount"
      :acknowledging="acknowledgingFall"
      @acknowledge="acknowledgePrimaryFall"
    />
  </main>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  width: 100%;
  background: var(--bg-base);
}

.app-shell--workspace {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.workspace-sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: 260px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 12px;
  background: var(--panel-strong);
  border-right: 1px solid var(--line);
  overflow: hidden auto;
  z-index: 100;
}

.workspace-sidebar__footer {
  margin-top: auto;
  padding-top: 14px;
  border-top: 1px solid var(--line);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.workspace-sidebar__version {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-muted);
  text-align: right;
  padding-right: 4px;
}

.workspace-stage {
  flex: 1;
  margin-left: 260px;
  width: calc(100% - 260px);
  height: 100vh;
  overflow-y: auto;
  overflow-x: hidden;
  display: flex;
  flex-direction: column;
  gap: 18px;
  padding: 14px 20px 32px;
}

.workspace-stage::-webkit-scrollbar {
  width: 8px;
}

.workspace-stage::-webkit-scrollbar-track {
  background: transparent;
}

.workspace-stage::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 4px;
}

.workspace-stage::-webkit-scrollbar-thumb:hover {
  background: rgba(148, 163, 184, 0.5);
}

.app-shell__controls {
  display: flex;
  justify-content: space-between;
  gap: 14px;
  align-items: flex-start;
}

.app-shell__content {
  flex: 1;
  width: 100%;
  min-height: 0;
}

/*
 * 全局 .app-shell__content 用 align-content:start 把面板顶到上方，
 * 代价是隐式网格行按内容高度收缩。聊天式页面需要撑满可用高度才能把输入框
 * 固定在底边，因此按页面切到 stretch —— 不要改全局值，其他页面依赖 start。
 */
.app-shell__content--fill {
  align-content: stretch;
}

@media (max-width: 960px) {
  .app-shell--workspace {
    flex-direction: column;
    height: auto;
    overflow: visible;
  }

  .workspace-sidebar {
    position: static;
    width: 100%;
    height: auto;
    border-right: none;
    border-bottom: 1px solid var(--line);
  }

  .workspace-stage {
    margin-left: 0;
    width: 100%;
    height: auto;
    overflow: visible;
  }
}
</style>
