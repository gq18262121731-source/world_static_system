<script setup lang="ts">
import PageHeader from "../components/layout/PageHeader.vue";
</script>

<template>
  <section class="page-stack">
    <PageHeader
      eyebrow="Access"
      title="当前角色暂无登录后页面权限"
      description="当前账号尚未分配可访问的业务页面，请联系管理员开通对应权限。"
      :meta="['请联系管理员确认角色权限', '当前页面不展示局部业务状态']"
    />

    <article class="panel">
      <div class="state-block state-large">
        <strong>未分配可访问页面</strong>
        <p>当前账号已登录，但暂时没有可进入的主业务页面。请检查当前角色是否需要分配社区、家属或调试相关权限。</p>
      </div>
    </article>
  </section>
</template>
