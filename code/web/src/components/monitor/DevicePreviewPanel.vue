<template>
  <article
    :class="[
      'monitor-preview',
      {
        'monitor-preview--compact': compact,
        'monitor-preview--interactive': showControls,
      },
    ]"
  >
    <header class="monitor-preview__header">
      <div>
        <p class="monitor-preview__eyebrow">{{ device.code }}</p>
        <strong>{{ device.name }}</strong>
        <p class="monitor-preview__meta">
          {{ device.install_location || '未设置安装位置' }} / {{ statusLabel }}
        </p>
      </div>
      <span :class="['service-badge', `service-badge--${previewStatusTone}`]">
        {{ previewStatusLabel }}
      </span>
    </header>

    <div
      ref="stageElement"
      :class="[
        'monitor-preview__stage',
        {
          'monitor-preview__stage--interactive': showControls,
          'monitor-preview__stage--draggable': canPan,
          'monitor-preview__stage--dragging': isDragging,
        },
      ]"
      :style="stageInteractionStyle"
      @pointerdown="startDrag"
      @pointermove="updateDrag"
      @pointerup="endDrag"
      @pointercancel="endDrag"
    >
      <div v-if="previewUrl" class="monitor-preview__pan-layer" :style="panStyle">
        <img
          ref="imageElement"
          :src="previewUrl"
          :alt="`${device.name} 监控预览`"
          class="monitor-preview__image"
          :style="mediaStyle"
          @load="handleImageLoad"
        />
      </div>
      <div v-else class="monitor-preview__empty">
        <strong>{{ loading ? '正在抓取画面...' : '暂无可用画面' }}</strong>
        <p>{{ previewError || '请检查视频流地址是否可访问，或稍后重试。' }}</p>
      </div>
    </div>

    <footer v-if="showControls" class="monitor-preview__controls">
      <button class="ghost-button" type="button" :disabled="zoom <= 1" @click="zoomOut">
        缩小
      </button>
      <button class="ghost-button" type="button" @click="zoomIn">
        放大
      </button>
      <button class="ghost-button" type="button" @click="setFitMode('contain')">
        适应画面
      </button>
      <button class="ghost-button" type="button" @click="setFitMode('cover')">
        填满窗口
      </button>
      <button class="ghost-button" type="button" @click="loadPreview">
        立即刷新
      </button>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { fetchDevicePreview } from '@/api/media';
import { useMediaViewportInteraction } from '@/composables/useMediaViewportInteraction';
import type { DeviceSummary } from '@/types/device';

const props = withDefaults(
  defineProps<{
    device: DeviceSummary;
    refreshMs?: number;
    compact?: boolean;
    showControls?: boolean;
  }>(),
  {
    refreshMs: 6000,
    compact: false,
    showControls: false,
  },
);

const previewUrl = ref('');
const imageElement = ref<HTMLImageElement | null>(null);
const stageElement = ref<HTMLElement | null>(null);
const loading = ref(false);
const previewError = ref('');
const zoom = ref(1);
const fitMode = ref<'contain' | 'cover'>('contain');
const intrinsicSize = ref({ width: 0, height: 0 });
const offsetX = ref(0);
const offsetY = ref(0);
const isDragging = ref(false);

let refreshTimer: number | null = null;

const statusLabel = computed(() => {
  if (props.device.status === 'online') {
    return '设备在线';
  }
  if (props.device.status === 'offline') {
    return '设备离线';
  }
  return '设备停用';
});
const previewStatusLabel = computed(() => {
  if (loading.value) {
    return '抓帧中';
  }
  if (previewError.value) {
    return '预览异常';
  }
  return props.device.status === 'online' ? '画面正常' : statusLabel.value;
});
const previewStatusTone = computed(() => {
  if (loading.value) {
    return 'unknown';
  }
  if (previewError.value || props.device.status !== 'online') {
    return 'down';
  }
  return 'up';
});
const {
  canPan,
  endDrag,
  mediaStyle,
  panStyle,
  resetViewport,
  stageInteractionStyle,
  startDrag,
  updateDrag,
} = useMediaViewportInteraction({
  fitMode,
  zoom,
  stageRef: stageElement,
  intrinsicSize,
  offsetX,
  offsetY,
  isDragging,
});

function revokePreviewUrl() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = '';
  }
}

function handleImageLoad() {
  const image = imageElement.value;
  if (!image) {
    return;
  }

  intrinsicSize.value = {
    width: image.naturalWidth,
    height: image.naturalHeight,
  };
}

async function loadPreview() {
  if (loading.value) {
    return;
  }

  loading.value = true;
  previewError.value = '';

  try {
    const blob = await fetchDevicePreview(props.device.id);
    const nextUrl = URL.createObjectURL(blob);
    revokePreviewUrl();
    previewUrl.value = nextUrl;
  } catch (error) {
    previewError.value = error instanceof Error ? error.message : '无法抓取监控画面。';
  } finally {
    loading.value = false;
  }
}

function startRefreshLoop() {
  stopRefreshLoop();
  void loadPreview();
  if (props.refreshMs > 0) {
    refreshTimer = window.setInterval(() => {
      void loadPreview();
    }, props.refreshMs);
  }
}

function stopRefreshLoop() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

function zoomIn() {
  zoom.value = Math.min(zoom.value + 0.25, 3);
}

function zoomOut() {
  zoom.value = Math.max(zoom.value - 0.25, 1);
}

function setFitMode(mode: 'contain' | 'cover') {
  fitMode.value = mode;
  resetViewport();
}

watch(
  () => [props.device.id, props.device.stream_url],
  () => {
    zoom.value = 1;
    fitMode.value = 'contain';
    intrinsicSize.value = { width: 0, height: 0 };
    resetViewport();
    startRefreshLoop();
  },
);

onMounted(() => {
  startRefreshLoop();
});

onBeforeUnmount(() => {
  stopRefreshLoop();
  revokePreviewUrl();
});
</script>
