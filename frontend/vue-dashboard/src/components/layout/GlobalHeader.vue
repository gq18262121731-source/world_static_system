<script setup lang="ts">
import { computed, onUnmounted, ref, toRef } from "vue";
import { Bell, LogOut, Search, ShieldCheck } from "lucide-vue-next";
import type { SessionUser } from "../../api/client";
import {
  focusCommunityWorkspaceDevice,
  useCommunityWorkspace,
} from "../../composables/useCommunityWorkspace";

const props = defineProps<{
  sessionUser: SessionUser;
  activeAlarmCount: number;
}>();

const emit = defineEmits<{
  logout: [];
  focusAlarms: [];
}>();

const roleLabel = computed(() => {
  switch (props.sessionUser.role) {
    case "community":
      return "社区值守";
    case "family":
      return "家属查看";
    case "admin":
      return "系统管理";
    default:
      return "成员账号";
  }
});

const showWorkspaceUtils = computed(
  () => props.sessionUser.role === "community" || props.sessionUser.role === "admin",
);

/* ---- 搜索：对已加载的老人与设备做本地模糊匹配 ---- */
const workspace = useCommunityWorkspace(toRef(props, "sessionUser"));
const keyword = ref("");
const searchOpen = ref(false);
let blurTimer: number | null = null;

type SearchHit = {
  elderId: string;
  deviceMac: string;
  name: string;
  apartment: string;
  risk: "high" | "medium" | "low";
  statusText: string;
};

const searchHits = computed<SearchHit[]>(() => {
  const query = keyword.value.trim().toLowerCase();
  if (!query) return [];

  const compact = query.replace(/[:\-\s]/g, "");
  return workspace.topRiskElders.value
    .filter((elder) => {
      const mac = (elder.device_mac ?? "").toLowerCase();
      return (
        elder.elder_name.toLowerCase().includes(query)
        || (elder.apartment ?? "").toLowerCase().includes(query)
        || mac.includes(query)
        || (compact.length >= 3 && mac.replace(/[:\-]/g, "").includes(compact))
      );
    })
    .slice(0, 6)
    .map((elder) => ({
      elderId: elder.elder_id,
      deviceMac: elder.device_mac ?? "",
      name: elder.elder_name,
      apartment: elder.apartment ?? "--",
      risk: elder.risk_level,
      statusText: !elder.device_mac
        ? "未绑定设备"
        : elder.device_status === "offline"
          ? "设备离线"
          : "在线",
    }));
});

const riskLabelMap: Record<SearchHit["risk"], string> = {
  high: "高风险",
  medium: "中风险",
  low: "低风险",
};

function openResults() {
  searchOpen.value = true;
  if (blurTimer !== null) {
    window.clearTimeout(blurTimer);
    blurTimer = null;
  }
}

function deferCloseResults() {
  // 延迟关闭，否则点击结果时下拉已经消失
  blurTimer = window.setTimeout(() => {
    searchOpen.value = false;
  }, 160);
}

function selectHit(hit: SearchHit) {
  if (hit.deviceMac) {
    focusCommunityWorkspaceDevice(hit.deviceMac);
  } else {
    workspace.setSelectedElderId(hit.elderId);
  }
  if (window.location.hash !== "#/overview") {
    window.location.hash = "#/overview";
  }
  keyword.value = "";
  searchOpen.value = false;
  window.setTimeout(() => {
    document.querySelector(".workspace-stage")?.scrollTo({ top: 0, behavior: "smooth" });
  }, 120);
}

onUnmounted(() => {
  if (blurTimer !== null) window.clearTimeout(blurTimer);
});
</script>

<template>
  <header class="modern-global-header">
    <div class="modern-global-header__brand">
      <div class="modern-global-header__icon">护</div>
      <div class="modern-global-header__text">
        <p class="modern-global-header__eyebrow">AIoT Care Console</p>
        <h1 class="modern-global-header__title">智慧康养健康监测平台</h1>
      </div>
    </div>

    <div class="modern-global-header__actions">
      <div v-if="showWorkspaceUtils" class="modern-global-header__search-wrap">
        <label class="modern-global-header__search">
          <Search :size="15" />
          <input
            v-model="keyword"
            type="text"
            placeholder="搜索老人 / 房号 / 设备 MAC"
            @focus="openResults"
            @blur="deferCloseResults"
          />
        </label>

        <div v-if="searchOpen && keyword.trim()" class="search-results">
          <button
            v-for="hit in searchHits"
            :key="hit.elderId"
            type="button"
            class="search-results__item"
            @mousedown.prevent="selectHit(hit)"
          >
            <span class="search-results__name">{{ hit.name }}</span>
            <span class="search-results__meta">{{ hit.apartment }} · {{ hit.statusText }}</span>
            <span class="search-results__risk" :class="`search-results__risk--${hit.risk}`">
              {{ riskLabelMap[hit.risk] }}
            </span>
          </button>
          <p v-if="!searchHits.length" class="search-results__empty">未找到匹配的老人或设备</p>
        </div>
      </div>

      <button
        v-if="showWorkspaceUtils"
        type="button"
        class="modern-global-header__bell"
        :class="{ 'modern-global-header__bell--active': activeAlarmCount > 0 }"
        :title="activeAlarmCount > 0 ? `${activeAlarmCount} 条未确认告警，点击查看` : '当前没有未确认告警'"
        @click="emit('focusAlarms')"
      >
        <Bell :size="17" />
        <span v-if="activeAlarmCount > 0" class="modern-global-header__bell-badge">
          {{ activeAlarmCount > 99 ? "99+" : activeAlarmCount }}
        </span>
      </button>

      <div class="modern-global-header__user-info">
        <span class="modern-global-header__user-avatar">{{ sessionUser.name.slice(0, 1) }}</span>
        <span class="modern-global-header__user-name">{{ sessionUser.name }}</span>
        <span class="modern-global-header__user-role">
          <ShieldCheck :size="14" />
          {{ roleLabel }}
        </span>
      </div>

      <button type="button" class="modern-global-header__logout-btn" @click="emit('logout')">
        <LogOut :size="16" />
        <span>退出</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.modern-global-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  padding: 14px 22px;
  background: var(--panel-strong);
  border: 1px solid var(--line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
}

.modern-global-header__brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.modern-global-header__icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: linear-gradient(135deg, var(--brand-2) 0%, var(--brand) 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #ffffff;
  font-size: 1.2rem;
  font-weight: 800;
  box-shadow: 0 4px 12px var(--brand-glow);
  flex-shrink: 0;
}

.modern-global-header__text {
  display: grid;
  gap: 2px;
}

.modern-global-header__eyebrow {
  margin: 0;
  font-size: 0.68rem;
  color: var(--brand);
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.modern-global-header__title {
  margin: 0;
  font-size: 1.12rem;
  font-weight: 800;
  color: var(--text-main);
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.modern-global-header__actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* 搜索框 */
.modern-global-header__search-wrap {
  position: relative;
}

.search-results {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 40;
  padding: 6px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-strong);
  box-shadow: var(--shadow-lg);
}

.search-results__item {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 10px;
  border: none;
  border-radius: 8px;
  background: transparent;
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: background 140ms ease;
}

.search-results__item:hover {
  background: var(--surface-cyan);
}

.search-results__name {
  font-size: 14.5px;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
}

.search-results__meta {
  font-size: 12.5px;
  color: var(--text-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.search-results__risk {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.search-results__risk--low { color: var(--risk-low); background: var(--surface-success); }
.search-results__risk--medium { color: var(--risk-medium); background: var(--surface-warning); }
.search-results__risk--high { color: var(--risk-high); background: var(--surface-danger); }

.search-results__empty {
  margin: 0;
  padding: 10px;
  font-size: 13.5px;
  color: var(--text-muted);
  text-align: center;
}

.modern-global-header__search {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 220px;
  height: 38px;
  padding: 0 14px;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: var(--panel-tinted);
  color: var(--text-muted);
  transition: all 200ms ease;
}

.modern-global-header__search:focus-within {
  border-color: var(--brand);
  background: var(--panel-strong);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

.modern-global-header__search input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
}

.modern-global-header__search input::placeholder {
  color: var(--text-muted);
}

/* 告警铃铛 */
.modern-global-header__bell {
  position: relative;
  width: 38px;
  height: 38px;
  padding: 0;
  border-radius: 11px;
  border: 1px solid var(--line);
  background: var(--panel-tinted);
  display: grid;
  place-items: center;
  color: var(--text-sub);
  flex-shrink: 0;
  cursor: pointer;
  transition: transform 150ms ease, box-shadow 150ms ease;
}

.modern-global-header__bell:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.modern-global-header__bell--active {
  color: var(--risk-medium);
  border-color: color-mix(in srgb, var(--risk-medium) 40%, transparent);
  background: var(--surface-warning);
}

.modern-global-header__bell-badge {
  position: absolute;
  top: -6px;
  right: -6px;
  min-width: 17px;
  height: 17px;
  border-radius: 999px;
  background: var(--risk-high);
  color: #ffffff;
  font-size: 11px;
  font-weight: 700;
  display: grid;
  place-items: center;
  padding: 0 4px;
  border: 2px solid var(--panel-strong);
}

/* 用户信息 */
.modern-global-header__user-info {
  display: flex;
  align-items: center;
  gap: 9px;
  padding: 6px 12px 6px 7px;
  border-radius: 999px;
  background: var(--panel-strong);
  border: 1px solid var(--line);
}

.modern-global-header__user-avatar {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: #ffffff;
  font-size: 13.5px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modern-global-header__user-name {
  font-size: 0.86rem;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
}

.modern-global-header__user-role {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 9px;
  border-radius: 8px;
  background: var(--surface-cyan);
  color: var(--brand);
  font-size: 0.76rem;
  font-weight: 600;
  white-space: nowrap;
}

.modern-global-header__logout-btn {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 9px 16px;
  border: 1px solid var(--line);
  border-radius: 11px;
  background: var(--panel-strong);
  color: var(--text-sub);
  font-size: 0.86rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 200ms ease;
  white-space: nowrap;
}

.modern-global-header__logout-btn:hover {
  background: var(--risk-high);
  border-color: var(--risk-high);
  color: #ffffff;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(197, 48, 48, 0.3);
}

@media (max-width: 1200px) {
  .modern-global-header__search {
    display: none;
  }
}

@media (max-width: 1024px) {
  .modern-global-header {
    flex-direction: column;
    align-items: stretch;
  }

  .modern-global-header__actions {
    justify-content: space-between;
  }
}
</style>
