<template>
  <main class="login-page">
    <section class="login-panel">
      <div class="login-panel__hero">
        <p class="login-panel__eyebrow">阶段 3 访问入口</p>
        <h1>登录牛只智能监控平台</h1>
        <p class="login-panel__text">
          本阶段已经接入推理服务、行为事件入库和阶段化演示工作台。
        </p>
      </div>

      <form class="login-form" @submit.prevent="handleSubmit">
        <label class="field">
          <span>用户名</span>
          <input v-model.trim="username" type="text" autocomplete="username" placeholder="请输入用户名" />
        </label>

        <label class="field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码" />
        </label>

        <button class="primary-button" type="submit" :disabled="submitting">
          {{ submitting ? '登录中...' : '登录' }}
        </button>

        <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>
      </form>

      <div class="credential-cards">
        <article class="credential-card">
          <h2>管理员账号</h2>
          <p>`admin` / `admin123`</p>
          <span>可新增、编辑、停用和删除设备。</span>
        </article>
        <article class="credential-card">
          <h2>普通账号</h2>
          <p>`viewer` / `viewer123`</p>
          <span>可查看设备，并在同一农场范围内管理区域。</span>
        </article>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';

import { useAuthStore } from '@/stores/auth';

const authStore = useAuthStore();
const route = useRoute();
const router = useRouter();

const username = ref('admin');
const password = ref('admin123');
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
