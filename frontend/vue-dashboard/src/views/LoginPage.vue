<script setup lang="ts">
import { computed } from "vue";
import { Activity, Droplets, Heart, Sparkles, Thermometer, Zap } from "lucide-vue-next";
import AuthCard from "../components/auth/AuthCard.vue";
import AuthShell from "../components/auth/AuthShell.vue";
import { useAuthFlow, type AuthCompletedCredentials, type AuthFlowRole } from "../composables/useAuthFlow";
import AuthLoginPage from "./auth/AuthLoginPage.vue";
import RegisterFlow from "./auth/RegisterFlow.vue";

defineProps<{
  loginUsername: string;
  loginPassword: string;
  authLoading: boolean;
  authError: string;
}>();

const emit = defineEmits<{
  "update:loginUsername": [value: string];
  "update:loginPassword": [value: string];
  submitLogin: [];
  prefillLogin: [payload: { username: string; password: string; role: AuthFlowRole }];
}>();

const authFlow = useAuthFlow();

const authCardVariant = computed(() => {
  return authFlow.currentStep.value === "register" ? "register" : "login";
});

function handleRegistrationComplete(payload: AuthCompletedCredentials) {
  authFlow.goToLogin();
  emit("prefillLogin", payload);
}
</script>

<template>
  <AuthShell>
    <div class="login-page-layout">
      <!-- 左：品牌区 -->
      <section class="login-hero">
        <div class="login-hero__chips" aria-hidden="true">
          <div class="hero-chip hero-chip--1">
            <span class="hero-chip__icon"><Heart :size="16" /></span>
            <span><b>76 bpm</b><i>心率 · 实时</i></span>
          </div>
          <div class="hero-chip hero-chip--2">
            <span class="hero-chip__icon"><Droplets :size="16" /></span>
            <span><b>97 %</b><i>血氧 SpO₂</i></span>
          </div>
          <div class="hero-chip hero-chip--3">
            <span class="hero-chip__icon"><Thermometer :size="16" /></span>
            <span><b>36.5 °C</b><i>体温 · 平稳</i></span>
          </div>
        </div>

        <div class="login-hero__brand">
          <span class="login-hero__logo"><Heart :size="26" :stroke-width="2.2" /></span>
          <span>
            <b>智慧养老健康监测平台</b>
            <i>AI-POWERED HEALTH MONITORING</i>
          </span>
        </div>

        <div class="login-hero__mid">
          <h2>每一次心跳，<br>都有人守护。</h2>
          <p>面向社区与家庭的一体化康养监护：手环体征实时采集，异常自动告警闭环，AI 帮你读懂每一条曲线。</p>
          <div class="login-hero__feats">
            <div class="hero-feat">
              <span class="hero-feat__icon"><Activity :size="18" /></span>
              <span><b>实时体征监测</b><i>心率 · 血氧 · 体温 · 秒级采集</i></span>
            </div>
            <div class="hero-feat">
              <span class="hero-feat__icon"><Zap :size="18" /></span>
              <span><b>智能告警闭环</b><i>分级告警，家属与值守同步通知</i></span>
            </div>
            <div class="hero-feat">
              <span class="hero-feat__icon"><Sparkles :size="18" /></span>
              <span><b>AI 健康洞察</b><i>智能体自动生成趋势解读与简报</i></span>
            </div>
          </div>
        </div>

        <div class="login-hero__foot">
          <div class="login-hero__stats">
            <span class="hero-stat"><b>11</b><i>监护对象</i></span>
            <span class="hero-stat"><b>24h</b><i>持续值守</i></span>
            <span class="hero-stat"><b>99.2%</b><i>采集成功率</i></span>
          </div>
          <span class="login-hero__copyright">© 2026 智慧康养 · AIOT CARE</span>
        </div>
      </section>

      <!-- 右：表单列 -->
      <section class="login-panel">
        <AuthCard :variant="authCardVariant">
          <AuthLoginPage
            v-if="authFlow.currentStep.value === 'login'"
            :login-username="loginUsername"
            :login-password="loginPassword"
            :auth-loading="authLoading"
            :auth-error="authError"
            @update:login-username="emit('update:loginUsername', $event)"
            @update:login-password="emit('update:loginPassword', $event)"
            @submit="emit('submitLogin')"
            @open-register="authFlow.openRegister()"
          />

          <RegisterFlow
            v-else-if="authFlow.currentStep.value === 'register'"
            @cancel="authFlow.goToLogin()"
            @complete="handleRegistrationComplete"
          />
        </AuthCard>
      </section>
    </div>
  </AuthShell>
</template>

<style scoped>
.login-page-layout {
  display: flex;
  align-items: stretch;
  gap: 48px;
  width: 100%;
}

/* ---- 左：品牌区 ---- */
.login-hero {
  position: relative;
  flex: 1 1 52%;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 40px;
  color: #ffffff;
  padding: 26px 12px;
}

.login-hero__brand {
  display: flex;
  align-items: center;
  gap: 14px;
}

.login-hero__logo {
  width: 52px;
  height: 52px;
  border-radius: 15px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.3);
  backdrop-filter: blur(6px);
  display: grid;
  place-items: center;
  color: #ffffff;
}

.login-hero__brand b {
  display: block;
  font-size: 21.5px;
  font-weight: 800;
  letter-spacing: 0.01em;
}

.login-hero__brand i {
  display: block;
  font-style: normal;
  font-size: 12px;
  letter-spacing: 0.18em;
  opacity: 0.75;
  margin-top: 4px;
  font-weight: 600;
}

.login-hero__mid {
  max-width: 460px;
}

.login-hero__mid h2 {
  margin: 0;
  font-size: 38px;
  font-weight: 800;
  line-height: 1.35;
  letter-spacing: 0.01em;
}

.login-hero__mid > p {
  margin: 12px 0 0;
  font-size: 15.5px;
  opacity: 0.82;
  line-height: 1.7;
}

.login-hero__feats {
  margin-top: 30px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.hero-feat {
  display: flex;
  align-items: center;
  gap: 13px;
}

.hero-feat__icon {
  width: 40px;
  height: 40px;
  flex-shrink: 0;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.13);
  border: 1px solid rgba(255, 255, 255, 0.24);
  display: grid;
  place-items: center;
  color: #ffffff;
}

.hero-feat b {
  display: block;
  font-size: 16px;
  font-weight: 700;
}

.hero-feat i {
  display: block;
  font-style: normal;
  font-size: 13.5px;
  opacity: 0.72;
  margin-top: 2px;
}

.login-hero__foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.login-hero__stats {
  display: flex;
  gap: 26px;
}

.hero-stat b {
  display: block;
  font-family: var(--font-mono, 'Consolas', monospace);
  font-size: 24.5px;
  font-weight: 700;
}

.hero-stat i {
  display: block;
  font-style: normal;
  font-size: 12.5px;
  opacity: 0.7;
  margin-top: 3px;
}

.login-hero__copyright {
  font-size: 12.5px;
  opacity: 0.55;
}

/* 悬浮体征卡 */
.login-hero__chips {
  position: absolute;
  inset: 0;
  pointer-events: none;
}

.hero-chip {
  position: absolute;
  display: flex;
  align-items: center;
  gap: 10px;
  background: rgba(255, 255, 255, 0.13);
  border: 1px solid rgba(255, 255, 255, 0.28);
  backdrop-filter: blur(10px);
  border-radius: 15px;
  padding: 11px 15px;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.18);
  animation: chipBob 5.5s ease-in-out infinite;
}

.hero-chip__icon {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  flex-shrink: 0;
  background: rgba(255, 255, 255, 0.2);
  display: grid;
  place-items: center;
  color: #ffffff;
}

.hero-chip b {
  display: block;
  font-family: var(--font-mono, 'Consolas', monospace);
  font-size: 18px;
  font-weight: 700;
  color: #ffffff;
}

.hero-chip i {
  display: block;
  font-style: normal;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.75);
  margin-top: 1px;
}

.hero-chip--1 { top: 22%; right: 6%; animation-delay: 0s; }
.hero-chip--2 { top: 52%; right: 14%; animation-delay: 1.8s; }
.hero-chip--3 { top: 72%; right: 4%; animation-delay: 3.6s; }

@keyframes chipBob {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-10px); }
}

/* ---- 右：表单列 ---- */
.login-panel {
  flex: 0 1 460px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  min-width: 0;
}

/* 响应式：窄屏纵向堆叠 */
@media (max-width: 980px) {
  .login-page-layout {
    flex-direction: column;
    gap: 28px;
  }

  .login-hero {
    flex: none;
    gap: 26px;
  }

  .login-hero__chips {
    display: none;
  }

  .login-panel {
    flex: none;
    width: 100%;
  }
}
</style>
