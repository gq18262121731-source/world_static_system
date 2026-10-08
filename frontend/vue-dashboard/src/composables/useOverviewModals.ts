import { ref } from "vue";

/**
 * 总览页弹窗的共享开关。
 * 做成模块级单例是因为触发点分散在不同层级：顶栏铃铛在 AppShell 里，
 * 快捷操作在 CommunityPage 里，两者要控制同一批弹窗。
 */
const alertsOpen = ref(false);
const reportOpen = ref(false);
const taskOpen = ref(false);

export function useOverviewModals() {
  return {
    alertsOpen,
    reportOpen,
    taskOpen,
    openAlerts: () => {
      alertsOpen.value = true;
    },
    openReport: () => {
      reportOpen.value = true;
    },
    openTask: () => {
      taskOpen.value = true;
    },
    closeAll: () => {
      alertsOpen.value = false;
      reportOpen.value = false;
      taskOpen.value = false;
    },
  };
}
