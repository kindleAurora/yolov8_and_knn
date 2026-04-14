<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">告警中心</p>
        <h2>告警中心</h2>
        <p class="page-header__text">
          集中查看规则触发后的异常告警，并支持按设备、状态、等级快速筛选和处理。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>告警总数</span>
        <strong>{{ summary.total_count }}</strong>
        <p>当前牧场已生成的告警记录总量。</p>
      </article>
      <article class="metric-card">
        <span>待处理</span>
        <strong>{{ summary.open_count }}</strong>
        <p>尚未确认的告警，建议优先排查。</p>
      </article>
      <article class="metric-card">
        <span>处理中</span>
        <strong>{{ summary.acknowledged_count }}</strong>
        <p>已确认但还未关闭的告警。</p>
      </article>
      <article class="metric-card">
        <span>高等级告警</span>
        <strong>{{ summary.high_severity_count }}</strong>
        <p>高优先级风险，适合优先跟进。</p>
      </article>
    </section>

    <div class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>筛选条件</h3>
          <span class="panel__badge">{{ alerts.total }} 条</span>
        </header>

        <div class="form-grid">
          <label class="field">
            <span>设备</span>
            <select v-model="filters.deviceId" @change="loadAlerts">
              <option value="">全部设备</option>
              <option v-for="device in devices" :key="device.id" :value="String(device.id)">
                {{ device.name }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>处理状态</span>
            <select v-model="filters.status" @change="loadAlerts">
              <option value="">全部状态</option>
              <option value="open">待处理</option>
              <option value="acknowledged">处理中</option>
              <option value="resolved">已解决</option>
            </select>
          </label>

          <label class="field">
            <span>告警等级</span>
            <select v-model="filters.severity" @change="loadAlerts">
              <option value="">全部等级</option>
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </label>

          <label class="field">
            <span>规则来源</span>
            <select v-model="filters.ruleSource" @change="loadAlerts">
              <option value="">全部来源</option>
              <option value="preset">预设规则</option>
              <option value="custom">自定义规则</option>
            </select>
          </label>
        </div>

        <p v-if="loadError" class="error-text">{{ loadError }}</p>

        <div class="stack-list">
          <article v-for="alert in alerts.items" :key="alert.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ alert.title }}</strong>
                <p>{{ alert.device_name || alert.device_code }} / {{ alert.rule_name || '未关联规则' }}</p>
              </div>
              <div class="alert-pill-group">
                <span :class="['alert-pill', `alert-pill--${alert.severity}`]">{{ formatSeverity(alert.severity) }}</span>
                <span :class="['alert-pill', `alert-pill--status-${alert.status}`]">{{ formatStatus(alert.status) }}</span>
              </div>
            </div>

            <p class="entity-note">{{ alert.description }}</p>

            <dl class="entity-grid">
              <div>
                <dt>触发时间</dt>
                <dd>{{ formatDate(alert.triggered_at) }}</dd>
              </div>
              <div>
                <dt>规则来源</dt>
                <dd>{{ formatRuleSource(alert.rule_source) }}</dd>
              </div>
              <div>
                <dt>处理人</dt>
                <dd>{{ alert.handled_by_user_name || '未处理' }}</dd>
              </div>
              <div>
                <dt>处理备注</dt>
                <dd>{{ alert.handling_note || '暂无' }}</dd>
              </div>
            </dl>

            <div class="entity-actions">
              <RouterLink class="ghost-button" :to="`/alerts/${alert.id}`">查看详情</RouterLink>
              <button
                v-if="alert.status === 'open'"
                class="ghost-button"
                type="button"
                @click="handleStatusUpdate(alert.id, 'acknowledged')"
              >
                标记处理中
              </button>
              <button
                v-if="alert.status !== 'resolved'"
                class="ghost-button"
                type="button"
                @click="handleStatusUpdate(alert.id, 'resolved')"
              >
                标记已解决
              </button>
            </div>
          </article>

          <p v-if="alerts.items.length === 0" class="entity-note">
            当前筛选条件下没有告警记录。
          </p>
        </div>

        <div class="pagination-row">
          <button class="ghost-button" type="button" :disabled="filters.page <= 1" @click="changePage(filters.page - 1)">
            上一页
          </button>
          <span>第 {{ filters.page }} 页</span>
          <button
            class="ghost-button"
            type="button"
            :disabled="filters.page * filters.pageSize >= alerts.total"
            @click="changePage(filters.page + 1)"
          >
            下一页
          </button>
        </div>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>最近告警速览</h3>
          <RouterLink class="ghost-button" to="/history">查看历史分析</RouterLink>
        </header>

        <div class="stack-list">
          <article v-for="alert in summary.recent_alerts" :key="`recent-${alert.id}`" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ alert.title }}</strong>
                <p>{{ formatDate(alert.triggered_at) }}</p>
              </div>
              <span :class="['alert-pill', `alert-pill--${alert.severity}`]">{{ formatSeverity(alert.severity) }}</span>
            </div>
            <p class="entity-note">{{ alert.description }}</p>
          </article>
          <p v-if="summary.recent_alerts.length === 0" class="entity-note">
            还没有最近告警记录。
          </p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue';

import { fetchAlertSummary, listAlerts, updateAlertStatus } from '@/api/alerts';
import { listDevices } from '@/api/devices';
import type { AlertListResult, AlertStatus, AlertSummaryStats } from '@/types/alert';
import type { DeviceSummary } from '@/types/device';

const devices = ref<DeviceSummary[]>([]);
const loadError = ref('');
const alerts = ref<AlertListResult>({
  total: 0,
  page: 1,
  page_size: 10,
  items: [],
});
const summary = ref<AlertSummaryStats>({
  total_count: 0,
  open_count: 0,
  acknowledged_count: 0,
  resolved_count: 0,
  high_severity_count: 0,
  recent_alerts: [],
});

const filters = reactive({
  deviceId: '',
  status: '',
  severity: '',
  ruleSource: '',
  page: 1,
  pageSize: 10,
});

function formatDate(value: string) {
  return new Date(value).toLocaleString();
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

function formatStatus(value: AlertStatus) {
  if (value === 'open') {
    return '待处理';
  }
  if (value === 'acknowledged') {
    return '处理中';
  }
  return '已解决';
}

function formatRuleSource(value: string) {
  return value === 'preset' ? '预设规则' : value === 'custom' ? '自定义规则' : value;
}

async function loadAlertSummary() {
  summary.value = await fetchAlertSummary();
}

async function loadAlerts() {
  loadError.value = '';

  try {
    alerts.value = await listAlerts({
      deviceId: filters.deviceId ? Number(filters.deviceId) : undefined,
      status: filters.status || undefined,
      severity: filters.severity || undefined,
      ruleSource: filters.ruleSource || undefined,
      page: filters.page,
      pageSize: filters.pageSize,
    });
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载告警列表。';
  }
}

async function changePage(nextPage: number) {
  filters.page = nextPage;
  await loadAlerts();
}

async function handleStatusUpdate(alertId: number, status: AlertStatus) {
  await updateAlertStatus(alertId, { status });
  await Promise.all([loadAlertSummary(), loadAlerts()]);
}

async function refreshAll() {
  loadError.value = '';

  try {
    const [deviceList, alertSummary] = await Promise.all([listDevices(), fetchAlertSummary()]);
    devices.value = deviceList;
    summary.value = alertSummary;
    await loadAlerts();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载告警中心数据。';
  }
}

onMounted(async () => {
  await refreshAll();
});
</script>

<style scoped>
.alert-pill-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: end;
}

.alert-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.alert-pill--high {
  background: rgba(190, 48, 48, 0.12);
  color: #a42323;
}

.alert-pill--medium {
  background: rgba(238, 152, 54, 0.14);
  color: #9c5713;
}

.alert-pill--low {
  background: rgba(40, 117, 179, 0.12);
  color: #1f5f94;
}

.alert-pill--status-open {
  background: rgba(198, 43, 43, 0.1);
  color: #9f2020;
}

.alert-pill--status-acknowledged {
  background: rgba(216, 144, 48, 0.14);
  color: #8d5516;
}

.alert-pill--status-resolved {
  background: rgba(36, 141, 90, 0.12);
  color: #1f7e50;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 760px) {
  .alert-pill-group,
  .pagination-row {
    justify-content: start;
  }

  .pagination-row {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
