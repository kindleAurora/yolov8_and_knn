<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">事件中心</p>
        <h2>行为事件中心</h2>
        <p class="page-header__text">
          查看已入库的行为事件，并把当天牛群状态按行为分布和时间轴直观展示出来。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="event-overview-grid">
      <article class="panel panel--behavior-hero">
        <header class="panel__header panel__header--stack">
          <div>
            <h3>今日状态看板</h3>
            <p class="panel__subtext">
              {{ selectedDeviceLabel }} · {{ activeOverview.date }}
            </p>
          </div>
          <span class="panel__badge">{{ activeOverview.total_events }} 条事件</span>
        </header>

        <div class="behavior-kpi-grid">
          <article class="behavior-kpi-card behavior-kpi-card--accent">
            <span>累计事件</span>
            <strong>{{ summary.total_count }}</strong>
            <p>当前筛选范围内累计写入的行为事件总数。</p>
          </article>
          <article class="behavior-kpi-card">
            <span>今日事件</span>
            <strong>{{ summary.today_count }}</strong>
            <p>从今日 00:00 到当前时间识别出的行为事件。</p>
          </article>
          <article class="behavior-kpi-card">
            <span>躺卧事件</span>
            <strong>{{ activeOverview.lying_event_count }}</strong>
            <p>今日识别到的躺卧状态事件次数。</p>
          </article>
          <article class="behavior-kpi-card">
            <span>站立时长</span>
            <strong>{{ formatDuration(activeOverview.standing_duration_seconds) }}</strong>
            <p>根据相邻事件时间估算的站立持续时间。</p>
          </article>
        </div>

        <div class="behavior-insight-grid">
          <article class="behavior-insight-card">
            <span>主导状态</span>
            <strong>{{ activeOverview.dominant_behavior || '暂无数据' }}</strong>
            <p>按今日累计时长占比最高的行为状态。</p>
          </article>
          <article class="behavior-insight-card">
            <span>覆盖时长</span>
            <strong>{{ formatDuration(activeOverview.tracked_duration_seconds) }}</strong>
            <p>当前可由事件流连续估算出的状态总时长。</p>
          </article>
          <article class="behavior-insight-card">
            <span>最近模型</span>
            <strong>{{ latestModel }}</strong>
            <p>{{ latestSource }}</p>
          </article>
        </div>

        <p class="summary summary--muted">
          当前可视化按“相邻事件时间差”估算持续时长，适合展示今日状态走势；如果后续接入单牛追踪 ID，还可以继续细化到单头牛的日轨迹。
        </p>
      </article>

      <article class="panel">
        <header class="panel__header panel__header--stack">
          <div>
            <h3>行为分布</h3>
            <p class="panel__subtext">按今日事件数与状态时长汇总</p>
          </div>
        </header>

        <div v-if="activeOverview.breakdown.length > 0" class="behavior-distribution">
          <div class="behavior-distribution__bar" aria-hidden="true">
            <div
              v-for="item in activeOverview.breakdown"
              :key="item.behavior_key"
              class="behavior-distribution__segment"
              :style="buildDistributionStyle(item)"
              :title="`${item.behavior_type} · ${formatDuration(item.duration_seconds)}`"
            />
          </div>

          <div class="behavior-breakdown-list">
            <article
              v-for="item in activeOverview.breakdown"
              :key="item.behavior_key"
              class="behavior-breakdown-item"
            >
              <div class="behavior-breakdown-item__top">
                <div class="behavior-chip">
                  <span
                    class="behavior-chip__dot"
                    :style="{ background: getBehaviorTheme(item.behavior_key).accent }"
                  />
                  <strong>{{ item.behavior_type }}</strong>
                </div>
                <strong>{{ item.event_count }} 次</strong>
              </div>

              <div class="behavior-progress" aria-hidden="true">
                <div class="behavior-progress__track">
                  <div
                    class="behavior-progress__fill"
                    :style="buildProgressStyle(item)"
                  />
                </div>
              </div>

              <div class="behavior-breakdown-item__meta">
                <span>时长 {{ formatDuration(item.duration_seconds) }}</span>
                <span>占比 {{ formatPercent(item.duration_share) }}</span>
              </div>
              <div class="behavior-breakdown-item__meta">
                <span>牛只累计 {{ item.cow_count_total }}</span>
                <span>事件占比 {{ formatPercent(item.event_share) }}</span>
              </div>
            </article>
          </div>
        </div>

        <p v-else class="entity-note">
          今日还没有可用于绘制分布图的行为事件。
        </p>
      </article>
    </section>

    <article class="panel panel--timeline">
      <header class="panel__header panel__header--stack">
        <div>
          <h3>今日状态时间轴</h3>
          <p class="panel__subtext">从 00:00 到当前时间的行为切换过程</p>
        </div>
        <span class="panel__badge">{{ activeOverview.timeline.length }} 段</span>
      </header>

      <div v-if="activeOverview.timeline.length > 0" class="behavior-timeline">
        <div class="behavior-timeline__track">
          <div
            v-for="segment in activeOverview.timeline"
            :key="`${segment.behavior_key}-${segment.started_at}-${segment.ended_at}`"
            class="behavior-timeline__segment"
            :style="buildTimelineStyle(segment)"
            :title="formatTimelineTitle(segment)"
          >
            <span>{{ segment.behavior_type }}</span>
          </div>
        </div>

        <div class="behavior-timeline__axis">
          <span>{{ formatTime(activeOverview.window_started_at) }}</span>
          <span>{{ formatTime(activeOverview.window_ended_at) }}</span>
        </div>

        <div class="behavior-timeline__legend">
          <div
            v-for="item in activeOverview.breakdown"
            :key="`legend-${item.behavior_key}`"
            class="behavior-chip behavior-chip--legend"
          >
            <span
              class="behavior-chip__dot"
              :style="{ background: getBehaviorTheme(item.behavior_key).accent }"
            />
            <span>{{ item.behavior_type }}</span>
          </div>
        </div>
      </div>

      <p v-else class="entity-note">
        今日还没有状态时间轴数据，导入或识别事件后这里会自动更新。
      </p>
    </article>

    <div class="content-grid event-content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>补录 / 校验推理</h3>
          <button class="ghost-button" type="button" @click="resetForm">重置表单</button>
        </header>

        <p class="summary">
          实时摄像头分析入口已经放在“画面监控”页。本页主要用于补录历史文件、校验边缘回传结果，或对指定来源做一次性人工复核。
        </p>

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

          <label class="field">
            <span>YOLO 置信度阈值</span>
            <input v-model.number="form.yoloConfidence" type="number" min="0" max="1" step="0.05" />
          </label>

          <label class="field">
            <span>YOLO IoU 阈值</span>
            <input v-model.number="form.yoloIou" type="number" min="0" max="1" step="0.05" />
          </label>

          <label class="field">
            <span>KNN 置信度阈值</span>
            <input
              v-model.number="form.knnConfidenceThreshold"
              type="number"
              min="0"
              max="1"
              step="0.05"
              :disabled="form.inferenceMode !== 'yolo-knn'"
            />
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
              placeholder='{"remark":"人工复核导入"}'
            />
          </label>

          <p class="summary">
            {{ inferenceModeHint }}
            Docker 联调时，本地文件请使用容器可见路径，例如 `/workspace/...`；摄像头可直接填写 `rtsp://` 地址。
          </p>

          <p v-if="inferenceMetaError" class="error-text">{{ inferenceMetaError }}</p>

          <button class="primary-button" type="submit" :disabled="submitting || devices.length === 0">
            {{ submitting ? '处理中...' : '执行补录推理并写入事件' }}
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
            <select v-model="filters.deviceId" @change="handleFilterChange">
              <option value="">全部设备</option>
              <option v-for="device in devices" :key="device.id" :value="String(device.id)">
                {{ device.name }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>显示条数</span>
            <select v-model="filters.limit" @change="handleFilterChange">
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
              <EventMediaViewer :event="event" lazy />

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
            当前还没有行为事件，可以先在画面监控中直接分析实时画面，或在左侧补录一条历史推理结果。
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
  BehaviorBreakdownItem,
  BehaviorEventStats,
  BehaviorEventSummary,
  BehaviorTimelineSegment,
  DailyBehaviorOverview,
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
  yoloConfidence: number;
  yoloIou: number;
  knnConfidenceThreshold: number;
}

interface BehaviorTheme {
  accent: string;
  soft: string;
  text: string;
}

const behaviorThemeMap: Record<string, BehaviorTheme> = {
  lying: {
    accent: '#4f7cff',
    soft: 'linear-gradient(135deg, rgba(79, 124, 255, 0.96), rgba(109, 156, 255, 0.82))',
    text: '#f7fbff',
  },
  standing: {
    accent: '#f08c2b',
    soft: 'linear-gradient(135deg, rgba(240, 140, 43, 0.96), rgba(255, 180, 93, 0.82))',
    text: '#fff9f1',
  },
  walking: {
    accent: '#14a06f',
    soft: 'linear-gradient(135deg, rgba(20, 160, 111, 0.96), rgba(74, 196, 148, 0.82))',
    text: '#f4fffb',
  },
  feeding: {
    accent: '#9c6ade',
    soft: 'linear-gradient(135deg, rgba(156, 106, 222, 0.96), rgba(191, 149, 242, 0.82))',
    text: '#fbf7ff',
  },
  drinking: {
    accent: '#0b9fb8',
    soft: 'linear-gradient(135deg, rgba(11, 159, 184, 0.96), rgba(86, 204, 227, 0.82))',
    text: '#f3feff',
  },
  resting: {
    accent: '#667085',
    soft: 'linear-gradient(135deg, rgba(102, 112, 133, 0.96), rgba(142, 152, 173, 0.82))',
    text: '#f7f9fb',
  },
  other: {
    accent: '#8d9aa3',
    soft: 'linear-gradient(135deg, rgba(141, 154, 163, 0.96), rgba(188, 196, 202, 0.82))',
    text: '#f8fbfc',
  },
};

const devices = ref<DeviceSummary[]>([]);
const events = ref<BehaviorEventSummary[]>([]);
const inferenceMeta = ref<InferenceMeta | null>(null);
const summary = ref<BehaviorEventStats>(createEmptyBehaviorStats());
const loadError = ref('');
const inferenceMetaError = ref('');
const submitError = ref('');
const submitMessage = ref('');
const submitting = ref(false);

const filters = reactive({
  deviceId: '',
  limit: '5',
});

let thresholdDefaultsInitialized = false;
const form = reactive<ImportFormState>(createEmptyForm());

const activeOverview = computed(() => summary.value.today_behavior_overview);
const selectedDeviceLabel = computed(() => {
  if (!filters.deviceId) {
    return '全牧场';
  }

  const target = devices.value.find((device) => device.id === Number(filters.deviceId));
  return target?.name ?? '当前设备';
});
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
    ? '当前为“YOLO + KNN”模式：先检测牛只，再做姿态 / 行为分类。'
    : '当前为“仅 YOLO”模式：仅依据 YOLO 检测结果生成事件统计。',
);
const resolvedYoloConfidence = computed(() =>
  normalizeThreshold(form.yoloConfidence, inferenceMeta.value?.default_yolo_confidence ?? 0.25),
);
const resolvedYoloIou = computed(() =>
  normalizeThreshold(form.yoloIou, inferenceMeta.value?.default_yolo_iou ?? 0.45),
);
const resolvedKnnConfidenceThreshold = computed(() =>
  normalizeThreshold(
    form.knnConfidenceThreshold,
    inferenceMeta.value?.default_knn_confidence_threshold ?? 0,
  ),
);

function createEmptyBehaviorOverview(): DailyBehaviorOverview {
  const now = new Date().toISOString();
  return {
    date: new Date().toLocaleDateString(),
    window_started_at: now,
    window_ended_at: now,
    total_events: 0,
    tracked_duration_seconds: 0,
    lying_event_count: 0,
    standing_duration_seconds: 0,
    dominant_behavior: null,
    breakdown: [],
    timeline: [],
  };
}

function createEmptyBehaviorStats(): BehaviorEventStats {
  return {
    total_count: 0,
    today_count: 0,
    recent_events: [],
    today_behavior_overview: createEmptyBehaviorOverview(),
  };
}

function formatNowForInput() {
  const currentDate = new Date();
  const timezoneOffset = currentDate.getTimezoneOffset();
  const localDate = new Date(currentDate.getTime() - timezoneOffset * 60 * 1000);
  return localDate.toISOString().slice(0, 16);
}

function normalizeThreshold(value: number, fallback: number) {
  if (!Number.isFinite(value)) {
    return fallback;
  }

  return Math.min(1, Math.max(0, value));
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
    metadataJson: '{\n  "remark": "人工复核导入"\n}',
    yoloConfidence: inferenceMeta.value?.default_yolo_confidence ?? 0.25,
    yoloIou: inferenceMeta.value?.default_yolo_iou ?? 0.45,
    knnConfidenceThreshold: inferenceMeta.value?.default_knn_confidence_threshold ?? 0,
  };
}

function getBehaviorTheme(behaviorKey: string): BehaviorTheme {
  return behaviorThemeMap[behaviorKey] ?? behaviorThemeMap.other;
}

function buildDistributionStyle(item: BehaviorBreakdownItem) {
  const theme = getBehaviorTheme(item.behavior_key);
  return {
    background: theme.soft,
    flexGrow: String(Math.max(item.duration_seconds, 1)),
  };
}

function buildProgressStyle(item: BehaviorBreakdownItem) {
  const theme = getBehaviorTheme(item.behavior_key);
  return {
    background: theme.soft,
    width: `${Math.max(item.duration_share * 100, item.duration_seconds > 0 ? 6 : 0)}%`,
  };
}

function buildTimelineStyle(segment: BehaviorTimelineSegment) {
  const theme = getBehaviorTheme(segment.behavior_key);
  return {
    background: theme.soft,
    color: theme.text,
    flexGrow: String(Math.max(segment.duration_seconds, 1)),
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

function formatTime(value: string) {
  return new Date(value).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function formatDuration(seconds: number) {
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return '0 分钟';
  }

  const totalMinutes = Math.floor(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  if (hours > 0 && minutes > 0) {
    return `${hours} 小时 ${minutes} 分钟`;
  }
  if (hours > 0) {
    return `${hours} 小时`;
  }
  if (totalMinutes > 0) {
    return `${totalMinutes} 分钟`;
  }
  return `${seconds} 秒`;
}

function formatTimelineTitle(segment: BehaviorTimelineSegment) {
  return `${segment.behavior_type} · ${formatTime(segment.started_at)} - ${formatTime(segment.ended_at)} · ${formatDuration(segment.duration_seconds)}`;
}

function parseMetadata() {
  const parsed = JSON.parse(form.metadataJson) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('扩展元数据 JSON 必须是对象。');
  }
  return parsed as Record<string, unknown>;
}

function buildImportMetadata() {
  return {
    ...parseMetadata(),
    yolo_confidence: resolvedYoloConfidence.value,
    yolo_iou: resolvedYoloIou.value,
    knn_confidence_threshold: resolvedKnnConfidenceThreshold.value,
  };
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
  if (!thresholdDefaultsInitialized && inferenceMeta.value) {
    form.yoloConfidence = inferenceMeta.value.default_yolo_confidence;
    form.yoloIou = inferenceMeta.value.default_yolo_iou;
    form.knnConfidenceThreshold = inferenceMeta.value.default_knn_confidence_threshold;
    thresholdDefaultsInitialized = true;
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
  summary.value = await fetchBehaviorEventSummary(filters.deviceId ? Number(filters.deviceId) : undefined);
}

async function loadEvents() {
  events.value = await listBehaviorEvents({
    deviceId: filters.deviceId ? Number(filters.deviceId) : undefined,
    limit: Number(filters.limit),
  });
}

async function handleFilterChange() {
  loadError.value = '';

  try {
    await Promise.all([loadSummary(), loadEvents()]);
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载行为事件数据。';
  }
}

async function refreshAll() {
  loadError.value = '';

  try {
    await Promise.all([loadDevices(), loadInferenceMeta(), loadSummary(), loadEvents()]);
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载行为事件数据。';
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
      metadata: buildImportMetadata(),
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

<style scoped>
.event-overview-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
  gap: 24px;
  margin-bottom: 24px;
}

.panel__header--stack {
  align-items: start;
}

.panel__subtext {
  margin: 6px 0 0;
  color: #62727d;
}

.panel--behavior-hero {
  overflow: hidden;
  background:
    radial-gradient(circle at top right, rgba(79, 124, 255, 0.14), transparent 30%),
    linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(241, 247, 252, 0.98));
}

.behavior-kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
}

.behavior-kpi-card,
.behavior-insight-card {
  display: grid;
  gap: 8px;
  padding: 18px;
  border: 1px solid rgba(79, 97, 108, 0.1);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.behavior-kpi-card--accent {
  background: linear-gradient(135deg, rgba(35, 74, 120, 0.98), rgba(79, 124, 255, 0.88));
  color: #f5f9ff;
}

.behavior-kpi-card span,
.behavior-insight-card span {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.behavior-kpi-card strong,
.behavior-insight-card strong {
  font-size: clamp(1.4rem, 2.2vw, 2rem);
  line-height: 1.1;
}

.behavior-kpi-card p,
.behavior-insight-card p {
  margin: 0;
  color: #60707b;
  line-height: 1.6;
}

.behavior-kpi-card--accent p {
  color: rgba(245, 249, 255, 0.82);
}

.behavior-insight-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
  margin-top: 14px;
}

.summary--muted {
  margin-top: 16px;
}

.behavior-distribution {
  display: grid;
  gap: 18px;
}

.behavior-distribution__bar {
  display: flex;
  min-height: 26px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(226, 234, 239, 0.9);
}

.behavior-distribution__segment {
  min-width: 12px;
}

.behavior-breakdown-list {
  display: grid;
  gap: 12px;
}

.behavior-breakdown-item {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-radius: 18px;
  background: rgba(244, 248, 250, 0.92);
}

.behavior-breakdown-item__top,
.behavior-breakdown-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.behavior-breakdown-item__meta {
  font-size: 13px;
  color: #62727d;
}

.behavior-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.behavior-chip--legend {
  color: #4c5d68;
  font-size: 13px;
  font-weight: 600;
}

.behavior-chip__dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  flex-shrink: 0;
}

.behavior-progress__track {
  height: 8px;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(219, 229, 234, 0.95);
}

.behavior-progress__fill {
  height: 100%;
  border-radius: inherit;
}

.panel--timeline {
  margin-bottom: 24px;
}

.behavior-timeline {
  display: grid;
  gap: 14px;
}

.behavior-timeline__track {
  display: flex;
  min-height: 64px;
  overflow: hidden;
  border-radius: 22px;
  background: rgba(237, 243, 245, 0.95);
}

.behavior-timeline__segment {
  display: flex;
  align-items: end;
  min-width: 12px;
  padding: 10px;
  font-size: 12px;
  font-weight: 700;
}

.behavior-timeline__segment span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.behavior-timeline__axis {
  display: flex;
  align-items: center;
  justify-content: space-between;
  color: #61707b;
  font-size: 13px;
}

.behavior-timeline__legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 16px;
}

.event-content-grid {
  align-items: start;
}

@media (max-width: 1180px) {
  .event-overview-grid {
    grid-template-columns: 1fr;
  }

  .behavior-kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .behavior-insight-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .behavior-kpi-grid {
    grid-template-columns: 1fr;
  }

  .behavior-breakdown-item__top,
  .behavior-breakdown-item__meta {
    align-items: start;
    flex-direction: column;
  }

  .behavior-timeline__segment {
    min-width: 8px;
    padding: 8px;
  }

  .behavior-timeline__segment span {
    display: none;
  }
}
</style>
