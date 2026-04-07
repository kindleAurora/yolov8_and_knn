<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">实时值守</p>
        <h2>画面监控</h2>
        <p class="page-header__text">
          汇总当前已配置视频流的设备画面，支持切换主画面并在页面内放大缩小查看。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="loadDevices">刷新设备</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>可预览设备</span>
        <strong>{{ previewDevices.length }}</strong>
        <p>已启用且配置了视频流地址的设备会进入监控画面墙。</p>
      </article>
      <article class="metric-card">
        <span>在线设备</span>
        <strong>{{ onlinePreviewCount }}</strong>
        <p>当前状态为在线的设备优先显示在监控列表前列。</p>
      </article>
      <article class="metric-card">
        <span>当前主画面</span>
        <strong>{{ activeDevice?.code || '暂无' }}</strong>
        <p>点击右侧设备列表或下方缩略图即可切换主监控画面。</p>
      </article>
      <article class="metric-card">
        <span>画面来源</span>
        <strong>{{ activeDevice ? '设备视频流' : '待配置' }}</strong>
        <p>RTSP 流会以抓帧方式在浏览器中展示，便于值守与联调。</p>
      </article>
    </section>

    <div class="monitor-layout">
      <article class="panel panel--monitor-stage">
        <header class="panel__header">
          <div>
            <h3>主监控画面</h3>
            <p class="panel__description">
              {{ activeDevice ? `${activeDevice.name} / ${activeDevice.install_location || '未设置安装位置'}` : '暂无可显示的主画面' }}
            </p>
          </div>
        </header>

        <DevicePreviewPanel
          v-if="activeDevice"
          :device="activeDevice"
          :refresh-ms="3500"
          show-controls
        />
        <p v-else class="entity-note">
          当前没有可用于监控的设备，请先在“设备管理”中填写视频流地址并启用设备。
        </p>
      </article>

      <article class="panel panel--monitor-sidebar">
        <header class="panel__header">
          <h3>设备切换</h3>
          <span class="panel__badge">{{ previewDevices.length }} 路</span>
        </header>

        <div class="monitor-device-list">
          <button
            v-for="device in previewDevices"
            :key="device.id"
            :class="['monitor-device-button', { 'monitor-device-button--active': device.id === activeDeviceId }]"
            type="button"
            @click="activeDeviceId = device.id"
          >
            <strong>{{ device.name }}</strong>
            <span>{{ device.code }} / {{ device.install_location || '未设置安装位置' }}</span>
            <small>{{ device.status === 'online' ? '在线画面优先刷新' : '当前处于离线或停用状态' }}</small>
          </button>
        </div>
      </article>
    </div>

    <article class="panel">
      <header class="panel__header">
        <h3>多画面缩略视图</h3>
        <p class="panel__description">点击任意缩略画面，即可把它切换到上方主监控位。</p>
      </header>

      <div v-if="previewDevices.length > 0" class="monitor-card-grid">
        <button
          v-for="device in previewDevices"
          :key="`thumb-${device.id}`"
          class="monitor-thumb-button"
          type="button"
          @click="activeDeviceId = device.id"
        >
          <DevicePreviewPanel :device="device" :refresh-ms="9000" compact />
        </button>
      </div>
      <p v-else class="entity-note">
        还没有可用于监控的设备，请先在设备管理中配置视频流地址。
      </p>
    </article>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';

import { listDevices } from '@/api/devices';
import DevicePreviewPanel from '@/components/monitor/DevicePreviewPanel.vue';
import type { DeviceSummary } from '@/types/device';

const devices = ref<DeviceSummary[]>([]);
const activeDeviceId = ref<number | null>(null);
const loadError = ref('');

const previewDevices = computed(() =>
  devices.value
    .filter((item) => item.is_enabled && Boolean(item.stream_url))
    .sort((left, right) => {
      const onlineDelta = Number(right.status === 'online') - Number(left.status === 'online');
      if (onlineDelta !== 0) {
        return onlineDelta;
      }
      return left.name.localeCompare(right.name, 'zh-CN');
    }),
);
const activeDevice = computed(
  () => previewDevices.value.find((item) => item.id === activeDeviceId.value) ?? previewDevices.value[0] ?? null,
);
const onlinePreviewCount = computed(
  () => previewDevices.value.filter((item) => item.status === 'online').length,
);

async function loadDevices() {
  loadError.value = '';

  try {
    devices.value = await listDevices();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载监控设备列表。';
  }
}

watch(
  previewDevices,
  (nextDevices) => {
    if (nextDevices.length === 0) {
      activeDeviceId.value = null;
      return;
    }

    if (!nextDevices.some((item) => item.id === activeDeviceId.value)) {
      activeDeviceId.value = nextDevices[0].id;
    }
  },
  { immediate: true },
);

onMounted(async () => {
  await loadDevices();
});
</script>
