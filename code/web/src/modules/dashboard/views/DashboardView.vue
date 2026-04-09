<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">运营总览</p>
        <h2>系统概览</h2>
        <p class="page-header__text">
          {{ APP_NAME }}用于集中查看设备接入、区域配置、行为事件与平台服务状态。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>设备总数</span>
        <strong>{{ deviceCount }}</strong>
        <p>{{ authStore.isAdmin ? '系统管理员可维护设备全生命周期。' : '观察账号在设备页为只读模式。' }}</p>
      </article>
      <article class="metric-card">
        <span>在线设备</span>
        <strong>{{ onlineDeviceCount }}</strong>
        <p>根据当前设备运行状态自动汇总。</p>
      </article>
      <article class="metric-card">
        <span>区域总数</span>
        <strong>{{ zoneCount }}</strong>
        <p>按当前农场范围隔离展示与维护。</p>
      </article>
      <article class="metric-card">
        <span>今日事件</span>
        <strong>{{ todayEventCount }}</strong>
        <p>统计当日已入库的行为事件记录。</p>
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
          <h3>业务入口</h3>
        </header>
        <div class="action-list">
          <RouterLink class="action-card" to="/monitor">
            <strong>进入监控中心</strong>
            <span>查看在线设备画面预览，并切换主监控画面。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/devices">
            <strong>进入设备资产</strong>
            <span>维护设备档案、视频流地址与运行状态。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/zones">
            <strong>进入区域配置</strong>
            <span>通过可视化画布绘制区域，并为设备绑定业务语义。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/events">
            <strong>进入事件中心</strong>
            <span>调用推理服务、导入结果并查看最新行为事件。</span>
          </RouterLink>
          <a class="action-card" :href="docsUrl" target="_blank" rel="noreferrer">
            <strong>查看 API 文档</strong>
            <span>检查 `/auth`、`/devices` 与 `/zones` 的接口契约。</span>
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
        <DeviceLivePlayer
          v-for="device in previewDevices"
          :key="device.id"
          :device="device"
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
        <RouterLink class="ghost-button" to="/events">打开事件中心</RouterLink>
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
          还没有行为事件记录，可以前往“事件中心”导入一条推理结果。
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
import DeviceLivePlayer from '@/components/monitor/DeviceLivePlayer.vue';
import { APP_NAME } from '@/config/branding';
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
