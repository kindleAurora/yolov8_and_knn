<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-panel__hero">
        <p class="login-panel__eyebrow">{{ APP_ACCESS_LABEL }}</p>
        <h1>{{ APP_NAME }}</h1>
        <p class="login-panel__text">
          {{ APP_SUBTITLE }}，面向智慧牧场提供设备接入、实时监控与行为事件管理能力。
        </p>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <label class="field">
          <span>用户名</span>
          <input v-model.trim="username" type="text" autocomplete="username" placeholder="请输入账号名称" />
        </label>

        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </label>

        <button class="primary-button" type="submit" :disabled="submitting">
          {{ submitting ? '登录中...' : '进入系统' }}
        </button>

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      </form>

      <div class="credential-cards">
        <article class="credential-card">
          <h2>系统管理员</h2>
          <p>`admin` / `admin123`</p>
          <span>具备设备、区域和行为事件的完整管理权限。</span>
        </article>
        <article class="credential-card">
          <h2>观察账号</h2>
          <p>`viewer` / `viewer123`</p>
          <span>可查看设备运行状态，并维护所属农场的区域配置。</span>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { APP_ACCESS_LABEL, APP_NAME, APP_SUBTITLE } from '@/config/branding';
import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const username = ref('');
const password = ref('');
const submitting = ref(false);
const errorMessage = ref('');

async function handleSubmit() {
  submitting.value = true;
  errorMessage.value = '';

  try {
    await authStore.login(username.value, password.value);
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/';
    await router.push(redirect);
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登录失败。';
  } finally {
    submitting.value = false;
  }
}
</script>
