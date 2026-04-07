<template>
  <div class="app-shell">
    <aside class="app-shell__sidebar">
      <div class="brand-block">
        <p class="brand-block__eyebrow">阶段 3</p>
        <h1>牛只智能监控平台</h1>
        <p class="brand-block__text">
          当前阶段已经打通推理服务接入、行为事件写库与结果展示链路。
        </p>
      </div>

      <nav class="nav-links">
        <RouterLink to="/" class="nav-link">总览</RouterLink>
        <RouterLink to="/monitor" class="nav-link">画面监控</RouterLink>
        <RouterLink to="/devices" class="nav-link">设备管理</RouterLink>
        <RouterLink to="/zones" class="nav-link">区域管理</RouterLink>
        <RouterLink to="/events" class="nav-link">行为事件</RouterLink>
      </nav>

      <a class="docs-link" :href="docsUrl" target="_blank" rel="noreferrer">打开接口文档</a>
    </aside>

    <main class="app-shell__main">
      <header class="topbar">
        <div>
          <p class="topbar__label">当前登录</p>
          <strong>{{ authStore.currentUser?.display_name }}</strong>
          <span class="topbar__meta">
            {{ authStore.currentUser?.farm.name }} / {{ authStore.isAdmin ? '管理员' : '普通用户' }}
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

import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const router = useRouter();
const docsUrl = `${import.meta.env.VITE_API_BASE_URL}/docs`;

async function handleLogout() {
  await authStore.logout();
  await router.push({ name: 'login' });
}
</script>
