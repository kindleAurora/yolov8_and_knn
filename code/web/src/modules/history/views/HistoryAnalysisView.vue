<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">历史分析</p>
        <h2>历史分析</h2>
        <p class="page-header__text">
          按时间范围回看行为事件与告警记录，并通过趋势图和占比图快速判断状态变化。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <article class="panel">
      <header class="panel__header">
        <h3>筛选条件</h3>
      </header>

      <form class="form-grid" @submit.prevent="refreshAll">
        <label class="field">
          <span>开始时间</span>
          <input v-model="filters.startAtLocal" type="datetime-local" />
        </label>

        <label class="field">
          <span>结束时间</span>
          <input v-model="filters.endAtLocal" type="datetime-local" />
        </label>

        <label class="field">
          <span>设备</span>
          <select v-model="filters.deviceId">
            <option value="">全部设备</option>
            <option v-for="device in devices" :key="device.id" :value="String(device.id)">
              {{ device.name }}
            </option>
          </select>
        </label>

        <button class="primary-button" type="submit">应用筛选</button>
      </form>

      <p v-if="loadError" class="error-text">{{ loadError }}</p>
    </article>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>行为事件数</span>
        <strong>{{ analysis.total_behavior_events }}</strong>
        <p>当前时间范围内的行为事件总量。</p>
      </article>
      <article class="metric-card">
        <span>告警数量</span>
        <strong>{{ analysis.total_alerts }}</strong>
        <p>当前时间范围内触发的告警总数。</p>
      </article>
      <article class="metric-card">
        <span>主导行为</span>
        <strong>{{ dominantBehavior }}</strong>
        <p>占比最高的行为类型。</p>
      </article>
      <article class="metric-card">
        <span>主要告警等级</span>
        <strong>{{ dominantSeverity }}</strong>
        <p>当前时间范围内出现最多的告警等级。</p>
      </article>
    </section>

    <div class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>行为趋势柱状图</h3>
          <span class="panel__badge">{{ analysis.behavior_trend.length }} 个时间点</span>
        </header>

        <div v-if="analysis.behavior_trend.length > 0" class="bar-chart">
          <div
            v-for="point in analysis.behavior_trend"
            :key="`behavior-${point.label}`"
            class="bar-chart__item"
          >
            <span class="bar-chart__value">{{ point.value }}</span>
            <div class="bar-chart__track">
              <div class="bar-chart__fill" :style="{ height: `${getBarHeight(point.value, behaviorTrendMax)}%` }" />
            </div>
            <span class="bar-chart__label">{{ point.label }}</span>
          </div>
        </div>
        <p v-else class="entity-note">当前时间范围内没有行为趋势数据。</p>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>告警趋势折线图</h3>
          <span class="panel__badge">{{ analysis.alert_trend.length }} 个时间点</span>
        </header>

        <div v-if="analysis.alert_trend.length > 0" class="line-chart">
          <svg viewBox="0 0 100 40" preserveAspectRatio="none" class="line-chart__svg">
            <polyline class="line-chart__line" :points="alertTrendPoints" />
            <circle
              v-for="point in alertTrendDots"
              :key="`${point.label}-${point.x}`"
              class="line-chart__dot"
              :cx="point.x"
              :cy="point.y"
              r="1.8"
            />
          </svg>

          <div class="line-chart__labels">
            <span v-for="point in analysis.alert_trend" :key="`alert-${point.label}`">{{ point.label }}</span>
          </div>
        </div>
        <p v-else class="entity-note">当前时间范围内没有告警趋势数据。</p>
      </article>
    </div>

    <div class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>行为占比</h3>
          <span class="panel__badge">{{ analysis.behavior_share.length }} 类</span>
        </header>

        <div v-if="analysis.behavior_share.length > 0" class="share-list">
          <article v-for="item in analysis.behavior_share" :key="item.label" class="share-item">
            <div class="share-item__top">
              <strong>{{ item.label }}</strong>
              <span>{{ formatPercent(item.share) }}</span>
            </div>
            <div class="share-item__track">
              <div class="share-item__fill" :style="{ width: `${Math.max(item.share * 100, 6)}%` }" />
            </div>
            <p>{{ item.value }} 条事件</p>
          </article>
        </div>
        <p v-else class="entity-note">当前时间范围内没有行为占比数据。</p>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>告警等级占比</h3>
          <span class="panel__badge">{{ analysis.alert_severity_distribution.length }} 类</span>
        </header>

        <div v-if="analysis.alert_severity_distribution.length > 0" class="share-list">
          <article v-for="item in analysis.alert_severity_distribution" :key="item.label" class="share-item">
            <div class="share-item__top">
              <strong>{{ formatSeverity(item.label) }}</strong>
              <span>{{ formatPercent(item.share) }}</span>
            </div>
            <div class="share-item__track">
              <div class="share-item__fill share-item__fill--alert" :style="{ width: `${Math.max(item.share * 100, 6)}%` }" />
            </div>
            <p>{{ item.value }} 条告警</p>
          </article>
        </div>
        <p v-else class="entity-note">当前时间范围内没有告警等级占比数据。</p>
      </article>
    </div>

    <div class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>历史行为记录</h3>
          <span class="panel__badge">{{ behaviorRecords.total }} 条</span>
        </header>

        <div class="stack-list">
          <article v-for="item in behaviorRecords.items" :key="item.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ item.behavior_type }}</strong>
                <p>{{ item.device_name || item.device_code }} / {{ item.zone_name || '未命中区域' }}</p>
              </div>
              <span class="service-badge service-badge--up">{{ Math.round(item.confidence * 100) }}%</span>
            </div>

            <dl class="entity-grid">
              <div>
                <dt>事件时间</dt>
                <dd>{{ formatDate(item.occurred_at) }}</dd>
              </div>
              <div>
                <dt>牛只数量</dt>
                <dd>{{ item.cow_count }}</dd>
              </div>
              <div>
                <dt>来源类型</dt>
                <dd>{{ item.source_type }}</dd>
              </div>
              <div>
                <dt>模型</dt>
                <dd>{{ item.model_name }}</dd>
              </div>
            </dl>
          </article>
          <p v-if="behaviorRecords.items.length === 0" class="entity-note">暂无历史行为记录。</p>
        </div>

        <div class="pagination-row">
          <button class="ghost-button" type="button" :disabled="behaviorPage <= 1" @click="changeBehaviorPage(behaviorPage - 1)">
            上一页
          </button>
          <span>第 {{ behaviorPage }} 页</span>
          <button
            class="ghost-button"
            type="button"
            :disabled="behaviorPage * pageSize >= behaviorRecords.total"
            @click="changeBehaviorPage(behaviorPage + 1)"
          >
            下一页
          </button>
        </div>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>历史告警记录</h3>
          <span class="panel__badge">{{ alertRecords.total }} 条</span>
        </header>

        <div class="stack-list">
          <article v-for="item in alertRecords.items" :key="item.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ item.title }}</strong>
                <p>{{ item.device_name || item.device_code }} / {{ item.rule_name || '未关联规则' }}</p>
              </div>
              <span class="history-alert-badge">{{ formatSeverity(item.severity) }}</span>
            </div>

            <dl class="entity-grid">
              <div>
                <dt>触发时间</dt>
                <dd>{{ formatDate(item.triggered_at) }}</dd>
              </div>
              <div>
                <dt>处理状态</dt>
                <dd>{{ formatStatus(item.status) }}</dd>
              </div>
              <div>
                <dt>规则来源</dt>
                <dd>{{ item.rule_source === 'preset' ? '预设规则' : '自定义规则' }}</dd>
              </div>
              <div>
                <dt>处理备注</dt>
                <dd>{{ item.handling_note || '暂无' }}</dd>
              </div>
            </dl>
          </article>
          <p v-if="alertRecords.items.length === 0" class="entity-note">暂无历史告警记录。</p>
        </div>

        <div class="pagination-row">
          <button class="ghost-button" type="button" :disabled="alertPage <= 1" @click="changeAlertPage(alertPage - 1)">
            上一页
          </button>
          <span>第 {{ alertPage }} 页</span>
          <button
            class="ghost-button"
            type="button"
            :disabled="alertPage * pageSize >= alertRecords.total"
            @click="changeAlertPage(alertPage + 1)"
          >
            下一页
          </button>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { listDevices } from '@/api/devices';
import { fetchHistoryAnalysis, listHistoryAlerts, listHistoryBehaviorEvents } from '@/api/history';
import type { DeviceSummary } from '@/types/device';
import type { HistoryAnalysisSummary, PagedHistoryAlertResult, PagedHistoryBehaviorEventResult } from '@/types/history';

const pageSize = 8;
const devices = ref<DeviceSummary[]>([]);
const loadError = ref('');
const behaviorPage = ref(1);
const alertPage = ref(1);

const analysis = ref<HistoryAnalysisSummary>({
  window_start: new Date().toISOString(),
  window_end: new Date().toISOString(),
  total_behavior_events: 0,
  total_alerts: 0,
  behavior_trend: [],
  alert_trend: [],
  behavior_share: [],
  alert_severity_distribution: [],
});
const behaviorRecords = ref<PagedHistoryBehaviorEventResult>({
  total: 0,
  page: 1,
  page_size: pageSize,
  items: [],
});
const alertRecords = ref<PagedHistoryAlertResult>({
  total: 0,
  page: 1,
  page_size: pageSize,
  items: [],
});

const filters = reactive({
  startAtLocal: createDefaultLocalDateTime(-6),
  endAtLocal: createDefaultLocalDateTime(0),
  deviceId: '',
});

const behaviorTrendMax = computed(() =>
  Math.max(...analysis.value.behavior_trend.map((item) => item.value), 1),
);
const alertTrendMax = computed(() =>
  Math.max(...analysis.value.alert_trend.map((item) => item.value), 1),
);
const dominantBehavior = computed(() => analysis.value.behavior_share[0]?.label ?? '暂无数据');
const dominantSeverity = computed(() => formatSeverity(analysis.value.alert_severity_distribution[0]?.label ?? '暂无数据'));
const alertTrendDots = computed(() => {
  if (analysis.value.alert_trend.length === 0) {
    return [];
  }

  return analysis.value.alert_trend.map((point, index, list) => {
    const x = list.length === 1 ? 50 : (index / (list.length - 1)) * 96 + 2;
    const y = 36 - (point.value / alertTrendMax.value) * 32;
    return {
      label: point.label,
      x,
      y,
    };
  });
});
const alertTrendPoints = computed(() => alertTrendDots.value.map((point) => `${point.x},${point.y}`).join(' '));

function createDefaultLocalDateTime(dayOffset: number) {
  const date = new Date();
  date.setDate(date.getDate() + dayOffset);
  date.setSeconds(0, 0);
  const timezoneOffset = date.getTimezoneOffset();
  const localDate = new Date(date.getTime() - timezoneOffset * 60 * 1000);
  return localDate.toISOString().slice(0, 16);
}

function toIsoString(value: string) {
  return value ? new Date(value).toISOString() : undefined;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
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

function formatStatus(value: string) {
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

function getBarHeight(value: number, maxValue: number) {
  return maxValue > 0 ? (value / maxValue) * 100 : 0;
}

async function loadAnalysis() {
  analysis.value = await fetchHistoryAnalysis({
    startAt: toIsoString(filters.startAtLocal),
    endAt: toIsoString(filters.endAtLocal),
    deviceId: filters.deviceId ? Number(filters.deviceId) : undefined,
  });
}

async function loadBehaviorRecords() {
  behaviorRecords.value = await listHistoryBehaviorEvents({
    startAt: toIsoString(filters.startAtLocal),
    endAt: toIsoString(filters.endAtLocal),
    deviceId: filters.deviceId ? Number(filters.deviceId) : undefined,
    page: behaviorPage.value,
    pageSize,
  });
}

async function loadAlertRecords() {
  alertRecords.value = await listHistoryAlerts({
    startAt: toIsoString(filters.startAtLocal),
    endAt: toIsoString(filters.endAtLocal),
    deviceId: filters.deviceId ? Number(filters.deviceId) : undefined,
    page: alertPage.value,
    pageSize,
  });
}

async function changeBehaviorPage(nextPage: number) {
  behaviorPage.value = nextPage;
  await loadBehaviorRecords();
}

async function changeAlertPage(nextPage: number) {
  alertPage.value = nextPage;
  await loadAlertRecords();
}

async function refreshAll() {
  loadError.value = '';
  behaviorPage.value = 1;
  alertPage.value = 1;

  try {
    const deviceList = await listDevices();
    devices.value = deviceList;
    await Promise.all([loadAnalysis(), loadBehaviorRecords(), loadAlertRecords()]);
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载历史分析数据。';
  }
}

onMounted(async () => {
  await refreshAll();
});
</script>

<style scoped>
.bar-chart {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(56px, 1fr));
  gap: 14px;
  min-height: 240px;
  align-items: end;
}

.bar-chart__item {
  display: grid;
  gap: 10px;
  justify-items: center;
}

.bar-chart__track {
  position: relative;
  width: 100%;
  height: 160px;
  display: flex;
  align-items: end;
  border-radius: 18px;
  padding: 8px;
  background: linear-gradient(180deg, rgba(233, 239, 243, 0.86), rgba(245, 248, 250, 0.96));
}

.bar-chart__fill {
  width: 100%;
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(49, 116, 201, 0.92), rgba(103, 157, 225, 0.92));
}

.bar-chart__value,
.bar-chart__label {
  font-size: 13px;
  color: #5a6974;
}

.line-chart {
  display: grid;
  gap: 12px;
}

.line-chart__svg {
  width: 100%;
  height: 220px;
  padding: 14px;
  border-radius: 20px;
  background:
    linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(243, 247, 250, 0.98)),
    linear-gradient(90deg, rgba(221, 229, 236, 0.6) 1px, transparent 1px);
}

.line-chart__line {
  fill: none;
  stroke: #cf6d1e;
  stroke-width: 2;
  stroke-linejoin: round;
  stroke-linecap: round;
}

.line-chart__dot {
  fill: #cf6d1e;
}

.line-chart__labels {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 12px;
  color: #657580;
}

.share-list {
  display: grid;
  gap: 14px;
}

.share-item {
  display: grid;
  gap: 10px;
}

.share-item__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.share-item__track {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(223, 231, 236, 0.92);
}

.share-item__fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, rgba(48, 132, 97, 0.96), rgba(103, 198, 161, 0.86));
}

.share-item__fill--alert {
  background: linear-gradient(90deg, rgba(201, 108, 43, 0.96), rgba(239, 165, 88, 0.86));
}

.share-item p {
  margin: 0;
  color: #65747e;
  font-size: 13px;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
}

.history-alert-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: rgba(198, 118, 44, 0.14);
  color: #985717;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 760px) {
  .line-chart__labels,
  .pagination-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
