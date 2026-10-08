import { ref } from "vue";

export type FamilySection = "overview" | "vitals" | "fall" | "report" | "alarms" | "assistant" | "devices";

/* 模块级单例：家属端侧栏（AppShell 层）与 FamilyPage 共享当前分区 */
const activeSection = ref<FamilySection>("overview");

export function useFamilySection() {
  function setSection(section: FamilySection) {
    activeSection.value = section;
  }

  function resetSection() {
    activeSection.value = "overview";
  }

  return { activeSection, setSection, resetSection };
}
