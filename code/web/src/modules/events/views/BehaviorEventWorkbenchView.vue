<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">阶段 3</p>
        <h2>行为事件工作台</h2>
        <p class="page-header__text">
          将图片、视频流或边缘来源送入推理服务，并把结构化结果写入行为事件库。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>累计事件</span>
        <strong>{{ summary.total_count }}</strong>
        <p>当前农场内已写入的结构化行为事件总数。</p>
      </article>
      <article class="metric-card">
        <span>今日事件</span>
        <strong>{{ summary.today_count }}</strong>
        <p>按当前农场时区统计的当日行为事件数量。</p>
      </article>
      <article class="metric-card">
        <span>最近模型</span>
        <strong>{{ latestModel }}</strong>
        <p>最新一次导入结果对应的模型名称。</p>
      </article>
      <article class="metric-card">
        <span>推理来源</span>
        <strong>{{ latestSource }}</strong>
        <p>用于生成最新事件的推理来源标识。</p>
      </article>
    </section>

    <div class="content-grid event-content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>导入推理结果</h3>
          <button class="ghost-button" type="button" @click="resetForm">重置表单</button>
        </header>

        <form class="form-grid" @submit.prevent="submitImport">
          <label class="field">
            <span>选择设备</span>
            <select v-model="form.deviceCode">
              <option value="" disabled>请选择设备</option>
              <option v-for="device in devices" :key="device.id" :value="device.code">
                {{ device.name }}（{{ device.code }}）
              </option>
            </select>
          </label>

          <label class="field">
            <span>推理模式</span>
            <select v-model="form.inferenceMode">
              <option value="yolo-knn">YOLO + KNN 行为分类</option>
              <option value="yolo-only">仅 YOLO 检测</option>
            </select>
          </label>

          <label class="field">
            <span>YOLO 模型</span>
            <select v-model="form.yoloModelKey">
              <option value="">使用默认模型</option>
              <option v-for="option in yoloModelOptions" :key="option.key" :value="option.key">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>输入来源</span>
            <select v-model="form.sourceType" @change="handleSourceTypeChange">
              <option value="video">视频文件</option>
              <option value="image">图片文件</option>
              <option value="stream">视频流</option>
              <option value="edge-report">边缘上报</option>
            </select>
          </label>

          <label class="field field--full">
            <span>来源地址</span>
            <input
              v-model.trim="form.sourceUri"
              type="text"
              :placeholder="sourceUriPlaceholder"
            />
          </label>

          <label class="field">
            <span>事件时间</span>
            <input v-model="form.occurredAtLocal" type="datetime-local" />
          </label>

          <label class="field">
            <span>截图地址（可选）</span>
            <input
              v-model.trim="form.frameUri"
              type="text"
              placeholder="例如：/workspace/data/frames/cam-001.jpg"
            />
          </label>

          <label class="field field--full">
            <span>扩展元数据 JSON</span>
            <textarea
              v-model="form.metadataJson"
              rows="8"
              placeholder='{"remark":"阶段3演示导入"}'
            />
          </label>

          <p class="summary">
            {{ inferenceModeHint }}
            Docker 联调时，本地文件请使用容器可见路径，例如 `/workspace/...`；摄像头可直接填写 `rtsp://` 地址。
          </p>

          <p v-if="inferenceMetaError" class="error-text">{{ inferenceMetaError }}</p>

          <button class="primary-button" type="submit" :disabled="submitting || devices.length === 0">
            {{ submitting ? '导入中...' : '调用推理并写入事件' }}
          </button>
        </form>

        <p v-if="submitMessage" class="success-text">{{ submitMessage }}</p>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>最近行为事件</h3>
          <span class="panel__badge">{{ events.length }} 条</span>
        </header>

        <div class="form-grid">
          <label class="field">
            <span>按设备筛选</span>
            <select v-model="filters.deviceId" @change="loadEvents">
              <option value="">全部设备</option>
              <option v-for="device in devices" :key="device.id" :value="String(device.id)">
                {{ device.name }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>显示条数</span>
            <select v-model="filters.limit" @change="loadEvents">
              <option value="5">5 条</option>
              <option value="10">10 条</option>
              <option value="20">20 条</option>
            </select>
          </label>
        </div>

        <p v-if="loadError" class="error-text">{{ loadError }}</p>

        <div class="stack-list">
          <article v-for="event in events" :key="event.id" class="entity-card">
            <div class="event-visual-card">
              <EventMediaViewer :event="event" />

              <div class="event-visual-card__content">
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
                    <dt>关联区域</dt>
                    <dd>{{ event.zone_name || '未命中区域' }}</dd>
                  </div>
                  <div>
                    <dt>模型版本</dt>
                    <dd>{{ event.model_name }} / {{ event.model_version }}</dd>
                  </div>
                  <div>
                    <dt>推理来源</dt>
                    <dd>{{ event.inference_source }}</dd>
                  </div>
                  <div>
                    <dt>请求编号</dt>
                    <dd>{{ event.request_id }}</dd>
                  </div>
                </dl>

                <p class="entity-note">{{ event.notes || '本条事件未附加备注。' }}</p>
              </div>
            </div>
          </article>

          <p v-if="events.length === 0" class="entity-note">
            当前还没有行为事件，可以先在左侧导入一条推理结果。
          </p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { listDevices } from '@/api/devices';
import { fetchBehaviorEventSummary, fetchInferenceMeta, importBehaviorEvents, listBehaviorEvents } from '@/api/events';
import EventMediaViewer from '@/components/events/EventMediaViewer.vue';
import type { DeviceSummary } from '@/types/device';
import type {
  BehaviorEventStats,
  BehaviorEventSummary,
  EventSourceType,
  InferenceMeta,
  InferenceMode,
} from '@/types/event';

interface ImportFormState {
  deviceCode: string;
  inferenceMode: InferenceMode;
  yoloModelKey: string;
  sourceType: EventSourceType;
  sourceUri: string;
  occurredAtLocal: string;
  frameUri: string;
  metadataJson: string;
}

const devices = ref<DeviceSummary[]>([]);
const events = ref<BehaviorEventSummary[]>([]);
const inferenceMeta = ref<InferenceMeta | null>(null);
const summary = ref<BehaviorEventStats>({
  total_count: 0,
  today_count: 0,
  recent_events: [],
});
const loadError = ref('');
const inferenceMetaError = ref('');
const submitError = ref('');
const submitMessage = ref('');
const submitting = ref(false);

const filters = reactive({
  deviceId: '',
  limit: '10',
});

const form = reactive<ImportFormState>(createEmptyForm());

const latestModel = computed(() => summary.value.recent_events[0]?.model_name ?? '暂无');
const latestSource = computed(() => summary.value.recent_events[0]?.inference_source ?? '暂无');
const yoloModelOptions = computed(() => inferenceMeta.value?.available_yolo_models ?? []);
const sourceUriPlaceholder = computed(() => {
  if (form.sourceType === 'image') {
    return '例如：/workspace/data/images/cam-001.jpg';
  }
  if (form.sourceType === 'stream') {
    return '例如：rtsp://192.168.1.20:554/live';
  }
  if (form.sourceType === 'edge-report') {
    return '例如：/workspace/data/reports/cam-001.json 或边缘事件标识';
  }
  return '例如：/workspace/data/videos/cam-001.mp4';
});
const inferenceModeHint = computed(() =>
  form.inferenceMode === 'yolo-knn'
    ? '当前为“YOLO + KNN”模式：先检测牛只，再做姿态/行为分类。'
    : '当前为“仅 YOLO”模式：仅依据 YOLO 检测结果生成事件统计。',
);

function formatNowForInput() {
  const currentDate = new Date();
  const timezoneOffset = currentDate.getTimezoneOffset();
  const localDate = new Date(currentDate.getTime() - timezoneOffset * 60 * 1000);
  return localDate.toISOString().slice(0, 16);
}

function createEmptyForm(): ImportFormState {
  return {
    deviceCode: '',
    inferenceMode: 'yolo-knn',
    yoloModelKey: '',
    sourceType: 'video',
    sourceUri: '',
    occurredAtLocal: formatNowForInput(),
    frameUri: '',
    metadataJson: '{\n  "remark": "阶段3演示导入"\n}',
  };
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

function parseMetadata() {
  const parsed = JSON.parse(form.metadataJson) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('扩展元数据 JSON 必须是对象。');
  }
  return parsed as Record<string, unknown>;
}

function normalizeWorkspacePath(value: string) {
  const trimmed = value.trim();
  if (trimmed.startsWith('workspace/')) {
    return `/${trimmed}`;
  }
  return trimmed;
}

function applyInferenceDefaults() {
  if (
    inferenceMeta.value?.default_yolo_model_key &&
    (!form.yoloModelKey || !yoloModelOptions.value.some((option) => option.key === form.yoloModelKey))
  ) {
    form.yoloModelKey = inferenceMeta.value.default_yolo_model_key;
  }
  if (
    inferenceMeta.value?.default_inference_mode &&
    !inferenceMeta.value.available_inference_modes.includes(form.inferenceMode)
  ) {
    form.inferenceMode = inferenceMeta.value.default_inference_mode;
  }
}

function handleSourceTypeChange() {
  if (form.sourceUri.startsWith('demo://')) {
    form.sourceUri = '';
  }
  if (form.frameUri.startsWith('demo://')) {
    form.frameUri = '';
  }
}

function resetForm() {
  Object.assign(form, createEmptyForm());
  if (devices.value.length > 0) {
    form.deviceCode = devices.value[0].code;
  }
  applyInferenceDefaults();
  submitError.value = '';
  submitMessage.value = '';
}

async function loadDevices() {
  devices.value = await listDevices();
  if (!form.deviceCode && devices.value.length > 0) {
    form.deviceCode = devices.value[0].code;
  }
}

async function loadInferenceMeta() {
  inferenceMetaError.value = '';

  try {
    inferenceMeta.value = await fetchInferenceMeta();
    applyInferenceDefaults();
  } catch (error) {
    inferenceMetaError.value = error instanceof Error ? error.message : '无法加载推理模型配置。';
  }
}

async function loadSummary() {
  summary.value = await fetchBehaviorEventSummary();
}

async function loadEvents() {
  loadError.value = '';

  try {
    events.value = await listBehaviorEvents({
      deviceId: filters.deviceId ? Number(filters.deviceId) : undefined,
      limit: Number(filters.limit),
    });
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载行为事件列表。';
  }
}

async function refreshAll() {
  loadError.value = '';

  try {
    await Promise.all([loadDevices(), loadInferenceMeta(), loadSummary(), loadEvents()]);
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载阶段 3 行为事件数据。';
  }
}

async function submitImport() {
  submitting.value = true;
  submitError.value = '';
  submitMessage.value = '';

  try {
    if (!form.deviceCode) {
      throw new Error('请选择设备。');
    }

    const occurredAt = new Date(form.occurredAtLocal);
    if (Number.isNaN(occurredAt.getTime())) {
      throw new Error('请输入有效的事件时间。');
    }

    const result = await importBehaviorEvents({
      device_code: form.deviceCode,
      inference_mode: form.inferenceMode,
      source_type: form.sourceType,
      source_uri: normalizeWorkspacePath(form.sourceUri),
      occurred_at: occurredAt.toISOString(),
      frame_uri: form.frameUri ? normalizeWorkspacePath(form.frameUri) : null,
      yolo_model_key: form.yoloModelKey || null,
      metadata: parseMetadata(),
    });

    submitMessage.value = `已导入 ${result.imported_count} 条行为事件，模型 ${result.model_name} 已完成写库。`;
    await Promise.all([loadSummary(), loadEvents()]);
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '导入行为事件失败。';
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  await refreshAll();
});
</script>
