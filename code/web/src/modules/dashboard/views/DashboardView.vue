<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">运营总览</p>
        <h2>系统概览</h2>
        <p class="page-header__text">
          {{ APP_NAME }}用于集中查看设备接入、区域配置、行为事件、告警状态与平台服务状态。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>在线设备数</span>
        <strong>{{ onlineDeviceCount }}</strong>
        <p>当前处于在线状态且已启用的设备数量。</p>
      </article>
      <article class="metric-card">
        <span>离线设备数</span>
        <strong>{{ offlineDeviceCount }}</strong>
        <p>当前处于离线或停用状态的设备数量。</p>
      </article>
      <article class="metric-card">
        <span>当日行为事件数</span>
        <strong>{{ todayEventCount }}</strong>
        <p>按当前农场时间口径汇总的今日行为事件数量。</p>
      </article>
      <article class="metric-card">
        <span>当前未处理告警数</span>
        <strong>{{ openAlertCount }}</strong>
        <p>尚未确认的告警记录数量。</p>
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
          <RouterLink class="action-card" to="/alerts">
            <strong>进入告警中心</strong>
            <span>查看最近异常告警并更新处理状态。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/rules">
            <strong>进入规则配置</strong>
            <span>启用预设规则或新增自定义规则。</span>
          </RouterLink>
          <RouterLink class="action-card" to="/history">
            <strong>进入历史分析</strong>
            <span>查看行为趋势图、告警趋势图和占比统计。</span>
          </RouterLink>
          <a class="action-card" :href="docsUrl" target="_blank" rel="noreferrer">
            <strong>查看 API 文档</strong>
            <span>检查接口契约并辅助联调演示。</span>
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
        <RouterLink
          v-for="device in previewDevices"
          :key="device.id"
          class="monitor-dashboard-link"
          :to="`/monitor/${device.id}`"
        >
          <DeviceLivePlayer :device="device" compact />
          <div class="monitor-dashboard-link__meta">
            <strong>{{ device.name }}</strong>
            <span>{{ device.code }} / {{ device.install_location || '未设置安装位置' }}</span>
          </div>
        </RouterLink>
      </div>
      <p v-else class="entity-note">
        当前没有可预览的已启用设备，请先在“设备管理”中配置视频流地址。
      </p>
    </article>

    <div class="content-grid">
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

            <div class="entity-actions">
              <RouterLink
                v-if="event.device_id"
                class="ghost-button"
                :to="`/monitor/${event.device_id}`"
              >
                打开设备详情
              </RouterLink>
            </div>
          </article>
          <p v-if="recentEvents.length === 0" class="entity-note">
            还没有行为事件记录，可以前往“事件中心”导入一条推理结果。
          </p>
        </div>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>最近告警</h3>
          <RouterLink class="ghost-button" to="/alerts">打开告警中心</RouterLink>
        </header>
        <div class="stack-list">
          <article v-for="alert in recentAlerts" :key="alert.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ alert.title }}</strong>
                <p>{{ alert.device_name || alert.device_code }} / {{ alert.rule_name || '未关联规则' }}</p>
              </div>
              <span :class="['dashboard-alert-pill', `dashboard-alert-pill--${alert.severity}`]">
                {{ formatAlertSeverity(alert.severity) }}
              </span>
            </div>

            <dl class="entity-grid">
              <div>
                <dt>触发时间</dt>
                <dd>{{ formatDate(alert.triggered_at) }}</dd>
              </div>
              <div>
                <dt>处理状态</dt>
                <dd>{{ formatAlertStatus(alert.status) }}</dd>
              </div>
              <div>
                <dt>规则来源</dt>
                <dd>{{ alert.rule_source === 'preset' ? '预设规则' : '自定义规则' }}</dd>
              </div>
              <div>
                <dt>处理备注</dt>
                <dd>{{ alert.handling_note || '暂无' }}</dd>
              </div>
            </dl>

            <div class="entity-actions">
              <RouterLink class="ghost-button" :to="`/alerts/${alert.id}`">打开告警详情</RouterLink>
              <RouterLink
                v-if="alert.device_id"
                class="ghost-button"
                :to="`/monitor/${alert.device_id}`"
              >
                打开设备详情
              </RouterLink>
            </div>
          </article>
          <p v-if="recentAlerts.length === 0" class="entity-note">
            还没有告警记录，可以在监控页或事件中心触发一条规则命中结果。
          </p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';

import { fetchAlertSummary } from '@/api/alerts';
import { listDevices } from '@/api/devices';
import { fetchBehaviorEventSummary } from '@/api/events';
import DeviceLivePlayer from '@/components/monitor/DeviceLivePlayer.vue';
import { APP_NAME } from '@/config/branding';
import { useAuthStore } from '@/stores/auth';
import { usePlatformStore } from '@/stores/platform';
import type { AlertSummary } from '@/types/alert';
import type { DeviceSummary } from '@/types/device';
import type { BehaviorEventSummary, EventSourceType } from '@/types/event';
import type { ServiceDependency } from '@/types/health';
import { summarizeDependencies } from '@/utils/health';

const authStore = useAuthStore();
const platformStore = usePlatformStore();

const onlineDeviceCount = ref(0);
const offlineDeviceCount = ref(0);
const todayEventCount = ref(0);
const openAlertCount = ref(0);
const recentEvents = ref<BehaviorEventSummary[]>([]);
const recentAlerts = ref<AlertSummary[]>([]);
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

function formatAlertSeverity(value: string) {
  if (value === 'high') {
    return '高等级';
  }
  if (value === 'medium') {
    return '中等级';
  }
  if (value === 'low') {
    return '低等级';
  }
  return value;
}

function formatAlertStatus(value: string) {
  if (value === 'open') {
    return '待处理';
  }
  if (value === 'acknowledged') {
    return '处理中';
  }
  if (value === 'resolved') {
    return '已解决';
  }
  return value;
}

async function refreshAll() {
  await Promise.all([
    platformStore.loadHealth(),
    (async () => {
      const [deviceList, eventSummary, alertSummary] = await Promise.all([
        listDevices(),
        fetchBehaviorEventSummary(),
        fetchAlertSummary(),
      ]);
      devices.value = deviceList;
      onlineDeviceCount.value = deviceList.filter((item) => item.status === 'online' && item.is_enabled).length;
      offlineDeviceCount.value = deviceList.filter((item) => item.status !== 'online' || !item.is_enabled).length;
      todayEventCount.value = eventSummary.today_count;
      openAlertCount.value = alertSummary.open_count;
      recentEvents.value = eventSummary.recent_events;
      recentAlerts.value = alertSummary.recent_alerts;
    })(),
  ]);
}

onMounted(async () => {
  await refreshAll();
});
</script>

<style scoped>
.monitor-dashboard-link {
  display: grid;
  gap: 12px;
  color: inherit;
  text-decoration: none;
}

.monitor-dashboard-link__meta {
  display: grid;
  gap: 4px;
}

.monitor-dashboard-link__meta span {
  color: #61707b;
  font-size: 13px;
}

.dashboard-alert-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.dashboard-alert-pill--high {
  background: rgba(190, 48, 48, 0.12);
  color: #a42323;
}

.dashboard-alert-pill--medium {
  background: rgba(238, 152, 54, 0.14);
  color: #9c5713;
}

.dashboard-alert-pill--low {
  background: rgba(40, 117, 179, 0.12);
  color: #1f5f94;
}
</style>
