<script setup lang="ts">
import { computed, onMounted } from "vue";
import {
  Activity,
  Cpu,
  Network,
  SquareTerminal,
  type LucideIcon,
  UsersRound,
} from "lucide-vue-next";
import type { SessionUser } from "../../api/client";
import { useCareTasks } from "../../composables/useCareTasks";
import type { PageKey } from "../../composables/useHashRouting";

const props = defineProps<{
  activePage: PageKey;
  allowedPages: PageKey[];
  sessionUser?: SessionUser;
}>();

const roleLabel = computed(() => {
  switch (props.sessionUser?.role) {
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

const emit = defineEmits<{
  navigate: [page: PageKey];
}>();

type NavItem = {
  page: PageKey;
  label: string;
  description: string;
  icon: LucideIcon;
};

const navItems = computed<NavItem[]>(() =>
  ([
    {
      page: "overview" as PageKey,
      label: "总览监护",
      description: "实时曲线与总览",
      icon: Activity,
    },
    {
      page: "topology" as PageKey,
      label: "设备拓扑",
      description: "老人与设备归属",
      icon: Network,
    },
    {
      page: "members" as PageKey,
      label: "成员设备",
      description: "注册、绑定与台账",
      icon: UsersRound,
    },
    {
      page: "agent" as PageKey,
      label: "康养智能体",
      description: "AI 风险分析与报告",
      icon: SquareTerminal,
    },
    {
      page: "family" as PageKey,
      label: "家属视图",
      description: "家庭成员查看页面",
      icon: Cpu,
    },
  ] satisfies NavItem[]).filter((item) => props.allowedPages.includes(item.page)),
);

/* 值班信息按真实时间计算：白班 08:00–20:00，夜班 20:00–08:00 */
const shiftInfo = computed(() => {
  const now = new Date();
  const hour = now.getHours() + now.getMinutes() / 60;
  const isDayShift = hour >= 8 && hour < 20;
  const elapsed = isDayShift ? hour - 8 : hour >= 20 ? hour - 20 : hour + 4;
  const progress = Math.min(100, Math.max(0, (elapsed / 12) * 100));
  return {
    name: isDayShift ? "白班" : "夜班",
    window: isDayShift ? "08:00–20:00" : "20:00–08:00",
    progress: Math.round(progress),
    elapsedText: `已值守 ${elapsed.toFixed(1)} 小时`,
    handoverText: isDayShift ? "20:00 交接" : "08:00 交接",
  };
});

const { tasks, doneCount, busyIds, loadTasks, toggleTask } = useCareTasks();

const sidebarTasks = computed(() => tasks.value.slice(0, 5));

onMounted(() => {
  void loadTasks();
});
</script>

<template>
  <nav v-if="navItems.length" class="modern-primary-nav" aria-label="主导航">
    <div class="modern-primary-nav__header">
      <p class="modern-primary-nav__eyebrow">Community Console</p>
      <h3 class="modern-primary-nav__title">社区工作台</h3>
      <p class="modern-primary-nav__subtitle">监护 · 拓扑 · 成员 · 智能体</p>
    </div>

    <div v-if="sessionUser" class="modern-primary-nav__profile">
      <span class="modern-primary-nav__avatar">{{ sessionUser.name.slice(0, 1) }}</span>
      <span class="modern-primary-nav__profile-info">
        <strong>{{ sessionUser.name }}</strong>
        <small>{{ roleLabel }}</small>
      </span>
      <span class="modern-primary-nav__onduty">● 在岗</span>
    </div>

    <div class="modern-primary-nav__items">
      <button
        v-for="item in navItems"
        :key="item.page"
        type="button"
        class="modern-primary-nav__item"
        :class="{ 'modern-primary-nav__item--active': activePage === item.page }"
        @click="emit('navigate', item.page)"
      >
        <div class="modern-primary-nav__icon">
          <component :is="item.icon" :size="19" />
        </div>
        <div class="modern-primary-nav__content">
          <strong class="modern-primary-nav__label">{{ item.label }}</strong>
          <small class="modern-primary-nav__description">{{ item.description }}</small>
        </div>
        <div class="modern-primary-nav__indicator"></div>
      </button>
    </div>

    <div v-if="sessionUser" class="modern-primary-nav__shift">
      <div class="modern-primary-nav__shift-head">
        <strong>今日值班 · {{ shiftInfo.name }}</strong>
        <span>{{ shiftInfo.window }}</span>
      </div>
      <div class="modern-primary-nav__shift-bar">
        <i :style="{ width: shiftInfo.progress + '%' }"></i>
      </div>
      <div class="modern-primary-nav__shift-foot">
        <span>{{ shiftInfo.elapsedText }}</span>
        <span>{{ shiftInfo.handoverText }}</span>
      </div>
    </div>

    <div v-if="sessionUser" class="modern-primary-nav__todo">
      <div class="modern-primary-nav__todo-head">
        <strong>今日待办</strong>
        <span>{{ doneCount }}/{{ tasks.length }}</span>
      </div>
      <button
        v-for="task in sidebarTasks"
        :key="task.id"
        type="button"
        class="modern-primary-nav__todo-item"
        :class="{
          'modern-primary-nav__todo-item--done': task.status === 'done',
          'modern-primary-nav__todo-item--busy': busyIds.has(task.id),
        }"
        :disabled="busyIds.has(task.id)"
        :title="task.note || task.title"
        @click="toggleTask(task)"
      >
        <span class="modern-primary-nav__todo-box">{{ task.status === "done" ? "✓" : "" }}</span>
        <label>{{ task.title }}</label>
      </button>
      <p v-if="!tasks.length" class="modern-primary-nav__todo-empty">
        暂无待办，可在总览页新建任务。
      </p>
    </div>
  </nav>
</template>

<style scoped>
.modern-primary-nav {
  display: grid;
  gap: 14px;
  padding: 12px 6px;
  background: transparent;
}

.modern-primary-nav__header {
  padding: 4px 4px 14px;
  border-bottom: 1px solid var(--line);
}

.modern-primary-nav__eyebrow {
  margin: 0;
  font-size: 0.64rem;
  color: var(--brand);
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.modern-primary-nav__title {
  margin: 6px 0 0;
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-main);
  letter-spacing: -0.02em;
}

.modern-primary-nav__subtitle {
  margin: 5px 0 0;
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.modern-primary-nav__profile {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--panel-tinted);
}

.modern-primary-nav__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  flex-shrink: 0;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: #ffffff;
  font-size: 17px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modern-primary-nav__profile-info {
  flex: 1;
  min-width: 0;
}

.modern-primary-nav__profile-info strong {
  display: block;
  font-size: 15.5px;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.modern-primary-nav__profile-info small {
  display: block;
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 2px;
}

.modern-primary-nav__onduty {
  font-size: 12px;
  font-weight: 700;
  color: var(--risk-low);
  background: var(--surface-success);
  padding: 3px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.modern-primary-nav__items {
  display: grid;
  gap: 9px;
}

.modern-primary-nav__item {
  position: relative;
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 13px;
  padding: 13px 14px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
  text-align: left;
  cursor: pointer;
  transition: all 200ms ease;
  overflow: hidden;
}

.modern-primary-nav__item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 3px;
  background: var(--brand);
  opacity: 0;
  transition: opacity 200ms ease;
}

.modern-primary-nav__item:hover {
  border-color: var(--line-strong);
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.modern-primary-nav__item--active {
  background: var(--surface-cyan);
  border-color: color-mix(in srgb, var(--brand) 45%, transparent);
}

.modern-primary-nav__item--active::before {
  opacity: 1;
}

.modern-primary-nav__icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: var(--panel-strong);
  border: 1px solid var(--line);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-sub);
  transition: all 200ms ease;
  flex-shrink: 0;
}

.modern-primary-nav__item--active .modern-primary-nav__icon {
  background: linear-gradient(135deg, var(--brand-2) 0%, var(--brand) 100%);
  border-color: transparent;
  color: #ffffff;
  box-shadow: 0 4px 12px var(--brand-glow);
}

.modern-primary-nav__content {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.modern-primary-nav__label {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-sub);
  letter-spacing: -0.01em;
}

.modern-primary-nav__description {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.modern-primary-nav__item--active .modern-primary-nav__label {
  color: var(--text-main);
  font-weight: 800;
}

.modern-primary-nav__item--active .modern-primary-nav__description {
  color: var(--text-sub);
}

.modern-primary-nav__indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: transparent;
  transition: all 200ms ease;
  flex-shrink: 0;
}

.modern-primary-nav__item--active .modern-primary-nav__indicator {
  background: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

/* 值班卡 */
.modern-primary-nav__shift {
  padding: 12px 13px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--panel-tinted);
}

.modern-primary-nav__shift-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modern-primary-nav__shift-head strong {
  font-size: 14px;
  color: var(--text-main);
}

.modern-primary-nav__shift-head span {
  font-family: var(--font-mono);
  color: var(--text-muted);
  font-size: 12.5px;
}

.modern-primary-nav__shift-bar {
  height: 7px;
  border-radius: 99px;
  background: var(--surface-0);
  overflow: hidden;
  margin-top: 9px;
}

.modern-primary-nav__shift-bar i {
  display: block;
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--brand-2), var(--brand));
}

.modern-primary-nav__shift-foot {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 6px;
}

/* 今日待办 */
.modern-primary-nav__todo {
  padding: 12px 13px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--panel-tinted);
}

.modern-primary-nav__todo-head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.modern-primary-nav__todo-head strong {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main);
}

.modern-primary-nav__todo-head span {
  font-family: var(--font-mono);
  color: var(--brand);
  font-size: 13.5px;
  font-weight: 700;
}

.modern-primary-nav__todo-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 5px 2px;
  border: none;
  background: transparent;
  font-size: 13.5px;
  font-family: inherit;
  color: var(--text-sub);
  text-align: left;
  cursor: pointer;
  border-radius: 6px;
  transition: background 140ms ease;
}

.modern-primary-nav__todo-item:hover:not(:disabled) {
  background: var(--surface-soft);
}

.modern-primary-nav__todo-item--busy {
  opacity: 0.55;
  cursor: progress;
}

.modern-primary-nav__todo-empty {
  margin: 2px 2px 0;
  font-size: 12.5px;
  color: var(--text-muted);
  line-height: 1.5;
}

.modern-primary-nav__todo-box {
  width: 15px;
  height: 15px;
  flex-shrink: 0;
  border-radius: 4px;
  border: 1.5px solid var(--line-strong);
  display: grid;
  place-items: center;
  font-size: 11px;
  color: #ffffff;
}

.modern-primary-nav__todo-item--done .modern-primary-nav__todo-box {
  background: var(--risk-low);
  border-color: var(--risk-low);
}

.modern-primary-nav__todo-item--done label {
  text-decoration: line-through;
  color: var(--text-muted);
}
</style>
