<script setup lang="ts">
import {
  Activity,
  BellRing,
  FileText,
  Heart,
  PersonStanding,
  Sparkles,
  Watch,
  type LucideIcon,
} from "lucide-vue-next";
import type { SessionUser } from "../../api/client";
import { useFamilySection, type FamilySection } from "../../composables/useFamilySection";

defineProps<{
  sessionUser: SessionUser;
}>();

const { activeSection, setSection } = useFamilySection();

type SectionItem = {
  id: FamilySection;
  label: string;
  description: string;
  icon: LucideIcon;
};

const sections: SectionItem[] = [
  { id: "overview", label: "今日安心", description: "家人状态总览", icon: Heart },
  { id: "vitals", label: "实时体征", description: "指标详情与趋势", icon: Activity },
  { id: "fall", label: "跌倒告警", description: "AI 跌倒监测", icon: PersonStanding },
  { id: "report", label: "健康报告", description: "评估结论与报告", icon: FileText },
  { id: "alarms", label: "告警动态", description: "异常与历史记录", icon: BellRing },
  { id: "assistant", label: "家庭智能体", description: "问答与照护建议", icon: Sparkles },
  { id: "devices", label: "设备管理", description: "手环状态与电量", icon: Watch },
];
</script>

<template>
  <nav class="family-nav" aria-label="家属导航">
    <div class="family-nav__header">
      <p class="family-nav__eyebrow">Family Console</p>
      <h3 class="family-nav__title">家属照护台</h3>
      <p class="family-nav__subtitle">安心 · 体征 · 报告 · 智能体</p>
    </div>

    <div class="family-nav__profile">
      <span class="family-nav__avatar">{{ sessionUser.name.slice(0, 1) }}</span>
      <span class="family-nav__profile-info">
        <strong>{{ sessionUser.name }}</strong>
        <small>家属查看</small>
      </span>
      <span class="family-nav__badge">● 已关联</span>
    </div>

    <div class="family-nav__items">
      <button
        v-for="item in sections"
        :key="item.id"
        type="button"
        class="family-nav__item"
        :class="{ 'family-nav__item--active': activeSection === item.id }"
        @click="setSection(item.id)"
      >
        <div class="family-nav__icon">
          <component :is="item.icon" :size="19" />
        </div>
        <div class="family-nav__content">
          <strong>{{ item.label }}</strong>
          <small>{{ item.description }}</small>
        </div>
        <div class="family-nav__indicator"></div>
      </button>
    </div>
  </nav>
</template>

<style scoped>
.family-nav {
  display: grid;
  gap: 14px;
  padding: 12px 6px;
}

.family-nav__header {
  padding: 4px 4px 14px;
  border-bottom: 1px solid var(--line);
}

.family-nav__eyebrow {
  margin: 0;
  font-size: 0.64rem;
  color: var(--brand);
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.family-nav__title {
  margin: 6px 0 0;
  font-size: 1.25rem;
  font-weight: 800;
  color: var(--text-main);
  letter-spacing: -0.02em;
}

.family-nav__subtitle {
  margin: 5px 0 0;
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.6;
}

.family-nav__profile {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 12px;
  border-radius: var(--radius-md);
  border: 1px solid var(--line);
  background: var(--panel-tinted);
}

.family-nav__avatar {
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

.family-nav__profile-info {
  flex: 1;
  min-width: 0;
}

.family-nav__profile-info strong {
  display: block;
  font-size: 15.5px;
  font-weight: 700;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.family-nav__profile-info small {
  display: block;
  font-size: 12.5px;
  color: var(--text-muted);
  margin-top: 2px;
}

.family-nav__badge {
  font-size: 12px;
  font-weight: 700;
  color: var(--risk-low);
  background: var(--surface-success);
  padding: 3px 8px;
  border-radius: 999px;
  white-space: nowrap;
}

.family-nav__items {
  display: grid;
  gap: 9px;
}

.family-nav__item {
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

.family-nav__item::before {
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

.family-nav__item:hover {
  border-color: var(--line-strong);
  transform: translateY(-2px);
  box-shadow: var(--shadow);
}

.family-nav__item--active {
  background: var(--surface-cyan);
  border-color: color-mix(in srgb, var(--brand) 45%, transparent);
}

.family-nav__item--active::before {
  opacity: 1;
}

.family-nav__icon {
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

.family-nav__item--active .family-nav__icon {
  background: linear-gradient(135deg, var(--brand-2) 0%, var(--brand) 100%);
  border-color: transparent;
  color: #ffffff;
  box-shadow: 0 4px 12px var(--brand-glow);
}

.family-nav__content {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.family-nav__content strong {
  font-size: 0.92rem;
  font-weight: 700;
  color: var(--text-sub);
  letter-spacing: -0.01em;
}

.family-nav__content small {
  font-size: 0.74rem;
  color: var(--text-muted);
  line-height: 1.4;
}

.family-nav__item--active .family-nav__content strong {
  color: var(--text-main);
  font-weight: 800;
}

.family-nav__item--active .family-nav__content small {
  color: var(--text-sub);
}

.family-nav__indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: transparent;
  transition: all 200ms ease;
  flex-shrink: 0;
}

.family-nav__item--active .family-nav__indicator {
  background: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-glow);
}
</style>
