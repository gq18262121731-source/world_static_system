<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { Trash2 } from "lucide-vue-next";
import type {
  CareTask,
  CareTaskPriority,
  CareTaskType,
  CommunityDashboardElderItem,
} from "../api/client";
import { useCareTasks } from "../composables/useCareTasks";

const props = defineProps<{
  elders: CommunityDashboardElderItem[];
}>();

const { tasks, doneCount, busyIds, loadTasks, toggleTask, createTask, deleteTask, errorText } =
  useCareTasks();

const showForm = ref(false);
const submitting = ref(false);
const draft = ref<{
  title: string;
  elderId: string;
  priority: CareTaskPriority;
  taskType: CareTaskType;
  note: string;
}>({ title: "", elderId: "", priority: "P2", taskType: "followup", note: "" });

function resetDraft() {
  draft.value = { title: "", elderId: "", priority: "P2", taskType: "followup", note: "" };
}

function closeForm() {
  showForm.value = false;
  resetDraft();
}

async function submitTask() {
  const title = draft.value.title.trim();
  if (!title || submitting.value) return;

  submitting.value = true;
  try {
    const created = await createTask({
      title,
      task_type: draft.value.taskType,
      priority: draft.value.priority,
      elder_id: draft.value.elderId || null,
      note: draft.value.note.trim(),
    });
    if (created) closeForm();
  } finally {
    submitting.value = false;
  }
}

function taskElderName(task: CareTask) {
  if (!task.elder_id) return "";
  return props.elders.find((item) => item.elder_id === task.elder_id)?.elder_name ?? "";
}

const summary = computed(() => `${doneCount.value}/${tasks.value.length} 已完成`);

onMounted(() => {
  void loadTasks();
});

defineExpose({ openForm: () => { showForm.value = true; } });
</script>

<template>
  <div class="task-panel">
    <div class="task-panel__head">
      <span class="task-panel__count">{{ summary }}</span>
      <button v-if="!showForm" type="button" class="task-panel__add" @click="showForm = true">
        + 新建任务
      </button>
    </div>

    <p v-if="errorText" class="feedback-banner feedback-error">{{ errorText }}</p>

    <form v-if="showForm" class="task-form" @submit.prevent="submitTask">
      <input
        v-model="draft.title"
        class="task-form__title"
        type="text"
        maxlength="120"
        placeholder="任务标题，例如：回访钱七确认夜间心率"
        required
      />
      <div class="task-form__row">
        <select v-model="draft.elderId" class="task-form__field">
          <option value="">不关联老人</option>
          <option v-for="elder in props.elders" :key="elder.elder_id" :value="elder.elder_id">
            {{ elder.elder_name }} · {{ elder.apartment }}
          </option>
        </select>
        <select v-model="draft.taskType" class="task-form__field">
          <option value="followup">随访</option>
          <option value="inspection">巡检</option>
          <option value="handover">交接</option>
        </select>
        <select v-model="draft.priority" class="task-form__field">
          <option value="P0">P0 立即</option>
          <option value="P1">P1 24 小时内</option>
          <option value="P2">P2 常规</option>
        </select>
      </div>
      <input
        v-model="draft.note"
        class="task-form__field task-form__note"
        type="text"
        maxlength="500"
        placeholder="备注（可选）"
      />
      <div class="task-form__actions">
        <button type="submit" class="task-form__submit" :disabled="submitting || !draft.title.trim()">
          {{ submitting ? "创建中…" : "创建任务" }}
        </button>
        <button type="button" class="task-form__cancel" @click="closeForm">取消</button>
      </div>
    </form>

    <div
      v-for="task in tasks"
      :key="task.id"
      class="task-row"
      :class="{ 'task-row--done': task.status === 'done' }"
    >
      <button
        type="button"
        class="task-row__box"
        :disabled="busyIds.has(task.id)"
        @click="toggleTask(task)"
      >
        {{ task.status === "done" ? "✓" : "" }}
      </button>
      <span class="task-row__info">
        <strong>{{ task.title }}</strong>
        <small>
          <template v-if="taskElderName(task)">{{ taskElderName(task) }} · </template>
          {{ task.status === "done" ? "已完成" : task.note || "待处理" }}
        </small>
      </span>
      <span class="task-row__pri">{{ task.priority }}</span>
      <button type="button" class="task-row__del" title="删除任务" @click="deleteTask(task.id)">
        <Trash2 :size="14" />
      </button>
    </div>

    <p v-if="!tasks.length && !showForm" class="task-panel__empty">
      暂无任务。点击「新建任务」安排随访、巡检或交接事项。
    </p>
  </div>
</template>

<style scoped>
.task-panel {
  display: grid;
  gap: 10px;
}

.task-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.task-panel__count {
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.task-panel__add {
  padding: 6px 14px;
  border: 1px solid color-mix(in srgb, var(--brand) 40%, transparent);
  border-radius: 999px;
  background: var(--surface-cyan);
  color: var(--brand);
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  white-space: nowrap;
}

.task-panel__add:hover {
  background: var(--surface-cyan-strong);
}

.task-panel__empty {
  margin: 4px 0 0;
  font-size: var(--fs-1);
  color: var(--text-muted);
}

/* 新建表单 */
.task-form {
  display: grid;
  gap: 9px;
  padding: 13px;
  border: 1px solid var(--line);
  border-radius: var(--radius-md);
  background: var(--panel-tinted);
}

.task-form__row {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr) minmax(0, 1fr);
  gap: 9px;
}

.task-form__title,
.task-form__field {
  height: 36px;
  padding: 0 11px;
  border: 1px solid var(--line);
  border-radius: var(--radius-sm);
  background: var(--panel-strong);
  color: var(--text-main);
  font-size: var(--fs-1);
  font-family: inherit;
  outline: none;
  min-width: 0;
}

.task-form__title:focus,
.task-form__field:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px var(--brand-glow);
}

.task-form__actions {
  display: flex;
  gap: 9px;
}

.task-form__submit,
.task-form__cancel {
  height: 34px;
  padding: 0 18px;
  border-radius: 999px;
  font-size: var(--fs-1);
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
}

.task-form__submit {
  border: none;
  background: linear-gradient(135deg, var(--brand), var(--brand-2));
  color: #ffffff;
}

.task-form__submit:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.task-form__cancel {
  border: 1px solid var(--line);
  background: var(--panel-strong);
  color: var(--text-sub);
}

/* 任务行 */
.task-row {
  display: flex;
  align-items: center;
  gap: 11px;
  padding: 10px 2px;
  border-bottom: 1px solid var(--line);
}

.task-row:last-of-type {
  border-bottom: none;
}

.task-row__box {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  display: grid;
  place-items: center;
  border: 1px solid var(--line-medium);
  border-radius: 5px;
  background: var(--panel-strong);
  color: var(--risk-low);
  font-size: var(--fs-1);
  font-weight: 700;
  cursor: pointer;
}

.task-row--done .task-row__box {
  border-color: var(--risk-low);
  background: var(--surface-success);
}

.task-row__info {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 2px;
}

.task-row__info strong {
  font-size: var(--fs-2);
  color: var(--text-main);
  font-weight: 600;
}

.task-row--done .task-row__info strong {
  color: var(--text-muted);
  text-decoration: line-through;
}

.task-row__info small {
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.task-row__pri {
  flex-shrink: 0;
  font-family: var(--font-mono);
  font-size: var(--fs-1);
  color: var(--text-muted);
}

.task-row__del {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border: 1px solid transparent;
  border-radius: 7px;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  opacity: 0;
  transition: opacity 150ms ease, color 150ms ease;
}

.task-row:hover .task-row__del {
  opacity: 1;
}

.task-row__del:hover {
  color: var(--risk-high);
  border-color: color-mix(in srgb, var(--risk-high) 35%, transparent);
}

@media (max-width: 720px) {
  .task-form__row {
    grid-template-columns: 1fr;
  }

  .task-row__del {
    opacity: 1;
  }
}
</style>
