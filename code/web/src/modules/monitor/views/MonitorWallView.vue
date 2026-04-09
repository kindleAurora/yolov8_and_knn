<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">实时值守</p>
        <h2>画面监控</h2>
        <p class="page-header__text">
          汇总当前已接入视频流的设备画面，可直接对主监控位发起 YOLO / KNN 智能分析。
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
        <p>当前状态为在线的设备会优先展示在监控列表前列。</p>
      </article>
      <article class="metric-card">
        <span>当前主画面</span>
        <strong>{{ activeDevice?.code || '暂无' }}</strong>
        <p>点击右侧设备列表或下方缩略图即可切换主监控位。</p>
      </article>
      <article class="metric-card">
        <span>AI 分析状态</span>
        <strong>{{ analysisStateLabel }}</strong>
        <p>{{ analysisStateDescription }}</p>
      </article>
    </section>

    <div class="monitor-layout">
      <article class="panel panel--monitor-stage">
        <header class="panel__header">
          <div>
            <h3>主监控画面</h3>
            <p class="panel__description">
              {{
                activeDevice
                  ? `${activeDevice.name} / ${activeDevice.install_location || '未设置安装位置'}`
                  : '暂无可显示的主画面'
              }}
            </p>
          </div>
        </header>

        <DeviceLivePlayer
          v-if="activeDevice"
          :device="activeDevice"
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

    <div class="content-grid monitor-analysis-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>智能分析控制</h3>
          <span class="panel__badge">{{ activeDevice ? activeDevice.code : '未选择设备' }}</span>
        </header>

        <div class="form-grid">
          <label class="field">
            <span>分析模式</span>
            <select v-model="analysisMode">
              <option value="yolo-knn">YOLO + KNN 行为分类</option>
              <option value="yolo-only">仅 YOLO 检测</option>
            </select>
          </label>

          <label class="field">
            <span>YOLO 模型</span>
            <select v-model="selectedYoloModelKey">
              <option value="">使用默认模型</option>
              <option v-for="option in yoloModelOptions" :key="option.key" :value="option.key">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>分析策略</span>
            <select v-model="autoAnalyzeMode">
              <option value="manual">仅手动分析</option>
              <option value="1000">每 1 秒自动分析</option>
              <option value="3000">每 3 秒自动分析</option>
              <option value="10000">每 10 秒自动分析</option>
            </select>
          </label>

          <label class="field">
            <span>YOLO 置信度阈值</span>
            <input v-model.number="yoloConfidence" type="number" min="0" max="1" step="0.05" />
          </label>

          <label class="field">
            <span>YOLO IoU 阈值</span>
            <input v-model.number="yoloIou" type="number" min="0" max="1" step="0.05" />
          </label>

          <label class="field">
            <span>KNN 置信度阈值</span>
            <input
              v-model.number="knnConfidenceThreshold"
              type="number"
              min="0"
              max="1"
              step="0.05"
              :disabled="analysisMode !== 'yolo-knn'"
            />
          </label>

          <div class="field">
            <span>当前说明</span>
            <p class="entity-note monitor-analysis__hint">
              监控页会直接读取当前主画面的实时流进行分析，并把结果写入事件库供首页和事件中心复用。
              当前阈值会随每次分析一并写入结果，后续结果图也会按同一组阈值回放。
            </p>
          </div>
        </div>

        <div class="entity-actions">
          <button
            class="primary-button"
            type="button"
            :disabled="!activeDevice || analysisSubmitting"
            @click="runDeviceAnalysis()"
          >
            {{ analysisSubmitting ? '分析中...' : '分析当前画面' }}
          </button>
          <button
            class="ghost-button"
            type="button"
            :disabled="analysisSubmitting"
            @click="clearAnalysisResult"
          >
            清空结果
          </button>
        </div>

        <p v-if="inferenceMetaError" class="error-text">{{ inferenceMetaError }}</p>
        <p v-if="analysisMessage" class="success-text">{{ analysisMessage }}</p>
        <p v-if="analysisError" class="error-text">{{ analysisError }}</p>
        <p v-if="recentAnalysisError" class="error-text">{{ recentAnalysisError }}</p>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>最新分析结果</h3>
          <span class="panel__badge">{{ analysisEvents.length }} 条</span>
        </header>

        <template v-if="activeAnalysisEvent">
          <div class="monitor-analysis__meta">
            <strong>{{ activeAnalysisEvent.behavior_type }}</strong>
            <span>
              请求编号 {{ activeAnalysisRequestLabel }} / 模型 {{ activeAnalysisModelLabel }}
            </span>
          </div>

          <EventMediaViewer :event="activeAnalysisEvent" />

          <div class="stack-list analysis-event-list">
            <article
              v-for="event in analysisEvents"
              :key="event.id"
              class="entity-card"
            >
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
                  <dt>来源</dt>
                  <dd>{{ event.inference_source }}</dd>
                </div>
              </dl>
            </article>
          </div>
        </template>

        <p v-else class="entity-note">
          当前还没有监控分析结果。点击“分析当前画面”即可直接对主监控位进行推理，不需要再去事件中心手动填写流地址。
        </p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { listDevices } from '@/api/devices';
import { fetchInferenceMeta, importBehaviorEvents, listBehaviorEvents } from '@/api/events';
import EventMediaViewer from '@/components/events/EventMediaViewer.vue';
import DeviceLivePlayer from '@/components/monitor/DeviceLivePlayer.vue';
import DevicePreviewPanel from '@/components/monitor/DevicePreviewPanel.vue';
import type { DeviceSummary } from '@/types/device';
import type {
  BehaviorEventImportResult,
  BehaviorEventSummary,
  EventSourceType,
  InferenceMeta,
  InferenceMode,
} from '@/types/event';

const devices = ref<DeviceSummary[]>([]);
const activeDeviceId = ref<number | null>(null);
const loadError = ref('');
const inferenceMeta = ref<InferenceMeta | null>(null);
const inferenceMetaError = ref('');
const analysisMode = ref<InferenceMode>('yolo-knn');
const selectedYoloModelKey = ref('');
const autoAnalyzeMode = ref('1000');
const yoloConfidence = ref(0.25);
const yoloIou = ref(0.45);
const knnConfidenceThreshold = ref(0);
const analysisSubmitting = ref(false);
const analysisError = ref('');
const analysisMessage = ref('');
const analysisResult = ref<BehaviorEventImportResult | null>(null);
const recentDeviceEvents = ref<BehaviorEventSummary[]>([]);
const recentAnalysisError = ref('');

let autoAnalyzeTimer: number | null = null;
let thresholdDefaultsInitialized = false;

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
const yoloModelOptions = computed(() => inferenceMeta.value?.available_yolo_models ?? []);
const resolvedYoloConfidence = computed(() =>
  normalizeThreshold(yoloConfidence.value, inferenceMeta.value?.default_yolo_confidence ?? 0.25),
);
const resolvedYoloIou = computed(() =>
  normalizeThreshold(yoloIou.value, inferenceMeta.value?.default_yolo_iou ?? 0.45),
);
const resolvedKnnConfidenceThreshold = computed(() =>
  normalizeThreshold(
    knnConfidenceThreshold.value,
    inferenceMeta.value?.default_knn_confidence_threshold ?? 0,
  ),
);
const analysisEvents = computed<BehaviorEventSummary[]>(() =>
  analysisResult.value?.behavior_events ?? recentDeviceEvents.value,
);
const activeAnalysisEvent = computed<BehaviorEventSummary | null>(() => analysisEvents.value[0] ?? null);
const activeAnalysisRequestLabel = computed(
  () => analysisResult.value?.request_id || activeAnalysisEvent.value?.request_id || '暂无请求编号',
);
const activeAnalysisModelLabel = computed(
  () => analysisResult.value?.model_name || activeAnalysisEvent.value?.model_name || '暂无模型信息',
);
const analysisStateLabel = computed(() => {
  if (analysisSubmitting.value) {
    return '分析中';
  }
  if (analysisError.value) {
    return '分析异常';
  }
  if (analysisEvents.value.length > 0) {
    return '结果已更新';
  }
  return autoAnalyzeMode.value === 'manual' ? '待触发' : '自动分析';
});
const analysisStateDescription = computed(() => {
  if (analysisError.value) {
    return analysisError.value;
  }
  if (analysisEvents.value.length > 0) {
    if (analysisResult.value) {
      return `最近一次监控分析写入了 ${analysisEvents.value.length} 条事件，可在下方直接查看结果图。`;
    }
    return `已加载该设备最近 ${analysisEvents.value.length} 条分析事件，监控页会继续自动补充新结果。`;
  }
  if (autoAnalyzeMode.value === 'manual') {
    return '当前为手动触发模式，可随时对主监控位执行一次分析。';
  }
  return `当前主画面会按 ${Number(autoAnalyzeMode.value) / 1000} 秒周期自动分析。`;
});

function normalizeThreshold(value: number, fallback: number) {
  if (!Number.isFinite(value)) {
    return fallback;
  }

  return Math.min(1, Math.max(0, value));
}

async function loadDevices() {
  loadError.value = '';

  try {
    devices.value = await listDevices();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载监控设备列表。';
  }
}

async function loadInferenceMeta() {
  inferenceMetaError.value = '';

  try {
    inferenceMeta.value = await fetchInferenceMeta();
    if (inferenceMeta.value.default_yolo_model_key && !selectedYoloModelKey.value) {
      selectedYoloModelKey.value = inferenceMeta.value.default_yolo_model_key;
    }
    if (!thresholdDefaultsInitialized) {
      yoloConfidence.value = inferenceMeta.value.default_yolo_confidence;
      yoloIou.value = inferenceMeta.value.default_yolo_iou;
      knnConfidenceThreshold.value = inferenceMeta.value.default_knn_confidence_threshold;
      thresholdDefaultsInitialized = true;
    }
  } catch (error) {
    inferenceMetaError.value = error instanceof Error ? error.message : '无法加载推理模型配置。';
  }
}

async function loadRecentAnalysisEvents() {
  recentAnalysisError.value = '';

  if (!activeDevice.value) {
    recentDeviceEvents.value = [];
    return;
  }

  try {
    recentDeviceEvents.value = await listBehaviorEvents({
      deviceId: activeDevice.value.id,
      limit: 6,
    });
  } catch (error) {
    recentAnalysisError.value = error instanceof Error ? error.message : '无法加载当前设备最近分析结果。';
    recentDeviceEvents.value = [];
  }
}

function stopAutoAnalyzeLoop() {
  if (autoAnalyzeTimer !== null) {
    window.clearInterval(autoAnalyzeTimer);
    autoAnalyzeTimer = null;
  }
}

function clearAnalysisResult() {
  analysisResult.value = null;
  analysisError.value = '';
  analysisMessage.value = '';
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

async function runDeviceAnalysis(options: { silent?: boolean } = {}) {
  if (!activeDevice.value || analysisSubmitting.value) {
    return;
  }

  analysisSubmitting.value = true;
  analysisError.value = '';
  if (!options.silent) {
    analysisMessage.value = '';
  }

  try {
    const result = await importBehaviorEvents({
      device_code: activeDevice.value.code,
      inference_mode: analysisMode.value,
      source_type: 'stream',
      source_uri: activeDevice.value.stream_url,
      occurred_at: new Date().toISOString(),
      frame_uri: null,
      yolo_model_key: selectedYoloModelKey.value || null,
      metadata: {
        trigger: options.silent ? 'monitor-auto' : 'monitor-manual',
        entry: 'monitor-wall',
        analysis_profile: 'realtime',
        max_video_frames: 12,
        frame_stride: 2,
        yolo_confidence: resolvedYoloConfidence.value,
        yolo_iou: resolvedYoloIou.value,
        knn_confidence_threshold: resolvedKnnConfidenceThreshold.value,
      },
    });

    analysisResult.value = result;
    recentDeviceEvents.value = result.behavior_events;
    analysisMessage.value =
      result.imported_count > 0
        ? `已从当前主画面写入 ${result.imported_count} 条分析事件。`
        : '本次分析已完成，但没有生成可写入的行为事件。';
  } catch (error) {
    analysisError.value = error instanceof Error ? error.message : '当前主画面分析失败。';
  } finally {
    analysisSubmitting.value = false;
  }
}

function restartAutoAnalyzeLoop() {
  stopAutoAnalyzeLoop();

  const intervalMs = Number(autoAnalyzeMode.value);
  if (!activeDevice.value || !Number.isFinite(intervalMs) || intervalMs <= 0) {
    return;
  }

  void runDeviceAnalysis({ silent: true });
  autoAnalyzeTimer = window.setInterval(() => {
    void runDeviceAnalysis({ silent: true });
  }, intervalMs);
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

watch(
  () => activeDevice.value?.id,
  () => {
    clearAnalysisResult();
  },
);

watch(
  () => [
    activeDevice.value?.id,
    activeDevice.value?.stream_url,
    analysisMode.value,
    selectedYoloModelKey.value,
    autoAnalyzeMode.value,
    resolvedYoloConfidence.value,
    resolvedYoloIou.value,
    resolvedKnnConfidenceThreshold.value,
  ],
  () => {
    analysisError.value = '';
    analysisMessage.value = '';
    void loadRecentAnalysisEvents();
    restartAutoAnalyzeLoop();
  },
);

onMounted(async () => {
  await Promise.all([loadDevices(), loadInferenceMeta()]);
});

onBeforeUnmount(() => {
  stopAutoAnalyzeLoop();
});
</script>
