<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">告警详情</p>
        <h2>{{ alert?.title || '告警详情' }}</h2>
        <p class="page-header__text">
          查看告警触发上下文、规则快照和处理进度。
        </p>
      </div>
      <RouterLink class="ghost-button" to="/alerts">返回告警中心</RouterLink>
    </header>

    <div v-if="alert" class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>告警信息</h3>
          <span :class="['alert-pill', `alert-pill--${alert.severity}`]">{{ formatSeverity(alert.severity) }}</span>
        </header>

        <dl class="entity-grid">
          <div>
            <dt>设备</dt>
            <dd>{{ alert.device_name || alert.device_code }}</dd>
          </div>
          <div>
            <dt>状态</dt>
            <dd>{{ formatStatus(alert.status) }}</dd>
          </div>
          <div>
            <dt>规则</dt>
            <dd>{{ alert.rule_name || '未关联规则' }}</dd>
          </div>
          <div>
            <dt>规则来源</dt>
            <dd>{{ alert.rule_source === 'preset' ? '预设规则' : '自定义规则' }}</dd>
          </div>
          <div>
            <dt>触发时间</dt>
            <dd>{{ formatDate(alert.triggered_at) }}</dd>
          </div>
          <div>
            <dt>最近处理人</dt>
            <dd>{{ alert.handled_by_user_name || '暂无' }}</dd>
          </div>
        </dl>

        <p class="detail-copy">{{ alert.description }}</p>
        <p class="detail-copy">
          处理备注：{{ alert.handling_note || '暂无处理备注' }}
        </p>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>处理状态更新</h3>
        </header>

        <form class="form-grid" @submit.prevent="submitStatusUpdate">
          <label class="field">
            <span>处理状态</span>
            <select v-model="form.status">
              <option value="open">待处理</option>
              <option value="acknowledged">处理中</option>
              <option value="resolved">已解决</option>
            </select>
          </label>

          <label class="field field--full">
            <span>处理备注</span>
            <textarea
              v-model.trim="form.handlingNote"
              rows="6"
              placeholder="例如：已查看现场，准备安排人工复检"
            />
          </label>

          <button class="primary-button" type="submit" :disabled="submitting">
            {{ submitting ? '提交中...' : '更新告警状态' }}
          </button>
        </form>

        <p v-if="submitMessage" class="success-text">{{ submitMessage }}</p>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
      </article>
    </div>

    <article v-if="alert" class="panel">
      <header class="panel__header">
        <h3>触发快照</h3>
      </header>

      <div class="snapshot-grid">
        <article
          v-for="entry in snapshotEntries"
          :key="entry.label"
          class="snapshot-card"
        >
          <span>{{ entry.label }}</span>
          <strong>{{ entry.value }}</strong>
        </article>
      </div>
    </article>

    <p v-if="loadError" class="error-text">{{ loadError }}</p>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';
import { useRoute } from 'vue-router';

import { getAlert, updateAlertStatus } from '@/api/alerts';
import type { AlertStatus, AlertSummary } from '@/types/alert';

const route = useRoute();

const alert = ref<AlertSummary | null>(null);
const loadError = ref('');
const submitError = ref('');
const submitMessage = ref('');
const submitting = ref(false);
const form = reactive({
  status: 'open' as AlertStatus,
  handlingNote: '',
});

const snapshotEntries = computed(() => {
  if (!alert.value) {
    return [];
  }

  return Object.entries(alert.value.snapshot).map(([label, value]) => ({
    label,
    value: typeof value === 'string' || typeof value === 'number' ? String(value) : JSON.stringify(value),
  }));
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

async function loadAlert() {
  loadError.value = '';

  try {
    const alertId = Number(route.params.alertId);
    alert.value = await getAlert(alertId);
    form.status = alert.value.status;
    form.handlingNote = alert.value.handling_note || '';
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载告警详情。';
  }
}

async function submitStatusUpdate() {
  if (!alert.value) {
    return;
  }

  submitting.value = true;
  submitError.value = '';
  submitMessage.value = '';

  try {
    alert.value = await updateAlertStatus(alert.value.id, {
      status: form.status,
      handling_note: form.handlingNote || null,
    });
    submitMessage.value = '告警状态已更新。';
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法更新告警状态。';
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  await loadAlert();
});
</script>

<style scoped>
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

.detail-copy {
  margin: 16px 0 0;
  color: #55646f;
  line-height: 1.7;
}

.snapshot-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 14px;
}

.snapshot-card {
  display: grid;
  gap: 8px;
  padding: 18px;
  border-radius: 18px;
  background: rgba(244, 248, 250, 0.92);
}

.snapshot-card span {
  color: #64737d;
  font-size: 13px;
}

.snapshot-card strong {
  word-break: break-word;
}
</style>
