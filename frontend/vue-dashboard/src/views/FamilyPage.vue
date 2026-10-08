<script setup lang="ts">
import { computed, onMounted, ref, toRef, watch } from "vue";
import type {
  AgentDeviceHealthReport,
  CareAccessProfile,
  CareHealthEvaluationSummary,
  CareHealthReportSummary,
  HealthSample,
  SessionUser,
} from "../api/client";
import { ApiError, api, getFamilyCameraStreamUrl, getVisionHealthEndpoint } from "../api/client";
import AlarmEscalationPanel from "../components/AlarmEscalationPanel.vue";
import AssistantPanel from "../components/AssistantPanel.vue";
import HealthEvaluationPanel from "../components/HealthEvaluationPanel.vue";
import PageHeader from "../components/layout/PageHeader.vue";
import BulletBar from "../components/viz/BulletBar.vue";
import DeltaChip from "../components/viz/DeltaChip.vue";
import MiniSparkline from "../components/viz/MiniSparkline.vue";
import { useCareDirectoryDashboard } from "../composables/useCareDirectoryDashboard";
import { useCountUp } from "../composables/useCountUp";
import { useDeviceTrend } from "../composables/useDeviceTrend";
import { useFamilySection } from "../composables/useFamilySection";
import { evaluateRisk, riskLabel, type RiskLevel } from "../domain/careModel";

type DemoTone = "neutral" | "stable" | "warning" | "critical";

interface ElderRow {
  id: string;
  name: string;
  apartment: string;
  deviceMac: string;
  familyNames: string;
  risk: RiskLevel;
  sample: HealthSample | null;
}

interface SnapshotMetric {
  id: string;
  shortLabel: string;
  label: string;
  value: string;
  unit: string;
  note: string;
  tone: DemoTone;
  /** 参考区间定位条配置；无临床区间的指标（如告警状态）为 null */
  bullet?: {
    value: number | null;
    low: number;
    high: number;
    min?: number;
    max?: number;
    unit?: string;
    upperOpen?: boolean;
  } | null;
}

const props = defineProps<{
  sessionUser: SessionUser;
}>();

const sessionUser = toRef(props, "sessionUser");
const {
  alarms,
  allFamilies: allFamiliesRaw,
  dashboardLoadError,
  dashboardLoading,
  devices,
  elders,
  lastSyncAt,
  latest,
} = useCareDirectoryDashboard(sessionUser);

const selectedFamilyId = ref("");
const selectedDeviceMac = ref("");
const accessProfile = ref<CareAccessProfile | null>(null);
const generatedHealthReport = ref<AgentDeviceHealthReport | null>(null);
const reportLoading = ref(false);
const reportError = ref("");

const { focusLatest, focusTrend } = useDeviceTrend({
  selectedDeviceMac,
  latest,
  pollIntervalMs: 15000,
});

const families = computed(() =>
  sessionUser.value.role === "family"
    ? allFamiliesRaw.value.filter((family) => family.id === sessionUser.value.family_id)
    : allFamiliesRaw.value,
);
const selectedFamily = computed(() =>
  families.value.find((family) => family.id === selectedFamilyId.value) ?? families.value[0] ?? null,
);
const elderRows = computed<ElderRow[]>(() =>
  elders.value.map((elder) => {
    const rawDeviceMac = elder.device_macs?.[0] ?? elder.device_mac ?? "";
    const deviceRecord = rawDeviceMac
      ? devices.value.find((device) => device.mac_address === rawDeviceMac) ?? null
      : null;
    const exposeDevice =
      deviceRecord != null
        ? deviceRecord.ingest_mode === "mock" || deviceRecord.bind_status === "bound"
        : false;
    const deviceMac = exposeDevice ? rawDeviceMac : "";
    const sample = deviceMac ? latest.value[deviceMac] ?? null : null;
    const risk = evaluateRisk(
      sample,
      deviceMac ? (deviceRecord?.status ?? "unknown") : "unbound",
    );
    const familyNames = elder.family_ids
      .map((id) => allFamiliesRaw.value.find((family) => family.id === id)?.name)
      .filter(Boolean)
      .join(" / ");
    return { id: elder.id, name: elder.name, apartment: elder.apartment, deviceMac, familyNames, risk, sample };
  }),
);
const visibleRows = computed(() =>
  sessionUser.value.role === "family" && selectedFamily.value
    ? elderRows.value.filter((row) => new Set(selectedFamily.value.elder_ids ?? []).has(row.id))
    : elderRows.value,
);
const focusRow = computed(
  () =>
    visibleRows.value.find((row) => row.deviceMac === selectedDeviceMac.value)
    ?? elderRows.value.find((row) => row.deviceMac === selectedDeviceMac.value)
    ?? null,
);
const focusAlarm = computed(
  () => alarms.value.find((alarm) => !alarm.acknowledged && alarm.device_mac === selectedDeviceMac.value) ?? null,
);
const currentHealthEvaluation = computed<CareHealthEvaluationSummary | null>(() => {
  if (!selectedDeviceMac.value || !accessProfile.value) return null;
  return accessProfile.value.health_evaluations.find((item) => item.device_mac === selectedDeviceMac.value) ?? null;
});
const currentHealthReportSummary = computed<CareHealthReportSummary | null>(() => {
  if (!selectedDeviceMac.value || !accessProfile.value) return null;
  return accessProfile.value.health_reports.find((item) => item.device_mac === selectedDeviceMac.value) ?? null;
});
const hasBoundDevice = computed(() => {
  if (sessionUser.value.role === "family") {
    return visibleRows.value.some((row) => Boolean(row.deviceMac));
  }
  return Boolean(focusRow.value?.deviceMac);
});
const focusRiskLabel = computed(() => (focusRow.value ? riskLabel(focusRow.value.risk) : "未选择对象"));
const focusTone = computed<DemoTone>(() => {
  if (!hasBoundDevice.value) return "neutral";
  if (focusAlarm.value) return "critical";
  if (focusRow.value?.risk === "high" || focusRow.value?.risk === "medium") return "warning";
  if (focusRow.value?.risk === "low") return "stable";
  return "neutral";
});
const focusUpdatedLabel = computed(() =>
  displayFocusLatest.value ? new Date(displayFocusLatest.value.timestamp).toLocaleString("zh-CN", { hour12: false }) : "尚未同步",
);
const focusSummaryTitle = computed(() => {
  if (!hasBoundDevice.value) return "当前家属还没有绑定设备";
  if (focusAlarm.value) return "已出现需要优先处理的告警";
  if (focusRow.value?.risk === "high") return "健康风险偏高，需要尽快跟进";
  if (focusRow.value?.risk === "medium") return "近期状态有波动，建议继续观察";
  if (focusRow.value?.risk === "low") return "当前状态总体平稳";
  return "等待更多同步数据";
});
const focusSummaryCopy = computed(() => {
  if (!hasBoundDevice.value) {
    return "当前还没有可用设备，请先确认家属关系和设备绑定状态。";
  }
  if (!displayFocusLatest.value) {
    return "已识别到绑定关系，但当前设备还没有可用的实时数据。请确认设备在线状态和最近同步情况。";
  }

  const metrics = `心率 ${displayFocusLatest.value.heart_rate} bpm，血氧 ${displayFocusLatest.value.blood_oxygen}%，体温 ${displayFocusLatest.value.temperature.toFixed(1)}°C`;

  if (focusAlarm.value) {
    return `${focusAlarm.value.message}。当前关键指标为 ${metrics}，建议先查看告警升级建议，再决定是否联系社区人员处理。`;
  }
  if (focusRow.value?.risk === "high") {
    return `当前对象综合风险为高，最近同步指标为 ${metrics}。建议尽快补充观察、生成正式报告并结合家属照护安排做进一步判断。`;
  }
  if (focusRow.value?.risk === "medium") {
    return `当前对象存在中度波动，最近同步指标为 ${metrics}。建议继续观察趋势变化，并结合健康评估结果决定是否需要人工干预。`;
  }
  return `最近同步指标为 ${metrics}。整体趋势相对平稳，可继续保持日常观察并关注后续波动。`;
});
const familyTrendPreview = computed(() => focusTrend.value.slice(-4).reverse());
const displayFocusLatest = computed(() => focusLatest.value ?? focusRow.value?.sample ?? null);
const familyTrendHeadline = computed(() => {
  if (!familyTrendPreview.value.length) {
    return "选中的设备还没有可展示的趋势片段，后续同步后会在这里展示最近的变化轨迹。";
  }

  const latestPoint = familyTrendPreview.value[0];
  const oldestPoint = familyTrendPreview.value[familyTrendPreview.value.length - 1];
  const latestScore = latestPoint.health_score ?? null;
  const oldestScore = oldestPoint.health_score ?? null;

  if (latestScore !== null && oldestScore !== null) {
    if (latestScore - oldestScore >= 5) return "最近几个采样点的健康分有回升趋势，短期状态正在改善。";
    if (oldestScore - latestScore >= 5) return "最近几个采样点的健康分有下降趋势，建议关注后续变化。";
  }

  return "最近同步的几个采样点整体波动有限，可以继续结合实时指标与评估结果做判断。";
});
const familySnapshotCards = computed<SnapshotMetric[]>(() => {
  const sample = displayFocusLatest.value;
  return [
    {
      id: "heart-rate",
      shortLabel: "HR",
      label: "心率",
      value: sample ? String(sample.heart_rate) : "--",
      unit: "bpm",
      note: sample
        ? sample.heart_rate >= 110 || sample.heart_rate <= 45
          ? "心率超出稳态区间，建议重点关注。"
          : "心率处于可接受范围。"
        : "等待实时数据同步。",
      tone: sample && (sample.heart_rate >= 110 || sample.heart_rate <= 45) ? "warning" : "stable",
      bullet: { value: sample?.heart_rate ?? null, low: 60, high: 100 },
    },
    {
      id: "blood-oxygen",
      shortLabel: "SpO2",
      label: "血氧",
      value: sample ? String(sample.blood_oxygen) : "--",
      unit: "%",
      note: sample ? (sample.blood_oxygen < 93 ? "血氧偏低，建议尽快查看告警与趋势。" : "血氧状态相对稳定。") : "等待实时数据同步。",
      tone: sample && sample.blood_oxygen < 93 ? "critical" : "stable",
      bullet: {
        value: sample?.blood_oxygen ?? null,
        low: 94,
        high: 100,
        min: 88,
        max: 100,
        unit: "%",
        upperOpen: true,
      },
    },
    {
      id: "temperature",
      shortLabel: "TEMP",
      label: "体温",
      value: sample ? sample.temperature.toFixed(1) : "--",
      unit: "°C",
      note: sample ? (sample.temperature >= 37.8 ? "体温偏高，需要继续观察。" : "体温状态平稳。") : "等待实时数据同步。",
      tone: sample && sample.temperature >= 37.8 ? "warning" : "stable",
      bullet: {
        value: sample?.temperature ?? null,
        low: 36,
        high: 37.2,
        min: 35.4,
        max: 38.4,
        unit: "°C",
      },
    },
    {
      id: "battery",
      shortLabel: "BAT",
      label: "设备电量",
      value: sample?.battery !== null && sample?.battery !== undefined ? String(sample.battery) : "--",
      unit: "%",
      note:
        sample?.battery !== null && sample?.battery !== undefined
          ? sample.battery <= 20
            ? "电量偏低，建议尽快充电。"
            : "设备电量正常。"
          : "尚未获取设备电量。",
      tone:
        sample?.battery !== null && sample?.battery !== undefined
          ? sample.battery <= 20
            ? "warning"
            : "stable"
          : "neutral",
    },
    {
      id: "health-score",
      shortLabel: "SCORE",
      label: "健康分",
      value:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? String(Math.round(sample.health_score))
          : "--",
      unit: "分",
      note:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? sample.health_score < 60
            ? "健康分偏低，建议生成正式报告。"
            : "健康分处于可观察区间。"
          : "等待健康分同步。",
      tone:
        sample?.health_score !== null && sample?.health_score !== undefined
          ? sample.health_score < 60
            ? "warning"
            : "stable"
          : "neutral",
    },
    {
      id: "alarm-stage",
      shortLabel: "ALERT",
      label: "告警状态",
      value: focusAlarm.value ? "处理中" : "无活动告警",
      unit: "",
      note: focusAlarm.value?.message ?? "当前没有活动告警，仍建议持续关注实时状态变化。",
      tone: focusAlarm.value ? "critical" : "stable",
    },
  ];
});
const syncLabel = computed(() =>
  lastSyncAt.value ? lastSyncAt.value.toLocaleTimeString("zh-CN", { hour12: false }) : "尚未同步",
);
const pageMeta = computed(() => [
  `家属 ${selectedFamily.value?.name || "未选择"}`,
  `对象 ${focusRow.value?.name || "未选择"}`,
  `设备 ${selectedDeviceMac.value || "未绑定"}`,
  `同步 ${syncLabel.value}`,
]);

function sessionToken() {
  return localStorage.getItem("ai_health_demo_session_token") ?? "";
}

function formatUiError(error: unknown, fallback: string) {
  if (error instanceof ApiError && error.detail) return error.detail;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

async function refreshAccessProfile() {
  if (sessionUser.value.role !== "family" && sessionUser.value.role !== "elder") {
    accessProfile.value = null;
    return;
  }

  accessProfile.value = await api.getCareAccessProfile(sessionToken()).catch(() => null);
}

async function generateHealthReport() {
  if (!selectedDeviceMac.value) {
    reportError.value = "请先选择一个已绑定设备，再生成正式健康报告。";
    return;
  }

  reportLoading.value = true;
  reportError.value = "";
  generatedHealthReport.value = null;

  try {
    const endAt = new Date();
    const startAt = new Date(endAt.getTime() - 24 * 60 * 60 * 1000);
    generatedHealthReport.value = await api.generateDeviceHealthReport({
      device_mac: selectedDeviceMac.value,
      start_at: startAt.toISOString(),
      end_at: endAt.toISOString(),
      role: "family",
      mode: "qwen",
    });
  } catch (error) {
    reportError.value = formatUiError(error, "正式健康报告生成失败，请稍后重试。");
  } finally {
    reportLoading.value = false;
  }
}

watch(
  families,
  (list) => {
    if (!list.length) {
      selectedFamilyId.value = "";
      return;
    }
    if (!list.some((item) => item.id === selectedFamilyId.value)) {
      selectedFamilyId.value = list[0].id;
    }
  },
  { immediate: true },
);

watch(
  visibleRows,
  (list) => {
    if (!list.length) {
      selectedDeviceMac.value = "";
      return;
    }
    if (!list.some((item) => item.deviceMac === selectedDeviceMac.value)) {
      selectedDeviceMac.value = list.find((item) => item.deviceMac)?.deviceMac ?? "";
    }
  },
  { immediate: true },
);

watch(selectedDeviceMac, () => {
  generatedHealthReport.value = null;
  reportError.value = "";
});

watch(
  lastSyncAt,
  () => {
    void refreshAccessProfile();
  },
  { immediate: true },
);

function riskClass(level: RiskLevel) {
  return `risk-${level}`;
}

function updateFamilyId(event: Event) {
  selectedFamilyId.value = (event.target as HTMLSelectElement).value;
}

/* 侧栏分区（状态由 AppShell 侧栏的 FamilyNav 驱动） */
const { activeSection } = useFamilySection();

/* 今日照护提示：由告警/风险/电量真实状态推导，末尾静态兜底 */
const careTips = computed(() => {
  const tips: Array<{ tone: "danger" | "warn" | "ok"; title: string; body: string }> = [];
  if (focusAlarm.value) {
    tips.push({
      tone: "danger",
      title: "优先处理当前告警",
      body: `${focusAlarm.value.message}。建议先查看告警动态分区的升级建议，再决定是否联系社区。`,
    });
  }
  const risk = focusRow.value?.risk;
  if (risk === "high" || risk === "medium") {
    tips.push({
      tone: "warn",
      title: "建议今天复测体征",
      body: "近期指标有波动，建议安排一次血氧与心率复测，并在健康报告分区生成最新报告。",
    });
  }
  const battery = displayFocusLatest.value?.battery;
  if (battery != null && battery <= 30) {
    tips.push({
      tone: "warn",
      title: "手环需要充电",
      body: `当前电量 ${battery}%，建议今晚为手环充电，保证夜间监测不中断。`,
    });
  }
  tips.push({
    tone: "ok",
    title: "保持日常陪伴",
    body: "天气适宜时安排 20–30 分钟散步，注意补水；有不适主诉及时提高关注等级。",
  });
  return tips.slice(0, 3);
});

/* 跌倒告警：来自视觉跌倒检测链路的告警类型 */
const FALL_ALARM_TYPES = new Set(["fall_detected", "fall_injury_risk", "video_fall"]);

function fallConfidence(alarm: { anomaly_probability?: number | null; metadata?: Record<string, unknown> }) {
  const meta = alarm.metadata ?? {};
  const event = (meta.event ?? meta.raw_event ?? meta) as Record<string, unknown>;
  const raw = event?.fall_score ?? event?.fall_prob ?? alarm.anomaly_probability;
  const value = typeof raw === "number" ? raw : null;
  if (value == null) return null;
  return Math.round((value <= 1 ? value * 100 : value));
}

function fallSnapshotUrl(alarm: { metadata?: Record<string, unknown> }) {
  const meta = alarm.metadata ?? {};
  const event = (meta.event ?? meta.raw_event ?? meta) as Record<string, unknown>;
  const url = event?.snapshot_url;
  // 相对路径指向视觉服务内部，浏览器无法直接解析，只展示绝对地址
  return typeof url === "string" && url.startsWith("http") ? url : null;
}

/**
 * 视觉大模型对关键帧的复核结论。
 * 当前后端只写入 { enabled } 状态位、尚未接真实 VL 复核，所以有结论时才渲染；
 * 接上之后 conclusion / reason 会自动出现，无需再改这里。
 */
function fallReview(alarm: { metadata?: Record<string, unknown> }) {
  const meta = alarm.metadata ?? {};
  const event = (meta.event ?? meta.raw_event ?? meta) as Record<string, unknown>;
  const review = event?.multimodal_review;
  if (!review || typeof review !== "object") return null;

  const row = review as Record<string, unknown>;
  const conclusion = typeof row.conclusion === "string" ? row.conclusion.trim() : "";
  const verdict = typeof row.verdict === "string" ? row.verdict.trim() : "";
  const reason = typeof row.reason === "string" ? row.reason.trim() : "";
  const label = conclusion || verdict;
  if (!label) return null;   // 只有 enabled 状态位时不显示

  const confirmed = !/误报|false|not_?fall|no_?fall/i.test(label);
  return { label, reason, confirmed };
}

/**
 * 视觉跌倒告警挂在摄像头伪 MAC 上，对象绑定在 metadata.elder_id / family_ids，
 * 因此归属判断必须同时覆盖手环 MAC 与 metadata 两条路径。
 */
function alarmBelongsToFamily(alarm: { device_mac: string; metadata?: Record<string, unknown> }) {
  const macs = new Set(visibleRows.value.map((row) => row.deviceMac).filter(Boolean));
  if (macs.has(alarm.device_mac)) return true;
  const meta = alarm.metadata ?? {};
  const familyIds = Array.isArray(meta.family_ids) ? (meta.family_ids as unknown[]) : [];
  const currentFamilyId = sessionUser.value.family_id;
  if (currentFamilyId && familyIds.includes(currentFamilyId)) return true;
  const elderIds = new Set(visibleRows.value.map((row) => row.id));
  if (typeof meta.elder_id === "string" && elderIds.has(meta.elder_id)) return true;
  return false;
}

const fallAlarms = computed(() =>
  alarms.value
    .filter((alarm) => FALL_ALARM_TYPES.has(alarm.alarm_type) && alarmBelongsToFamily(alarm))
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
    .slice(0, 10),
);

const activeFallAlarm = computed(() => fallAlarms.value.find((alarm) => !alarm.acknowledged) ?? null);

/*
 * 跌倒时刻的体征切片：跨模态关联的界面呈现。
 * 摄像头给"什么时候摔的"，手环给"当时身体什么状况"，两者靠时间戳对齐——
 * 让家属能直观看到心率是否骤升（应激反应），而不是只看到一句告警文字。
 */
const FALL_VITALS_SPAN_MINUTES = 10;

const fallVitalsWindow = computed(() => {
  const alarm = fallAlarms.value[0];
  if (!alarm) return null;

  const center = new Date(alarm.created_at).getTime();
  const span = FALL_VITALS_SPAN_MINUTES * 60 * 1000;
  const samples = focusTrend.value.filter((item) => {
    const at = new Date(item.timestamp).getTime();
    return at >= center - span && at <= center + span;
  });
  if (samples.length < 2) return null;   // 一两个点画不出趋势，不如不显示

  const heartRates = samples.map((item) => item.heart_rate).filter((v) => Number.isFinite(v));
  const baseline = heartRates.length ? heartRates[0] : null;
  const peak = heartRates.length ? Math.max(...heartRates) : null;

  return {
    alarm,
    occurredAt: alarm.created_at,
    samples,
    heartRates,
    bloodOxygen: samples.map((item) => item.blood_oxygen).filter((v) => Number.isFinite(v)),
    // 心率相对起点的抬升幅度，用于判断有无应激反应
    surge: baseline != null && peak != null ? Math.round(peak - baseline) : null,
    peak,
  };
});

/* 视觉服务在线状态与家属摄像头画面 */
const visionOnline = ref<boolean | null>(null);

/* 画面双源：优先直连 Go2 机器狗前置摄像头（与 Vision 检测同源），失败回落主系统家属通道 */
const GO2_STREAM_URL = "http://192.0.2.32:8093/stream.mjpg";
type CameraSource = "go2" | "family" | "failed";
const cameraSource = ref<CameraSource>("go2");

const cameraStreamUrl = computed(() =>
  cameraSource.value === "go2" ? GO2_STREAM_URL : getFamilyCameraStreamUrl(),
);

const cameraSourceLabel = computed(() => {
  if (cameraSource.value === "go2") return "机器狗视角 · 直连";
  if (cameraSource.value === "family") return "主系统家属通道";
  return "画面不可用";
});

function handleStreamError() {
  if (cameraSource.value === "go2") {
    cameraSource.value = "family";
    return;
  }
  cameraSource.value = "failed";
}

async function probeVisionService() {
  try {
    const response = await fetch(getVisionHealthEndpoint());
    const data = (await response.json().catch(() => null)) as { status?: string } | null;
    visionOnline.value = response.ok && data?.status === "ok";
  } catch {
    visionOnline.value = false;
  }
}

onMounted(() => {
  void probeVisionService();
});

watch(activeSection, (section) => {
  if (section === "fall") {
    void probeVisionService();
    cameraSource.value = "go2";
  }
});

/* 应急处置指引：家属发现跌倒后的标准四步 */
const fallGuideSteps = [
  { title: "保持冷静，不要立即扶起", body: "先观察老人意识与体位，贸然扶起可能加重骨折或脊柱损伤。" },
  { title: "确认意识与呼吸", body: "呼唤老人并观察胸廓起伏；如无反应或呼吸异常，立即拨打 120。" },
  { title: "联系社区值守", body: "通过平台告警或电话通知社区值守人员，说明位置与老人状态。" },
  { title: "记录经过并陪同观察", body: "记录跌倒时间与经过，即使起身无碍也建议 24 小时内留意头晕、疼痛等症状。" },
];

/* 家人告警记录：手环告警按 MAC 归属，视觉告警按 metadata 归属 */
const familyAlarms = computed(() =>
  alarms.value
    .filter((alarm) => alarmBelongsToFamily(alarm))
    .sort((left, right) => new Date(right.created_at).getTime() - new Date(left.created_at).getTime())
    .slice(0, 8),
);

/* 设备台账：家人 → 设备状态/电量 */
const familyDevices = computed(() =>
  visibleRows.value.map((row) => {
    const device = row.deviceMac
      ? devices.value.find((item) => item.mac_address === row.deviceMac) ?? null
      : null;
    const online = device ? device.status !== "offline" : false;
    return {
      elderId: row.id,
      elderName: row.name,
      apartment: row.apartment,
      mac: row.deviceMac,
      bound: Boolean(row.deviceMac),
      online,
      statusText: !row.deviceMac ? "未绑定设备" : online ? "在线" : "离线",
      battery: row.sample?.battery ?? null,
      lastSeen: row.sample?.timestamp
        ? new Date(row.sample.timestamp).toLocaleString("zh-CN", { hour12: false })
        : "尚未同步",
    };
  }),
);

/* 安心指数环 */
const RING_CIRCUMFERENCE = 289;
const familyRingScore = useCountUp(
  computed(() => {
    const score = displayFocusLatest.value?.health_score;
    return score != null && Number.isFinite(score) ? Math.round(score) : null;
  }),
);
const familyRingOffset = computed(() => {
  const score = familyRingScore.value;
  if (score == null) return RING_CIRCUMFERENCE;
  return RING_CIRCUMFERENCE - (RING_CIRCUMFERENCE * Math.min(Math.max(score, 0), 100)) / 100;
});

/*
 * Hero 主 KPI：健康分近期轨迹（按时间正序，与 familyTrendPreview 的倒序区分）。
 * 与社区端同理，0 分代表该次采样没有算出健康分，入图会造出假涨幅，需剔除。
 */
const familyScoreSeries = computed(() =>
  focusTrend.value
    .map((point) => point.health_score)
    .filter((score): score is number => score != null && Number.isFinite(score) && score > 0),
);

const familyScoreDelta = computed(() => {
  const series = familyScoreSeries.value;
  if (series.length < 2) return null;
  return series[series.length - 1] - series[0];
});

/* Hero 次级卡：三项体征 + 设备电量，正好填满主卡右侧 2×2 网格；健康分已由主卡承担 */
const familyHeroSecondaryCards = computed(() =>
  ["heart-rate", "blood-oxygen", "temperature", "battery"]
    .map((id) => familySnapshotCards.value.find((card) => card.id === id))
    .filter((card): card is SnapshotMetric => card != null),
);

const familyScoreNote = computed(() => {
  const count = familyScoreSeries.value.length;
  if (!count) return "等待健康分同步。";
  if (count < 2) return "已收到首个健康分，继续观察趋势。";
  return `近 ${count} 次采样轨迹`;
});
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="家属照护视图"
      title="家属视图"
      description="查看家人的实时健康状况、体征趋势、健康报告与告警动态。"
      :meta="pageMeta"
    />

    <p v-if="dashboardLoadError" class="feedback-banner feedback-error">{{ dashboardLoadError }}</p>

    <div v-else-if="dashboardLoading && !visibleRows.length" class="state-block state-loading">
      <strong>正在加载家属视图</strong>
      <p>页面会在数据到位后展示绑定对象、实时摘要、健康评估和正式报告入口。</p>
    </div>

    <section v-else class="fam-stage stage-enter">
      <!-- 当前对象条：所有分区常驻 -->
      <section class="panel fam-focus-bar">
        <div class="fam-focus-bar__who">
          <span class="fam-focus-bar__avatar">{{ focusRow?.name.slice(0, 1) ?? "?" }}</span>
          <span class="fam-focus-bar__id">
            <strong>{{ focusRow?.name ?? "未选择对象" }}</strong>
            <small>{{ focusRow?.apartment ?? "--" }}{{ selectedDeviceMac ? " · T10 手环" : " · 未绑定设备" }}</small>
          </span>
          <span class="fam-elder-card__badge" :class="riskClass(focusRow?.risk ?? 'low')">
            {{ hasBoundDevice ? focusRiskLabel : "待同步" }}
          </span>
        </div>

        <div class="fam-focus-bar__switch">
          <button
            v-for="row in visibleRows"
            :key="row.id"
            type="button"
            class="fam-focus-pill"
            :class="{ 'fam-focus-pill--active': row.deviceMac === selectedDeviceMac && Boolean(row.deviceMac) }"
            @click="selectedDeviceMac = row.deviceMac"
          >
            {{ row.name }}
          </button>
        </div>

        <label class="fam-select">
          <span>当前家属</span>
          <select :value="selectedFamilyId" @change="updateFamilyId">
            <option v-for="family in families" :key="family.id" :value="family.id">
              {{ family.name }} / {{ family.relationship }}
            </option>
          </select>
        </label>
      </section>

      <!-- ═══ 分区 1：今日安心 ═══ -->
      <section v-if="activeSection === 'overview'" class="panel fam-hero">
        <div class="fam-hero__score">
          <div class="fam-ring">
            <svg width="108" height="108" viewBox="0 0 108 108">
              <circle class="fam-ring__track" cx="54" cy="54" r="46" />
              <circle
                class="fam-ring__bar"
                :class="`fam-ring__bar--${focusTone}`"
                cx="54"
                cy="54"
                r="46"
                :style="{ strokeDashoffset: familyRingOffset }"
              />
            </svg>
            <div class="fam-ring__val">
              <b>{{ familyRingScore ?? "--" }}</b>
              <span>{{ focusRow?.name ?? "未选择" }} · 健康分</span>
            </div>
          </div>
          <div class="fam-hero__meta">
            <h2>{{ focusSummaryTitle }}</h2>
            <p>{{ focusSummaryCopy }}</p>
            <div class="fam-hero__tags">
              <span class="fam-tag" :class="focusAlarm ? 'fam-tag--danger' : 'fam-tag--ok'">
                {{ hasBoundDevice ? focusRiskLabel : "未绑定设备" }}
              </span>
              <span class="fam-tag fam-tag--muted">房间 {{ focusRow?.apartment ?? "--" }}</span>
              <span class="fam-tag fam-tag--muted">更新 {{ focusUpdatedLabel }}</span>
            </div>
          </div>
        </div>

        <div class="fam-hero__kpis">
          <!-- 主 KPI：健康分跨列 + 近期轨迹，主次分明 -->
          <article class="fam-kpi fam-kpi--primary" :class="`fam-kpi--${focusTone}`">
            <div class="fam-kpi__top">
              <span class="fam-kpi__label">健康分</span>
              <DeltaChip :delta="familyScoreDelta" />
            </div>
            <span class="fam-kpi__value fam-kpi__value--lg">
              {{ familyRingScore ?? "--" }}<small>分</small>
            </span>
            <MiniSparkline v-if="familyScoreSeries.length > 1" :values="familyScoreSeries" :height="32" />
            <span class="fam-kpi__note">{{ familyScoreNote }}</span>
          </article>

          <article
            v-for="card in familyHeroSecondaryCards"
            :key="card.id"
            class="fam-kpi"
            :class="`fam-kpi--${card.tone}`"
          >
            <span class="fam-kpi__label">{{ card.label }}</span>
            <span class="fam-kpi__value">{{ card.value }}<small>{{ card.unit }}</small></span>
            <BulletBar
              v-if="card.bullet"
              :value="card.bullet.value"
              :low="card.bullet.low"
              :high="card.bullet.high"
              :min="card.bullet.min"
              :max="card.bullet.max"
              :unit="card.bullet.unit"
              :upper-open="card.bullet.upperOpen ?? false"
            />
            <span v-else class="fam-kpi__note">{{ card.note }}</span>
          </article>
        </div>
      </section>

      <!-- 分区 1：我的家人 -->
      <section v-if="activeSection === 'overview'" class="panel">
        <div class="fam-section-head">
          <div>
            <p class="section-eyebrow">照护对象</p>
            <h2>我的家人</h2>
          </div>
        </div>

        <div class="fam-elder-grid">
          <button
            v-for="row in visibleRows"
            :key="row.id"
            type="button"
            class="fam-elder-card"
            :class="[`fam-elder-card--${row.risk}`, { 'fam-elder-card--active': row.deviceMac === selectedDeviceMac }]"
            @click="selectedDeviceMac = row.deviceMac"
          >
            <div class="fam-elder-card__top">
              <span class="fam-elder-card__avatar">{{ row.name.slice(0, 1) }}</span>
              <span class="fam-elder-card__id">
                <strong>{{ row.name }}</strong>
                <small>{{ row.apartment }}{{ row.deviceMac ? " · T10 手环" : " · 未绑定设备" }}</small>
              </span>
              <span class="fam-elder-card__badge" :class="riskClass(row.risk)">{{ riskLabel(row.risk) }}</span>
            </div>
            <div class="fam-elder-card__vitals">
              <span class="fam-vt"><i>心率</i><b>{{ row.sample?.heart_rate ?? "--" }}</b></span>
              <span class="fam-vt"><i>血氧</i><b>{{ row.sample?.blood_oxygen != null ? row.sample.blood_oxygen + "%" : "--" }}</b></span>
              <span class="fam-vt"><i>健康分</i><b>{{ row.sample?.health_score != null ? Math.round(row.sample.health_score) : "--" }}</b></span>
            </div>
          </button>
        </div>
      </section>

      <!-- 分区 1：今日照护提示 -->
      <section v-if="activeSection === 'overview'" class="panel">
        <div class="fam-section-head">
          <div>
            <p class="section-eyebrow">照护建议</p>
            <h2>今日照护提示</h2>
          </div>
          <span class="fam-tag fam-tag--muted">按当前状态生成</span>
        </div>
        <div class="fam-tips">
          <article v-for="(tip, index) in careTips" :key="index" class="fam-tip" :class="`fam-tip--${tip.tone}`">
            <span class="fam-tip__dot"></span>
            <span class="fam-tip__body">
              <strong>{{ tip.title }}</strong>
              <small>{{ tip.body }}</small>
            </span>
          </article>
        </div>
      </section>

      <!-- ═══ 分区 2：实时体征 ═══ -->
      <section v-if="activeSection === 'vitals'" class="panel">
        <div class="fam-section-head">
          <div>
            <p class="section-eyebrow">实时体征</p>
            <h2>指标详情</h2>
          </div>
          <span class="fam-tag fam-tag--muted">更新 {{ focusUpdatedLabel }}</span>
        </div>
        <div class="fam-kpi-grid">
          <article
            v-for="card in familySnapshotCards"
            :key="card.id"
            class="fam-kpi"
            :class="`fam-kpi--${card.tone}`"
          >
            <span class="fam-kpi__label">{{ card.label }}</span>
            <span class="fam-kpi__value">{{ card.value }}<small>{{ card.unit }}</small></span>
            <BulletBar
              v-if="card.bullet"
              :value="card.bullet.value"
              :low="card.bullet.low"
              :high="card.bullet.high"
              :min="card.bullet.min"
              :max="card.bullet.max"
              :unit="card.bullet.unit"
              :upper-open="card.bullet.upperOpen ?? false"
            />
            <span class="fam-kpi__note">{{ card.note }}</span>
          </article>
        </div>
      </section>

      <section v-if="activeSection === 'vitals' && hasBoundDevice" class="panel">
        <div class="fam-section-head">
          <div>
            <p class="section-eyebrow">趋势预览</p>
            <h2>最近同步轨迹</h2>
          </div>
          <span class="fam-tag fam-tag--muted">片段 {{ familyTrendPreview.length }}</span>
        </div>
        <p class="fam-trend-headline">{{ familyTrendHeadline }}</p>

        <div v-if="familyTrendPreview.length" class="fam-trend-list">
          <div v-for="point in familyTrendPreview" :key="point.timestamp" class="fam-trend-row">
            <span class="fam-trend-row__time">
              {{ new Date(point.timestamp).toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }) }}
            </span>
            <span class="fam-trend-row__vitals">
              <span>HR <b>{{ point.heart_rate }}</b></span>
              <span>SpO₂ <b>{{ point.blood_oxygen }}%</b></span>
              <span>体温 <b>{{ point.temperature.toFixed(1) }}°C</b></span>
            </span>
            <span class="fam-trend-row__score">健康分 <b>{{ point.health_score != null ? Math.round(point.health_score) : "--" }}</b></span>
          </div>
        </div>
        <p v-else class="fam-empty">设备完成更多同步后，这里会展示最近几个采样点的变化轨迹。</p>
      </section>

      <!-- ═══ 分区：跌倒告警 ═══ -->
      <template v-if="activeSection === 'fall'">
        <section class="panel fam-fall-status" :class="activeFallAlarm ? 'fam-fall-status--danger' : 'fam-fall-status--ok'">
          <div class="fam-fall-status__icon">
            <span :class="{ 'fam-fall-status__pulse': activeFallAlarm }">{{ activeFallAlarm ? "⚠" : "✓" }}</span>
          </div>
          <div class="fam-fall-status__copy">
            <p class="section-eyebrow">Fall Guard · AI 视觉跌倒监测</p>
            <h2>{{ activeFallAlarm ? "检测到疑似跌倒，请立即处理" : "跌倒监测运行中，当前一切正常" }}</h2>
            <p>
              {{
                activeFallAlarm
                  ? `${activeFallAlarm.message}。请按下方应急指引处置，并保持与社区值守的联系。`
                  : "AI 视觉模型持续分析监控画面中的姿态变化，识别到跌倒或受伤风险时会第一时间推送告警并通知社区值守。"
              }}
            </p>
            <div class="fam-hero__tags">
              <template v-if="activeFallAlarm">
                <span class="fam-tag fam-tag--danger">
                  置信度 {{ fallConfidence(activeFallAlarm) != null ? fallConfidence(activeFallAlarm) + "%" : "分析中" }}
                </span>
                <span
                  v-if="fallReview(activeFallAlarm)"
                  class="fam-tag"
                  :class="fallReview(activeFallAlarm)!.confirmed ? 'fam-tag--danger' : 'fam-tag--ok'"
                  :title="fallReview(activeFallAlarm)!.reason || undefined"
                >
                  AI 复核：{{ fallReview(activeFallAlarm)!.label }}
                </span>
                <span class="fam-tag fam-tag--muted">
                  {{ new Date(activeFallAlarm.created_at).toLocaleString("zh-CN", { hour12: false }) }}
                </span>
              </template>
              <span class="fam-tag" :class="visionOnline ? 'fam-tag--ok' : 'fam-tag--muted'">
                视觉服务 {{ visionOnline == null ? "检测中…" : visionOnline ? "在线" : "离线" }}
              </span>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="fam-section-head">
            <div>
              <p class="section-eyebrow">实时画面</p>
              <h2>监护摄像头</h2>
            </div>
            <span class="fam-tag" :class="cameraSource === 'failed' ? 'fam-tag--muted' : 'fam-tag--ok'">
              {{ cameraSourceLabel }}
            </span>
          </div>
          <div class="fam-cam">
            <img
              v-if="cameraSource !== 'failed'"
              :key="cameraStreamUrl"
              :src="cameraStreamUrl"
              alt="监护摄像头实时画面"
              @error="handleStreamError"
            />
            <p v-else class="fam-empty">
              摄像头画面暂不可用（机器狗网络未接入且主系统未配置摄像头）。切回本分区可重试连接。
            </p>
          </div>
        </section>

        <!-- 跨模态关联：摄像头给时刻，手环给当时体征 -->
        <section v-if="fallVitalsWindow" class="panel">
          <div class="fam-section-head">
            <div>
              <p class="section-eyebrow">跨模态关联</p>
              <h2>跌倒时的身体状况</h2>
            </div>
            <span class="fam-tag fam-tag--muted">
              {{ new Date(fallVitalsWindow.occurredAt).toLocaleString("zh-CN", { hour12: false }) }} 前后
              {{ FALL_VITALS_SPAN_MINUTES }} 分钟
            </span>
          </div>

          <p class="fam-fall-vitals__lead">
            <template v-if="fallVitalsWindow.surge != null && fallVitalsWindow.surge >= 15">
              这段时间心率最高抬升 <b>{{ fallVitalsWindow.surge }}</b> 次/分（峰值
              {{ fallVitalsWindow.peak }}），提示当时有明显应激反应，建议结合是否疼痛、头晕一并观察。
            </template>
            <template v-else-if="fallVitalsWindow.surge != null">
              这段时间心率波动 {{ fallVitalsWindow.surge }} 次/分，未见明显应激抬升。
            </template>
            <template v-else>已取到该时段体征采样，但心率数据不完整。</template>
          </p>

          <div class="fam-fall-vitals">
            <article class="fam-fall-vitals__card">
              <span class="fam-fall-vitals__label">心率</span>
              <MiniSparkline
                v-if="fallVitalsWindow.heartRates.length > 1"
                :values="fallVitalsWindow.heartRates"
                :height="40"
                :rise-is-good="false"
              />
              <small>{{ fallVitalsWindow.heartRates.length }} 次采样</small>
            </article>
            <article class="fam-fall-vitals__card">
              <span class="fam-fall-vitals__label">血氧</span>
              <MiniSparkline
                v-if="fallVitalsWindow.bloodOxygen.length > 1"
                :values="fallVitalsWindow.bloodOxygen"
                :height="40"
              />
              <small>{{ fallVitalsWindow.bloodOxygen.length }} 次采样</small>
            </article>
          </div>
        </section>

        <section class="panel">
          <div class="fam-section-head">
            <div>
              <p class="section-eyebrow">跌倒记录</p>
              <h2>历史跌倒告警</h2>
            </div>
            <span class="fam-tag fam-tag--muted">{{ fallAlarms.length }} 条</span>
          </div>
          <div v-if="fallAlarms.length" class="fam-alarm-list">
            <div v-for="alarm in fallAlarms" :key="alarm.id" class="fam-alarm-row">
              <span class="fam-alarm-row__dot" :class="{ 'fam-alarm-row__dot--open': !alarm.acknowledged }"></span>
              <span class="fam-alarm-row__body">
                <strong>{{ alarm.message }}</strong>
                <small>
                  {{ new Date(alarm.created_at).toLocaleString("zh-CN", { hour12: false }) }}
                  · {{ alarm.acknowledged ? "已处理" : "待处理" }}
                  <template v-if="fallConfidence(alarm) != null"> · 置信度 {{ fallConfidence(alarm) }}%</template>
                  <template v-if="fallReview(alarm)">
                    ·
                    <em
                      class="fam-review-chip"
                      :class="fallReview(alarm)!.confirmed ? 'fam-review-chip--confirmed' : 'fam-review-chip--false'"
                      :title="fallReview(alarm)!.reason || undefined"
                    >
                      AI 复核：{{ fallReview(alarm)!.label }}
                    </em>
                  </template>
                </small>
              </span>
              <img
                v-if="fallSnapshotUrl(alarm)"
                :src="fallSnapshotUrl(alarm)!"
                class="fam-alarm-row__snap"
                alt="跌倒关键帧"
              />
            </div>
          </div>
          <p v-else class="fam-empty">没有跌倒告警记录。AI 监测持续在线，出现疑似跌倒会立即在这里展示。</p>
        </section>

        <section class="panel">
          <div class="fam-section-head">
            <div>
              <p class="section-eyebrow">应急指引</p>
              <h2>发现跌倒怎么办</h2>
            </div>
          </div>
          <div class="fam-fall-guide">
            <article v-for="(step, index) in fallGuideSteps" :key="index" class="fam-fall-step">
              <span class="fam-fall-step__index">{{ index + 1 }}</span>
              <strong>{{ step.title }}</strong>
              <p>{{ step.body }}</p>
            </article>
          </div>
        </section>
      </template>

      <!-- ═══ 分区 3：健康报告 ═══ -->
      <template v-if="activeSection === 'report'">
        <HealthEvaluationPanel
          v-if="hasBoundDevice"
          :is-bound="hasBoundDevice"
          :subject-name="focusRow?.name ?? '未选择对象'"
          :device-mac="selectedDeviceMac"
          :evaluation="currentHealthEvaluation"
          :report-summary="currentHealthReportSummary"
          :generated-report="generatedHealthReport"
          :report-loading="reportLoading"
          :report-error="reportError"
          @generate-report="generateHealthReport"
        />
        <article v-else class="panel">
          <h2 class="fam-empty-title">健康报告</h2>
          <p class="fam-empty">当前对象还没有绑定设备，绑定后这里会展示健康评估与报告生成入口。</p>
        </article>
      </template>

      <!-- ═══ 分区 4：告警动态 ═══ -->
      <template v-if="activeSection === 'alarms'">
        <AlarmEscalationPanel
          v-if="hasBoundDevice"
          :sample="displayFocusLatest"
          :trend="focusTrend"
          :focus-alarm="focusAlarm"
        />
        <section class="panel">
          <div class="fam-section-head">
            <div>
              <p class="section-eyebrow">告警记录</p>
              <h2>家人告警历史</h2>
            </div>
            <span class="fam-tag fam-tag--muted">{{ familyAlarms.length }} 条</span>
          </div>
          <div v-if="familyAlarms.length" class="fam-alarm-list">
            <div v-for="alarm in familyAlarms" :key="alarm.id" class="fam-alarm-row">
              <span class="fam-alarm-row__dot" :class="{ 'fam-alarm-row__dot--open': !alarm.acknowledged }"></span>
              <span class="fam-alarm-row__body">
                <strong>{{ alarm.message }}</strong>
                <small>{{ new Date(alarm.created_at).toLocaleString("zh-CN", { hour12: false }) }} · {{ alarm.acknowledged ? "已处理" : "待处理" }}</small>
              </span>
            </div>
          </div>
          <p v-else class="fam-empty">当前没有家人相关的告警记录，整体平稳。</p>
        </section>
      </template>

      <!-- ═══ 分区 5：家庭智能体 ═══ -->
      <template v-if="activeSection === 'assistant'">
        <AssistantPanel
          v-if="hasBoundDevice"
          :device-mac="selectedDeviceMac"
          :subject-name="focusRow?.name ?? '未选择对象'"
          :sample="displayFocusLatest"
          :risk-label="focusRiskLabel"
          :focus-alarm="focusAlarm"
          :trend-count="focusTrend.length"
        />
        <article v-else class="panel">
          <h2 class="fam-empty-title">家庭智能体</h2>
          <p class="fam-empty">完成设备绑定后，这里会展示基于当前对象状态生成的照护建议与对话入口。</p>
        </article>
      </template>

      <!-- ═══ 分区 6：设备管理 ═══ -->
      <section v-if="activeSection === 'devices'" class="panel">
        <div class="fam-section-head">
          <div>
            <p class="section-eyebrow">设备管理</p>
            <h2>家人设备台账</h2>
          </div>
          <span class="fam-tag fam-tag--muted">{{ familyDevices.filter((item) => item.bound).length }} 台已绑定</span>
        </div>
        <div class="fam-device-list">
          <article
            v-for="item in familyDevices"
            :key="item.elderId"
            class="fam-device-card"
            :class="{ 'fam-device-card--offline': item.bound && !item.online, 'fam-device-card--unbound': !item.bound }"
          >
            <div class="fam-device-card__head">
              <span class="fam-focus-bar__avatar">{{ item.elderName.slice(0, 1) }}</span>
              <span class="fam-elder-card__id">
                <strong>{{ item.elderName }}</strong>
                <small>{{ item.apartment }}</small>
              </span>
              <span class="fam-tag" :class="item.bound && item.online ? 'fam-tag--ok' : item.bound ? 'fam-tag--danger' : 'fam-tag--muted'">
                {{ item.statusText }}
              </span>
            </div>
            <div class="fam-device-card__rows">
              <span><i>设备</i><b>{{ item.bound ? "T10 手环" : "未绑定" }}</b></span>
              <span><i>MAC</i><b>{{ item.mac || "--" }}</b></span>
              <span><i>电量</i><b>{{ item.battery != null ? item.battery + "%" : "--" }}</b></span>
              <span><i>最近同步</i><b>{{ item.lastSeen }}</b></span>
            </div>
            <p v-if="!item.bound" class="fam-empty">请在移动端完成手环绑定后查看设备状态。</p>
          </article>
        </div>
      </section>
    </section>
  </section>
</template>

<style scoped>
.fam-stage {
  display: grid;
  gap: 18px;
}

.fam-stage > * {
  min-width: 0;
}

/*
 * 分区切换过渡：各分区带 v-if，切换时重新挂载，动画随之重放，无需 <Transition>。
 * 只动 opacity/transform 以保持 60fps；改结构前需确认分区仍是 v-if 而非 v-show，
 * 否则动画不会触发。
 */
.fam-stage > .panel {
  animation: fam-section-in 320ms var(--ease-enter, cubic-bezier(0.22, 0.8, 0.3, 1)) both;
}

/* ---- 跌倒时体征切片 ---- */
.fam-fall-vitals__lead {
  margin: 0 0 12px;
  font-size: var(--fs-2);
  color: var(--text-sub);
  line-height: 1.7;
}

.fam-fall-vitals__lead b {
  color: var(--risk-high);
  font-family: var(--font-mono);
}

.fam-fall-vitals {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.fam-fall-vitals__card {
  display: grid;
  gap: 6px;
  padding: 13px 15px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
}

.fam-fall-vitals__label {
  font-size: var(--fs-1);
  font-weight: 600;
  color: var(--text-sub);
}

.fam-fall-vitals__card small {
  font-size: var(--fs-0);
  color: var(--text-muted);
}

/* ---- AI 复核结论徽章 ---- */
.fam-review-chip {
  font-style: normal;
  padding: 1px 8px;
  margin-left: 6px;
  border-radius: 999px;
  font-size: var(--fs-0);
  font-weight: 700;
  white-space: nowrap;
}

.fam-review-chip--confirmed {
  color: var(--risk-high);
  background: var(--surface-danger);
}

.fam-review-chip--false {
  color: var(--risk-low);
  background: var(--surface-success);
}

@media (max-width: 720px) {
  .fam-fall-vitals {
    grid-template-columns: 1fr;
  }
}

@keyframes fam-section-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* ---- 1. 安心指数 Hero ---- */
.fam-hero {
  display: flex;
  align-items: center;
  gap: 26px;
  flex-wrap: wrap;
}

.fam-hero__score {
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.fam-ring {
  position: relative;
  width: 108px;
  height: 108px;
  flex-shrink: 0;
}

.fam-ring svg {
  transform: rotate(-90deg);
}

.fam-ring__track {
  fill: none;
  stroke: var(--surface-0);
  stroke-width: 9;
}

.fam-ring__bar {
  fill: none;
  stroke: var(--brand);
  stroke-width: 9;
  stroke-linecap: round;
  stroke-dasharray: 289;
  transition: stroke-dashoffset 900ms cubic-bezier(0.4, 0, 0.2, 1);
}

.fam-ring__bar--warning { stroke: var(--risk-medium); }
.fam-ring__bar--critical { stroke: var(--risk-high); }
.fam-ring__bar--stable { stroke: var(--risk-low); }

.fam-ring__val {
  position: absolute;
  inset: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 3px;
  text-align: center;
}

.fam-ring__val b {
  font-family: var(--font-mono);
  font-size: 30px;
  display: block;
  line-height: 1;
  color: var(--text-main);
}

.fam-ring__val span {
  font-size: 11px;
  color: var(--text-muted);
  max-width: 84px;
}

.fam-hero__meta {
  max-width: 320px;
}

.fam-hero__meta h2 {
  margin: 0 0 6px;
  font-size: 19px;
  font-family: var(--font-display);
  color: var(--text-main);
}

.fam-hero__meta p {
  margin: 0;
  font-size: 14px;
  color: var(--text-sub);
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.fam-hero__tags {
  display: flex;
  gap: 7px;
  margin-top: 9px;
  flex-wrap: wrap;
}

.fam-tag {
  font-size: 12.5px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  white-space: nowrap;
}

.fam-tag--ok { color: var(--risk-low); background: var(--surface-success); }
.fam-tag--danger { color: var(--risk-high); background: var(--surface-danger); }
.fam-tag--muted { color: var(--text-sub); background: var(--surface-soft); }

.fam-hero__kpis {
  flex: 1;
  min-width: 420px;
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 1fr) minmax(0, 1fr);
  grid-template-rows: auto auto;
  gap: 12px;
}

/* 主 KPI 占左侧整列，三个体征卡分列右侧两列 */
.fam-kpi--primary {
  grid-row: span 2;
  display: flex;
  flex-direction: column;
  gap: 6px;
  border-color: color-mix(in srgb, var(--brand) 28%, transparent);
  background: linear-gradient(160deg, var(--surface-cyan), var(--panel-tinted) 70%);
}

.fam-kpi__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.fam-kpi__value--lg {
  font-size: 36px;
  line-height: 1.1;
}

.fam-kpi--primary .fam-kpi__note {
  margin-top: auto;
}

.fam-kpi {
  border: 1px solid var(--line);
  background: var(--panel-tinted);
  border-radius: var(--radius-md);
  padding: 13px 15px;
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.fam-kpi:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.fam-kpi__label {
  display: block;
  font-size: 13px;
  color: var(--text-muted);
}

.fam-kpi__value {
  display: block;
  font-family: var(--font-mono);
  font-size: 26px;
  font-weight: 700;
  margin-top: 4px;
  color: var(--text-main);
}

.fam-kpi__value small {
  font-size: 13.5px;
  color: var(--text-muted);
  font-weight: 400;
  margin-left: 3px;
}

.fam-kpi__note {
  display: block;
  margin-top: 6px;
  font-size: 12px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fam-kpi--warning {
  border-color: color-mix(in srgb, var(--risk-medium) 40%, transparent);
  background: var(--surface-warning);
}

.fam-kpi--warning .fam-kpi__value { color: var(--risk-medium); }

.fam-kpi--critical {
  border-color: color-mix(in srgb, var(--risk-high) 40%, transparent);
  background: var(--surface-danger);
}

.fam-kpi--critical .fam-kpi__value { color: var(--risk-high); }

/* ---- 2. 照护对象 ---- */
.fam-section-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 14px;
}

.fam-section-head h2 {
  margin: 4px 0 0;
  font-family: var(--font-display);
  color: var(--text-main);
}

.fam-select {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13.5px;
  color: var(--text-muted);
  white-space: nowrap;
}

.fam-select select {
  height: 36px;
  padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: 9px;
  background: var(--panel-strong);
  color: var(--text-main);
  font-size: 14.5px;
  font-family: inherit;
  outline: none;
}

.fam-elder-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 13px;
}

.fam-elder-card {
  position: relative;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-strong);
  padding: 14px 15px 12px;
  cursor: pointer;
  text-align: left;
  transition: transform 160ms ease, box-shadow 160ms ease;
  overflow: hidden;
}

.fam-elder-card::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 4px;
  border-radius: 8px 0 0 8px;
  background: var(--surface-3);
}

.fam-elder-card--low::before { background: var(--risk-low); }
.fam-elder-card--medium::before { background: var(--risk-medium); }
.fam-elder-card--high::before { background: var(--risk-high); }

.fam-elder-card:hover {
  transform: translateY(-3px);
  box-shadow: var(--shadow);
}

.fam-elder-card--active {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

.fam-elder-card__top {
  display: flex;
  align-items: center;
  gap: 11px;
}

.fam-elder-card__avatar {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: #ffffff;
  font-weight: 700;
  font-size: 18px;
  display: grid;
  place-items: center;
}

.fam-elder-card__id {
  flex: 1;
  min-width: 0;
}

.fam-elder-card__id strong {
  display: block;
  font-size: 17px;
  color: var(--text-main);
}

.fam-elder-card__id small {
  display: block;
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.fam-elder-card__badge {
  font-size: 12.5px;
  padding: 3px 10px;
  border-radius: 999px;
  font-weight: 600;
  white-space: nowrap;
}

.fam-elder-card__badge.risk-low { color: var(--risk-low); background: var(--surface-success); }
.fam-elder-card__badge.risk-medium { color: var(--risk-medium); background: var(--surface-warning); }
.fam-elder-card__badge.risk-high { color: var(--risk-high); background: var(--surface-danger); }

.fam-elder-card__vitals {
  display: flex;
  gap: 7px;
  margin-top: 12px;
}

.fam-vt {
  flex: 1;
  text-align: center;
  border: 1px solid var(--line);
  background: var(--panel-tinted);
  border-radius: 8px;
  padding: 6px 2px 5px;
}

.fam-vt i {
  font-style: normal;
  display: block;
  font-size: 11px;
  color: var(--text-muted);
}

.fam-vt b {
  font-family: var(--font-mono);
  font-size: 15.5px;
  color: var(--text-main);
}

/* ---- 3. 趋势 ---- */
.fam-trend-headline {
  margin: -4px 0 12px;
  font-size: 14px;
  color: var(--text-sub);
  line-height: 1.6;
}

.fam-trend-list {
  display: grid;
}

.fam-trend-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 2px;
  border-bottom: 1px dashed var(--line);
  flex-wrap: wrap;
}

.fam-trend-row:last-child {
  border-bottom: none;
}

.fam-trend-row__time {
  font-family: var(--font-mono);
  font-size: 13px;
  color: var(--text-muted);
  width: 96px;
  flex-shrink: 0;
}

.fam-trend-row__vitals {
  flex: 1;
  display: flex;
  gap: 16px;
  font-size: 13.5px;
  color: var(--text-sub);
}

.fam-trend-row__vitals b,
.fam-trend-row__score b {
  font-family: var(--font-mono);
  color: var(--text-main);
}

.fam-trend-row__score {
  font-size: 13.5px;
  color: var(--text-sub);
  white-space: nowrap;
}

.fam-empty {
  margin: 0;
  color: var(--text-sub);
  font-size: 14px;
}

.fam-empty-title {
  margin: 0 0 8px;
  font-family: var(--font-display);
  color: var(--text-main);
}

/* ---- 当前对象条 ---- */
.fam-focus-bar {
  display: flex;
  align-items: center;
  gap: 18px;
  flex-wrap: wrap;
}

.fam-focus-bar__who {
  display: flex;
  align-items: center;
  gap: 11px;
  min-width: 0;
}

.fam-focus-bar__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: #ffffff;
  font-weight: 700;
  font-size: 17px;
  display: grid;
  place-items: center;
}

.fam-focus-bar__id strong {
  display: block;
  font-size: 16px;
  color: var(--text-main);
}

.fam-focus-bar__id small {
  display: block;
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 1px;
}

.fam-focus-bar__switch {
  flex: 1;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.fam-focus-pill {
  padding: 7px 16px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-tinted);
  color: var(--text-sub);
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 160ms ease;
}

.fam-focus-pill:hover {
  border-color: var(--line-strong);
  transform: translateY(-1px);
}

.fam-focus-pill--active {
  background: var(--surface-cyan);
  border-color: color-mix(in srgb, var(--brand) 45%, transparent);
  color: var(--brand);
  font-weight: 700;
}

/* ---- 今日照护提示 ---- */
.fam-tips {
  display: grid;
  gap: 10px;
}

.fam-tip {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 12px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
}

.fam-tip__dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 6px;
  background: var(--risk-low);
}

.fam-tip--warn .fam-tip__dot { background: var(--risk-medium); }
.fam-tip--danger .fam-tip__dot { background: var(--risk-high); }

.fam-tip--warn {
  border-color: color-mix(in srgb, var(--risk-medium) 35%, transparent);
  background: var(--surface-warning);
}

.fam-tip--danger {
  border-color: color-mix(in srgb, var(--risk-high) 35%, transparent);
  background: var(--surface-danger);
}

.fam-tip__body strong {
  display: block;
  font-size: 14.5px;
  color: var(--text-main);
}

.fam-tip__body small {
  display: block;
  font-size: 13px;
  color: var(--text-sub);
  margin-top: 2px;
  line-height: 1.6;
}

/* ---- 实时体征全量网格 ---- */
.fam-kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

/* ---- 告警记录 ---- */
.fam-alarm-list {
  display: grid;
}

.fam-alarm-row {
  display: flex;
  align-items: flex-start;
  gap: 11px;
  padding: 10px 2px;
  border-bottom: 1px dashed var(--line);
}

.fam-alarm-row:last-child {
  border-bottom: none;
}

.fam-alarm-row__dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
  background: var(--risk-low);
}

.fam-alarm-row__dot--open {
  background: var(--risk-high);
  animation: pulse-ring 2s infinite;
}

.fam-alarm-row__body strong {
  display: block;
  font-size: 14.5px;
  color: var(--text-main);
}

.fam-alarm-row__body small {
  display: block;
  font-family: var(--font-mono);
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 2px;
}

/* ---- 设备台账 ---- */
.fam-device-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 13px;
}

.fam-device-card {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  padding: 14px 16px;
}

.fam-device-card--offline {
  border-color: color-mix(in srgb, var(--risk-high) 35%, transparent);
  background: var(--surface-danger);
}

.fam-device-card--unbound {
  border-style: dashed;
}

.fam-device-card__head {
  display: flex;
  align-items: center;
  gap: 11px;
}

.fam-device-card__rows {
  display: grid;
  gap: 6px;
  margin-top: 12px;
}

.fam-device-card__rows span {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13.5px;
}

.fam-device-card__rows i {
  font-style: normal;
  color: var(--text-muted);
  flex-shrink: 0;
}

.fam-device-card__rows b {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--text-main);
  text-align: right;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fam-device-card .fam-empty {
  margin-top: 10px;
}

/* ---- 跌倒告警 ---- */
.fam-fall-status {
  display: flex;
  align-items: center;
  gap: 20px;
}

.fam-fall-status--ok {
  border-color: color-mix(in srgb, var(--risk-low) 35%, transparent);
}

.fam-fall-status--danger {
  border-color: color-mix(in srgb, var(--risk-high) 45%, transparent);
  background: var(--surface-danger);
}

.fam-fall-status__icon {
  width: 72px;
  height: 72px;
  flex-shrink: 0;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 33.5px;
  background: var(--surface-success);
  color: var(--risk-low);
}

.fam-fall-status--danger .fam-fall-status__icon {
  background: color-mix(in srgb, var(--risk-high) 14%, transparent);
  color: var(--risk-high);
}

.fam-fall-status__pulse {
  display: grid;
  place-items: center;
  width: 100%;
  height: 100%;
  border-radius: 50%;
  animation: pulse-ring 1.8s infinite;
}

.fam-fall-status__copy {
  min-width: 0;
}

.fam-fall-status__copy h2 {
  margin: 4px 0 8px;
  font-family: var(--font-display);
  color: var(--text-main);
}

.fam-fall-status--danger .fam-fall-status__copy h2 {
  color: var(--risk-high);
}

.fam-fall-status__copy p {
  margin: 0;
  font-size: 14px;
  color: var(--text-sub);
  line-height: 1.7;
  max-width: 640px;
}

.fam-cam {
  border-radius: var(--radius-md);
  overflow: hidden;
  background: #0b1520;
  min-height: 200px;
  display: grid;
  place-items: center;
}

.fam-cam img {
  width: 100%;
  max-height: 460px;
  object-fit: contain;
  display: block;
}

.fam-cam .fam-empty {
  color: var(--text-muted);
  padding: 40px 20px;
}

.fam-alarm-row__snap {
  width: 88px;
  height: 60px;
  object-fit: cover;
  border-radius: 8px;
  border: 1px solid var(--line);
  flex-shrink: 0;
}

.fam-fall-guide {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.fam-fall-step {
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  padding: 15px 16px;
}

.fam-fall-step__index {
  display: inline-flex;
  width: 30px;
  height: 30px;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface-cyan);
  color: var(--brand);
  font-family: var(--font-mono);
  font-weight: 800;
  margin-bottom: 9px;
}

.fam-fall-step strong {
  display: block;
  font-size: 15px;
  color: var(--text-main);
}

.fam-fall-step p {
  margin: 6px 0 0;
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.65;
}

@media (max-width: 1180px) {
  .fam-hero__kpis {
    min-width: 0;
    grid-template-columns: 1fr;
    grid-template-rows: auto;
  }

  .fam-kpi--primary {
    grid-row: auto;
  }

  .fam-focus-bar__switch {
    order: 3;
    flex-basis: 100%;
  }
}
</style>
