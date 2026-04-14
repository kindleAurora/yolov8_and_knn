<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">监控详情</p>
        <h2>{{ device?.name || '设备监控详情' }}</h2>
        <p class="page-header__text">
          汇总单设备实时画面、区域配置、最新行为和最近告警，方便直接讲解完整业务链路。
        </p>
      </div>
      <div class="detail-header-actions">
        <RouterLink class="ghost-button" to="/monitor">返回监控中心</RouterLink>
        <RouterLink class="ghost-button" to="/zones">打开区域配置</RouterLink>
      </div>
    </header>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>

    <template v-if="device">
      <section class="metrics-grid">
        <article class="metric-card">
          <span>设备编号</span>
          <strong>{{ device.code }}</strong>
          <p>当前详情页对应的监控设备唯一编号。</p>
        </article>
        <article class="metric-card">
          <span>运行状态</span>
          <strong>{{ formatDeviceStatus(device.status) }}</strong>
          <p>{{ device.is_enabled ? '设备当前已启用。' : '设备当前处于停用状态。' }}</p>
        </article>
        <article class="metric-card">
          <span>区域数量</span>
          <strong>{{ zones.length }}</strong>
          <p>当前设备已关联的区域配置总数。</p>
        </article>
        <article class="metric-card">
          <span>最近告警</span>
          <strong>{{ alerts.length }}</strong>
          <p>当前设备最近触发的告警条数。</p>
        </article>
      </section>

      <div class="content-grid">
        <article class="panel">
          <header class="panel__header">
            <h3>实时画面</h3>
            <span class="panel__badge">{{ device.install_location || '未设置安装位置' }}</span>
          </header>
          <DeviceLivePlayer :device="device" show-controls />
        </article>

        <article class="panel">
          <header class="panel__header">
            <h3>设备信息</h3>
            <RouterLink class="ghost-button" :to="`/devices`">打开设备资产</RouterLink>
          </header>

          <dl class="entity-grid">
            <div>
              <dt>设备类型</dt>
              <dd>{{ device.device_type }}</dd>
            </div>
            <div>
              <dt>安装位置</dt>
              <dd>{{ device.install_location || '未设置' }}</dd>
            </div>
            <div>
              <dt>最近在线时间</dt>
              <dd>{{ device.last_seen_at ? formatDate(device.last_seen_at) : '暂无' }}</dd>
            </div>
            <div>
              <dt>视频流地址</dt>
              <dd>{{ device.stream_url }}</dd>
            </div>
          </dl>

          <p class="entity-note">
            区域配置入口已和当前设备详情联动。需要重新划区时，可直接点上方“打开区域配置”，再按当前设备继续编辑。
          </p>
        </article>
      </div>

      <div class="content-grid">
        <article class="panel">
          <header class="panel__header">
            <h3>区域信息</h3>
            <span class="panel__badge">{{ zones.length }} 个区域</span>
          </header>

          <div class="stack-list">
            <article v-for="zone in zones" :key="zone.id" class="entity-card">
              <div class="entity-card__header">
                <div>
                  <strong>{{ zone.name }}</strong>
                  <p>{{ zone.zone_type }} / {{ zone.shape_type }}</p>
                </div>
                <span class="service-badge" :class="zone.is_enabled ? 'service-badge--up' : 'service-badge--unknown'">
                  {{ zone.is_enabled ? '启用中' : '已停用' }}
                </span>
              </div>
              <p class="entity-note">当前区域共有 {{ zone.points.length }} 个坐标点。</p>
            </article>
            <p v-if="zones.length === 0" class="entity-note">当前设备还没有配置区域。</p>
          </div>
        </article>

        <article class="panel">
          <header class="panel__header">
            <h3>最新行为识别结果</h3>
            <RouterLink class="ghost-button" :to="`/events`">打开事件中心</RouterLink>
          </header>

          <div class="stack-list">
            <article v-for="event in events" :key="event.id" class="entity-card">
              <div class="entity-card__header">
                <div>
                  <strong>{{ event.behavior_type }}</strong>
                  <p>{{ formatDate(event.occurred_at) }} / {{ event.zone_name || '未命中区域' }}</p>
                </div>
                <span class="service-badge service-badge--up">{{ formatConfidence(event.confidence) }}</span>
              </div>

              <dl class="entity-grid">
                <div>
                  <dt>牛只数量</dt>
                  <dd>{{ event.cow_count }}</dd>
                </div>
                <div>
                  <dt>模型</dt>
                  <dd>{{ event.model_name }} / {{ event.model_version }}</dd>
                </div>
                <div>
                  <dt>来源</dt>
                  <dd>{{ event.inference_source }}</dd>
                </div>
                <div>
                  <dt>请求编号</dt>
                  <dd>{{ event.request_id }}</dd>
                </div>
              </dl>
            </article>
            <p v-if="events.length === 0" class="entity-note">当前设备还没有最近行为记录。</p>
          </div>
        </article>
      </div>

      <article class="panel">
        <header class="panel__header">
          <h3>最近告警</h3>
          <RouterLink class="ghost-button" to="/alerts">打开告警中心</RouterLink>
        </header>

        <div class="stack-list">
          <article v-for="alert in alerts" :key="alert.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ alert.title }}</strong>
                <p>{{ formatDate(alert.triggered_at) }} / {{ alert.rule_name || '未关联规则' }}</p>
              </div>
              <div class="detail-alert-pills">
                <span :class="['detail-alert-pill', `detail-alert-pill--${alert.severity}`]">{{ formatSeverity(alert.severity) }}</span>
                <span :class="['detail-alert-pill', `detail-alert-pill--status-${alert.status}`]">{{ formatAlertStatus(alert.status) }}</span>
              </div>
            </div>

            <p class="entity-note">{{ alert.description }}</p>

            <div class="entity-actions">
              <RouterLink class="ghost-button" :to="`/alerts/${alert.id}`">查看告警详情</RouterLink>
            </div>
          </article>
          <p v-if="alerts.length === 0" class="entity-note">当前设备还没有最近告警。</p>
        </div>
      </article>
    </template>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRoute } from 'vue-router';

import { listAlerts } from '@/api/alerts';
import { getDevice } from '@/api/devices';
import { listBehaviorEvents } from '@/api/events';
import { listZones } from '@/api/zones';
import DeviceLivePlayer from '@/components/monitor/DeviceLivePlayer.vue';
import type { AlertSummary } from '@/types/alert';
import type { DeviceSummary } from '@/types/device';
import type { BehaviorEventSummary } from '@/types/event';
import type { ZoneSummary } from '@/types/zone';

const route = useRoute();

const device = ref<DeviceSummary | null>(null);
const zones = ref<ZoneSummary[]>([]);
const events = ref<BehaviorEventSummary[]>([]);
const alerts = ref<AlertSummary[]>([]);
const loadError = ref('');

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function formatConfidence(confidence: number) {
  return `${Math.round(confidence * 100)}%`;
}

function formatDeviceStatus(status: string) {
  if (status === 'online') {
    return '在线';
  }
  if (status === 'offline') {
    return '离线';
  }
  if (status === 'disabled') {
    return '停用';
  }
  return status;
}

function formatSeverity(value: string) {
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

async function loadDetail() {
  loadError.value = '';

  try {
    const deviceId = Number(route.params.deviceId);
    const [deviceDetail, zoneList, eventList, alertList] = await Promise.all([
      getDevice(deviceId),
      listZones(deviceId),
      listBehaviorEvents({ deviceId, limit: 6 }),
      listAlerts({ deviceId, page: 1, pageSize: 6 }),
    ]);
    device.value = deviceDetail;
    zones.value = zoneList;
    events.value = eventList;
    alerts.value = alertList.items;
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载设备监控详情。';
  }
}

onMounted(async () => {
  await loadDetail();
});
</script>

<style scoped>
.detail-header-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.detail-alert-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: end;
}

.detail-alert-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.detail-alert-pill--high {
  background: rgba(190, 48, 48, 0.12);
  color: #a42323;
}

.detail-alert-pill--medium {
  background: rgba(238, 152, 54, 0.14);
  color: #9c5713;
}

.detail-alert-pill--low {
  background: rgba(40, 117, 179, 0.12);
  color: #1f5f94;
}

.detail-alert-pill--status-open {
  background: rgba(198, 43, 43, 0.1);
  color: #9f2020;
}

.detail-alert-pill--status-acknowledged {
  background: rgba(216, 144, 48, 0.14);
  color: #8d5516;
}

.detail-alert-pill--status-resolved {
  background: rgba(36, 141, 90, 0.12);
  color: #1f7e50;
}

@media (max-width: 760px) {
  .detail-header-actions,
  .detail-alert-pills {
    justify-content: start;
  }
}
</style>
