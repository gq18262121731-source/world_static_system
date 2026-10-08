<template>
  <section class="modern-auth-shell">
    <!-- 动态背景 -->
    <div class="modern-auth-background" aria-hidden="true">
      <!-- 渐变背景 -->
      <div class="modern-auth-gradient"></div>

      <!-- 动态网格 -->
      <div class="modern-auth-grid">
        <div class="modern-auth-grid-line" v-for="i in 20" :key="`v-${i}`" :style="{ left: `${i * 5}%` }"></div>
        <div class="modern-auth-grid-line modern-auth-grid-line--horizontal" v-for="i in 12" :key="`h-${i}`" :style="{ top: `${i * 8.33}%` }"></div>
      </div>

      <!-- 浮动元素 -->
      <div class="modern-auth-floats">
        <div class="modern-auth-float modern-auth-float--1"></div>
        <div class="modern-auth-float modern-auth-float--2"></div>
        <div class="modern-auth-float modern-auth-float--3"></div>
        <div class="modern-auth-float modern-auth-float--4"></div>
      </div>

      <!-- ECG 心电图效果：pathLength 归一化，画入后滑出，无残段 -->
      <svg class="modern-auth-ecg" viewBox="0 0 1600 900" preserveAspectRatio="none">
        <path
          class="modern-auth-ecg-line modern-auth-ecg-line--main"
          pathLength="1000"
          d="M-80 300 L280 300 L340 300 L372 262 L404 340 L436 236 L468 300 L880 300 L940 300 L972 274 L1004 326 L1036 248 L1068 300 L1680 300"
          stroke="rgba(255, 255, 255, 0.45)"
          stroke-width="2.5"
          fill="none"
        />
        <path
          class="modern-auth-ecg-line modern-auth-ecg-line--secondary"
          pathLength="1000"
          d="M-80 640 L240 640 L300 640 L328 616 L356 662 L384 596 L412 640 L820 640 L880 640 L908 622 L936 656 L964 606 L992 640 L1680 640"
          stroke="rgba(255, 255, 255, 0.18)"
          stroke-width="2"
          fill="none"
        />
      </svg>
    </div>

    <!-- 内容区域 -->
    <div class="modern-auth-content">
      <div class="modern-auth-container">
        <slot />
      </div>
    </div>
  </section>
</template>

<style scoped>
.modern-auth-shell {
  position: relative;
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  overflow: hidden;
}

/* 背景层 */
.modern-auth-background {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: hidden;
}

/* 渐变背景：医疗器械风深青 */
.modern-auth-gradient {
  position: absolute;
  inset: 0;
  background: linear-gradient(155deg,
    #0b3b4c 0%,
    #0d5468 30%,
    #0e6280 52%,
    #0a4356 76%,
    #083245 100%
  );
}

.modern-auth-gradient::before {
  content: '';
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 22% 28%, rgba(8, 145, 178, 0.28) 0%, transparent 52%),
              radial-gradient(circle at 78% 72%, rgba(13, 148, 99, 0.16) 0%, transparent 50%);
  animation: gradientShift 15s ease-in-out infinite;
}

@keyframes gradientShift {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

/* 网格效果 */
.modern-auth-grid {
  position: absolute;
  inset: 0;
  opacity: 0.16;
}

.modern-auth-grid-line {
  position: absolute;
  background: linear-gradient(to bottom, transparent, rgba(255, 255, 255, 0.5), transparent);
  width: 1px;
  height: 100%;
  animation: gridPulse 3s ease-in-out infinite;
}

.modern-auth-grid-line--horizontal {
  background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.5), transparent);
  width: 100%;
  height: 1px;
  animation: gridPulse 4s ease-in-out infinite;
}

@keyframes gridPulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.7; }
}

/* 浮动元素 */
.modern-auth-floats {
  position: absolute;
  inset: 0;
}

.modern-auth-float {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.4;
  animation: float 20s ease-in-out infinite;
}

.modern-auth-float--1 {
  width: 400px;
  height: 400px;
  background: radial-gradient(circle, rgba(8, 145, 178, 0.45), transparent);
  top: 10%;
  left: 10%;
  animation-delay: 0s;
}

.modern-auth-float--2 {
  width: 300px;
  height: 300px;
  background: radial-gradient(circle, rgba(13, 148, 99, 0.30), transparent);
  top: 60%;
  right: 15%;
  animation-delay: 5s;
}

.modern-auth-float--3 {
  width: 350px;
  height: 350px;
  background: radial-gradient(circle, rgba(14, 116, 144, 0.35), transparent);
  bottom: 20%;
  left: 20%;
  animation-delay: 10s;
}

.modern-auth-float--4 {
  width: 250px;
  height: 250px;
  background: radial-gradient(circle, rgba(8, 145, 178, 0.32), transparent);
  top: 40%;
  right: 30%;
  animation-delay: 15s;
}

@keyframes float {
  0%, 100% {
    transform: translate(0, 0) scale(1);
  }
  25% {
    transform: translate(30px, -30px) scale(1.1);
  }
  50% {
    transform: translate(-20px, 20px) scale(0.9);
  }
  75% {
    transform: translate(20px, 30px) scale(1.05);
  }
}

/* ECG 心电图 */
.modern-auth-ecg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.8;
}

.modern-auth-ecg-line {
  stroke-linecap: round;
  stroke-linejoin: round;
  stroke-dasharray: 1000 1000;
  stroke-dashoffset: 1000;
}

.modern-auth-ecg-line--main {
  animation: ecgSweep 7s linear infinite;
}

.modern-auth-ecg-line--secondary {
  animation: ecgSweep 7s linear infinite 3.5s;
}

/* 先完整画入（0→55%），再从起点滑出（55%→100%），保证任意时刻只有一条连续线 */
@keyframes ecgSweep {
  0%   { stroke-dashoffset: 1000; }
  55%  { stroke-dashoffset: 0; }
  100% { stroke-dashoffset: -1000; }
}

/* 内容区域 */
.modern-auth-content {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 1240px;
  display: flex;
  justify-content: center;
  align-items: center;
}

.modern-auth-container {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

/* 响应式 */
@media (max-width: 768px) {
  .modern-auth-shell {
    padding: 16px;
  }

  .modern-auth-float {
    filter: blur(40px);
  }

  .modern-auth-float--1,
  .modern-auth-float--2,
  .modern-auth-float--3,
  .modern-auth-float--4 {
    width: 200px;
    height: 200px;
  }
}
</style>
