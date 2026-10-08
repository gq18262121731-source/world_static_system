<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { ApiError, api, type AuthAccountPreview } from "./api/client";
import AppShell from "./components/layout/AppShell.vue";
import QuickLoginPanel from "./components/auth/QuickLoginPanel.vue";
import { useHashRouting } from "./composables/useHashRouting";
import { useSessionAuth } from "./composables/useSessionAuth";
import AccessDeniedPage from "./views/AccessDeniedPage.vue";
import CommunityAgentPage from "./views/CommunityAgentPage.vue";
import CommunityPage from "./views/CommunityPage.vue";
import CommunityTopologyPage from "./views/CommunityTopologyPage.vue";
import DebugPage from "./views/DebugPage.vue";
import FamilyPage from "./views/FamilyPage.vue";
import LoginPage from "./views/LoginPage.vue";
import MemberDevicePage from "./views/MemberDevicePage.vue";

const {
  authError,
  authLoading,
  isLoggedIn,
  login,
  loginPassword,
  loginUsername,
  logoutSession,
  restoreSession,
  sessionUser,
} = useSessionAuth();

const {
  activePage,
  allowedPages,
  canAccessDebug,
  disposeHashRouting,
  initHashRouting,
  resetToDefaultPage,
  routeTo,
  routeToNonce,
} = useHashRouting(sessionUser);

async function submitLogin() {
  const user = await login();
  if (!user) return;

  if (user.role === "family") {
    routeTo("family");
    return;
  }

  if (user.role === "community" || user.role === "admin") {
    routeTo("overview");
    return;
  }

  resetToDefaultPage();
}

function applyRegistrationLoginPrefill(payload: { username: string; password: string }) {
  loginUsername.value = payload.username;
  loginPassword.value = payload.password;
  authError.value = "";
}

function logout() {
  sessionUser.value = null;
  logoutSession();
  resetToDefaultPage();
}

/* ---- 演示账号悬浮球（全局）---- */
const quickAccounts = ref<AuthAccountPreview[]>([]);
const quickLoginError = ref("");
const switchingAccount = ref(false);

const quickSelectedAccount = computed(
  () => sessionUser.value?.username ?? loginUsername.value,
);

const quickHelperText = computed(() => {
  if (quickLoginError.value) return quickLoginError.value;
  if (!quickAccounts.value.length) return "当前没有可用的演示账号。";
  return isLoggedIn.value
    ? "点击账号可直接切换登录身份。"
    : "可直接选择演示账号并回填到登录表单，默认密码会同步写入。";
});

async function loadQuickAccounts() {
  try {
    quickLoginError.value = "";
    const accounts = await api.listMockAccounts();
    quickAccounts.value = accounts;
    if (!accounts.length) return;

    if (!isLoggedIn.value && !loginUsername.value.trim()) {
      const first = accounts[0];
      loginUsername.value = first.username;
      loginPassword.value = first.default_password;
    }
  } catch (error) {
    quickAccounts.value = [];
    if (error instanceof ApiError && error.detail) {
      quickLoginError.value = error.detail;
      return;
    }
    quickLoginError.value = "演示账号加载失败，请稍后重试。";
  }
}

async function handleQuickSelect(username: string) {
  const account = quickAccounts.value.find((item) => item.username === username);
  if (!account) return;
  if (isLoggedIn.value && sessionUser.value?.username === username) return;

  loginUsername.value = account.username;
  loginPassword.value = account.default_password;
  authError.value = "";

  if (!isLoggedIn.value) return;

  switchingAccount.value = true;
  try {
    sessionUser.value = null;
    logoutSession();
    await submitLogin();
  } finally {
    switchingAccount.value = false;
  }
}

watch(canAccessDebug, (allowed) => {
  if (!allowed && activePage.value === "debug") {
    const fallbackPage = allowedPages.value[0];
    if (fallbackPage && fallbackPage !== "none") {
      routeTo(fallbackPage);
      return;
    }
    resetToDefaultPage();
  }
});

onMounted(async () => {
  await restoreSession();
  initHashRouting();
  void loadQuickAccounts();
});

onUnmounted(() => {
  disposeHashRouting();
});
</script>

<template>
  <LoginPage
    v-if="!isLoggedIn"
    :login-username="loginUsername"
    :login-password="loginPassword"
    :auth-loading="authLoading"
    :auth-error="authError"
    @update:login-username="loginUsername = $event"
    @update:login-password="loginPassword = $event"
    @submit-login="submitLogin"
    @prefill-login="applyRegistrationLoginPrefill"
  />

  <AppShell
    v-else-if="sessionUser"
    :session-user="sessionUser"
    :active-page="activePage"
    :allowed-pages="allowedPages"
    :can-access-debug="canAccessDebug"
    @logout="logout"
    @navigate="routeTo"
  >
    <DebugPage
      v-if="activePage === 'debug'"
      :can-go-community="allowedPages.includes('overview')"
      @navigate="routeTo"
    />

    <CommunityPage
      v-else-if="activePage === 'overview'"
      :session-user="sessionUser"
      :can-access-debug="canAccessDebug"
    />

    <CommunityTopologyPage
      v-else-if="activePage === 'topology'"
      :session-user="sessionUser"
    />

    <CommunityAgentPage
      v-else-if="activePage === 'agent'"
      :session-user="sessionUser"
      :refresh-key="routeToNonce"
    />

    <FamilyPage
      v-else-if="activePage === 'family'"
      :session-user="sessionUser"
    />

    <MemberDevicePage
      v-else-if="activePage === 'members'"
      :session-user="sessionUser"
    />

    <AccessDeniedPage v-else />
  </AppShell>

  <QuickLoginPanel
    :accounts="quickAccounts"
    :helper-text="quickHelperText"
    :selected-account="quickSelectedAccount"
    :disabled="authLoading || switchingAccount"
    @select="handleQuickSelect"
  />
</template>
