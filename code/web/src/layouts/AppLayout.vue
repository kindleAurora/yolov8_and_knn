<template>
  <div class="app-shell">
    <aside class="app-shell__sidebar">
      <div class="brand-block">
        <p class="brand-block__eyebrow">{{ APP_OPERATION_LABEL }}</p>
        <h1>{{ APP_NAME }}</h1>
        <p class="brand-block__text">{{ APP_SUBTITLE }}，{{ APP_DESCRIPTION }}</p>
      </div>

      <nav class="nav-links">
        <RouterLink to="/" class="nav-link">系统总览</RouterLink>
        <RouterLink to="/monitor" class="nav-link">监控中心</RouterLink>
        <RouterLink to="/devices" class="nav-link">设备资产</RouterLink>
        <RouterLink to="/zones" class="nav-link">区域配置</RouterLink>
        <RouterLink to="/events" class="nav-link">事件中心</RouterLink>
        <RouterLink to="/alerts" class="nav-link">告警中心</RouterLink>
        <RouterLink to="/rules" class="nav-link">规则配置</RouterLink>
        <RouterLink to="/history" class="nav-link">历史分析</RouterLink>
      </nav>

      <a class="docs-link" :href="docsUrl" target="_blank" rel="noreferrer">查看 API 文档</a>
    </aside>

    <main class="app-shell__main">
      <header class="topbar">
        <div>
          <p class="topbar__label">当前账号</p>
          <strong>{{ authStore.currentUser?.display_name }}</strong>
          <span class="topbar__meta">
            {{ authStore.currentUser?.farm.name }} / {{ authStore.isAdmin ? '系统管理员' : '观察账号' }}
          </span>
        </div>
        <button class="ghost-button" type="button" @click="handleLogout">退出登录</button>
      </header>

      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

import { APP_DESCRIPTION, APP_NAME, APP_OPERATION_LABEL, APP_SUBTITLE } from '@/config/branding';
import { apiDocsUrl } from '@/config/runtime';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const router = useRouter();
const docsUrl = apiDocsUrl;

async function handleLogout() {
  await authStore.logout();
  await router.push({ name: 'login' });
}
</script>
