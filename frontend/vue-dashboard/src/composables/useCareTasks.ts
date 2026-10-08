import { computed, ref } from "vue";
import {
  api,
  type CareTask,
  type CareTaskCreatePayload,
  type CareTaskUpdatePayload,
} from "../api/client";
import { getStoredSessionToken } from "./useSessionAuth";

/**
 * 模块级单例：侧栏「今日待办」与总览「随访任务」共享同一份数据，
 * 任一处勾选后另一处立即同步，避免两套状态不一致。
 */
const tasks = ref<CareTask[]>([]);
const loading = ref(false);
const errorText = ref("");
const busyIds = ref<Set<string>>(new Set());
let loadedOnce = false;

function markBusy(id: string, busy: boolean) {
  const next = new Set(busyIds.value);
  if (busy) next.add(id);
  else next.delete(id);
  busyIds.value = next;
}

function formatError(error: unknown, fallback: string) {
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function useCareTasks() {
  const pendingTasks = computed(() => tasks.value.filter((task) => task.status === "pending"));
  const doneCount = computed(() => tasks.value.filter((task) => task.status === "done").length);

  async function loadTasks(options: { force?: boolean } = {}) {
    if (loadedOnce && !options.force && tasks.value.length) return;
    const token = getStoredSessionToken();
    if (!token) return;

    loading.value = true;
    errorText.value = "";
    try {
      tasks.value = await api.listCareTasks(token, { limit: 50 });
      loadedOnce = true;
    } catch (error) {
      errorText.value = formatError(error, "任务加载失败，请稍后重试。");
    } finally {
      loading.value = false;
    }
  }

  async function toggleTask(task: CareTask) {
    const token = getStoredSessionToken();
    if (!token || busyIds.value.has(task.id)) return;

    const nextStatus = task.status === "done" ? "pending" : "done";
    markBusy(task.id, true);
    try {
      const updated = await api.updateCareTask(token, task.id, { status: nextStatus });
      tasks.value = tasks.value.map((item) => (item.id === updated.id ? updated : item));
    } catch (error) {
      errorText.value = formatError(error, "任务状态更新失败。");
    } finally {
      markBusy(task.id, false);
    }
  }

  async function createTask(payload: CareTaskCreatePayload) {
    const token = getStoredSessionToken();
    if (!token) return null;

    errorText.value = "";
    try {
      const created = await api.createCareTask(token, payload);
      tasks.value = [created, ...tasks.value];
      return created;
    } catch (error) {
      errorText.value = formatError(error, "任务创建失败。");
      return null;
    }
  }

  async function updateTask(taskId: string, payload: CareTaskUpdatePayload) {
    const token = getStoredSessionToken();
    if (!token) return null;
    try {
      const updated = await api.updateCareTask(token, taskId, payload);
      tasks.value = tasks.value.map((item) => (item.id === updated.id ? updated : item));
      return updated;
    } catch (error) {
      errorText.value = formatError(error, "任务更新失败。");
      return null;
    }
  }

  async function deleteTask(taskId: string) {
    const token = getStoredSessionToken();
    if (!token) return false;
    try {
      await api.deleteCareTask(token, taskId);
      tasks.value = tasks.value.filter((item) => item.id !== taskId);
      return true;
    } catch (error) {
      errorText.value = formatError(error, "任务删除失败。");
      return false;
    }
  }

  function resetTasks() {
    tasks.value = [];
    loadedOnce = false;
    errorText.value = "";
  }

  return {
    tasks,
    pendingTasks,
    doneCount,
    loading,
    errorText,
    busyIds,
    loadTasks,
    toggleTask,
    createTask,
    updateTask,
    deleteTask,
    resetTasks,
  };
}
