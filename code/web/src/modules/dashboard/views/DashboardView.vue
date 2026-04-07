<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">平台总览</p>
        <h2>当前工作台</h2>
        <p class="page-header__text">
          当前版本已经打通推理服务接入、行为事件写库和前端展示的完整链路。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>设备总数</span>
        <strong>{{ deviceCount }}</strong>
        <p>{{ authStore.isAdmin ? '管理员可维护设备全生命周期。' : '普通用户在设备页为只读模式。' }}</p>
      </article>
      <article class="metric-card">
        <span>在线设备</span>
        <strong>{{ onlineDeviceCount }}</strong>
        <p>基于当前设备状态列表实时统计。</p>
      </article>
      <article class="metric-card">
        <span>区域总数</span>
        <strong>{{ zoneCount }}</strong>
        <p>区域数据默认按当前农场隔离。</p>
      </article>
      <article class="metric-card">
        <span>今日事件</span>
        <strong>{{ todayEventCount }}</strong>
        <p>已写入数据库的当日行为事件数量。</p>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>平台健康状态</h3>
          <span class="panel__badge">{{ loadStateLabel }}</span>
        </header>
        <ul class="service-list">
          <li v-for="dependency in dependencies" :key="dependency.name" class="service-item">
            <div>
              <strong>{{ formatDependencyName(dependency.name) }}</strong>
              <p>{{ dependency.detail }}</p>
            </div>
            <span :class="['service-badge', `service-badge--${dependency.status}`]">
              {{ formatDependencyStatus(dependency.status) }}
            </span>
          </li>
        </ul>
        <p class="summary">{{ dependencySummary }}</p>
        <p v-if="platformStore.errorMessage" class="error-text">{{ platformStore.errorMessage }}</p>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>快捷入口</h3>
        </header>
        <div class="action-list">
          <RouterLink class="action-card" to="/monitor">
            <strong>进入画面监控</strong>
            <span>查看在线摄像头预览，并在监控页切换主画面进行放大缩小。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/devices">
            <strong>进入设备管理</strong>
            <span>查看设备档案、流地址与启停状态。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/zones">
            <strong>进入区域管理</strong>
            <span>通过可视化画布绘制区域，并为指定设备绑定语义区域。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/events">
            <strong>进入行为事件工作台</strong>
            <span>调用推理服务、导入结果并查看最新行为事件。</span>
          </RouterLink>
          <a class="action-card" :href="docsUrl" target="_blank" rel="noreferrer">
            <strong>查看接口文档</strong>
            <span>检查 `/auth`、`/devices` 与 `/zones` 的契约细节。</span>
          </a>
        </div>
      </article>
    </section>

    <article class="panel">
      <header class="panel__header">
        <h3>在线监控预览</h3>
        <RouterLink class="ghost-button" to="/monitor">打开画面监控</RouterLink>
      </header>
      <div v-if="previewDevices.length > 0" class="monitor-card-grid">
        <DevicePreviewPanel
          v-for="device in previewDevices"
          :key="device.id"
          :device="device"
          :refresh-ms="8000"
          compact
        />
      </div>
      <p v-else class="entity-note">
        当前没有可预览的已启用设备，请先在“设备管理”中配置视频流地址。
      </p>
    </article>

    <article class="panel">
      <header class="panel__header">
        <h3>最近行为事件</h3>
        <RouterLink class="ghost-button" to="/events">打开事件工作台</RouterLink>
      </header>
      <div class="stack-list">
        <article v-for="event in recentEvents" :key="event.id" class="entity-card">
          <div class="entity-card__header">
            <div>
              <strong>{{ event.behavior_type }}</strong>
              <p>{{ event.device_name || event.device_code }} / {{ formatSourceType(event.source_type) }}</p>
            </div>
            <span class="service-badge service-badge--up">{{ formatConfidence(event.confidence) }}</span>
          </div>

          <dl class="entity-grid">
            <div>
              <dt>牛只数量</dt>
              <dd>{{ event.cow_count }}</dd>
            </div>
            <div>
              <dt>事件时间</dt>
              <dd>{{ formatDate(event.occurred_at) }}</dd>
            </div>
            <div>
              <dt>区域</dt>
              <dd>{{ event.zone_name || '未命中区域' }}</dd>
            </div>
            <div>
              <dt>模型</dt>
              <dd>{{ event.model_name }} / {{ event.model_version }}</dd>
            </div>
          </dl>
        </article>
        <p v-if="recentEvents.length === 0" class="entity-note">
          还没有行为事件记录，可以前往“行为事件工作台”导入一条推理结果。
        </p>
      </div>
    </article>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { listDevices } from '@/api/devices';
import { fetchBehaviorEventSummary } from '@/api/events';
import { listZones } from '@/api/zones';
import DevicePreviewPanel from '@/components/monitor/DevicePreviewPanel.vue';
import { useAuthStore } from '@/stores/auth';
import { usePlatformStore } from '@/stores/platform';
import type { DeviceSummary } from '@/types/device';
import type { BehaviorEventSummary, EventSourceType } from '@/types/event';
import type { ServiceDependency } from '@/types/health';
import { summarizeDependencies } from '@/utils/health';

const authStore = useAuthStore();
const platformStore = usePlatformStore();

const deviceCount = ref(0);
const onlineDeviceCount = ref(0);
const zoneCount = ref(0);
const todayEventCount = ref(0);
const recentEvents = ref<BehaviorEventSummary[]>([]);
const devices = ref<DeviceSummary[]>([]);
const docsUrl = `${import.meta.env.VITE_API_BASE_URL}/docs`;
const dependencyNameMap: Record<string, string> = {
  postgres: '数据库服务',
  redis: '缓存服务',
  'inference-service': '推理服务',
};

const defaultDependencies: ServiceDependency[] = [
  { name: 'postgres', status: 'unknown', detail: '等待 API 完成健康检查探测。' },
  { name: 'redis', status: 'unknown', detail: '等待 API 完成健康检查探测。' },
  { name: 'inference-service', status: 'unknown', detail: '等待 API 完成健康检查探测。' },
];

const dependencies = computed(() => platformStore.health?.dependencies ?? defaultDependencies);
const previewDevices = computed(() =>
  devices.value
    .filter((item) => item.is_enabled && Boolean(item.stream_url))
    .sort((left, right) => Number(right.status === 'online') - Number(left.status === 'online'))
    .slice(0, 3),
);
const dependencySummary = computed(() =>
  summarizeDependencies(
    dependencies.value.map((item) => ({
      ...item,
      name: formatDependencyName(item.name),
    })),
  ),
);
const loadStateLabel = computed(() => {
  switch (platformStore.loadState) {
    case 'loading':
      return '加载中';
    case 'success':
      return '正常';
    case 'error':
      return '异常';
    default:
      return '待检测';
  }
});

function formatDependencyStatus(status: ServiceDependency['status']) {
  if (status === 'up') {
    return '正常';
  }
  if (status === 'down') {
    return '异常';
  }
  return '未知';
}

function formatDependencyName(name: string) {
  return dependencyNameMap[name] ?? name;
}

function formatSourceType(sourceType: EventSourceType) {
  if (sourceType === 'video') {
    return '视频文件';
  }
  if (sourceType === 'image') {
    return '图片文件';
  }
  if (sourceType === 'stream') {
    return '视频流';
  }
  return '边缘上报';
}

function formatConfidence(confidence: number) {
  return `${Math.round(confidence * 100)}%`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

async function refreshAll() {
  await Promise.all([
    platformStore.loadHealth(),
    (async () => {
      const [deviceList, zones, eventSummary] = await Promise.all([
        listDevices(),
        listZones(),
        fetchBehaviorEventSummary(),
      ]);
      devices.value = deviceList;
      deviceCount.value = deviceList.length;
      onlineDeviceCount.value = deviceList.filter((item) => item.status === 'online' && item.is_enabled).length;
      zoneCount.value = zones.length;
      todayEventCount.value = eventSummary.today_count;
      recentEvents.value = eventSummary.recent_events;
    })(),
  ]);
}

onMounted(async () => {
  await refreshAll();
});
</script>
