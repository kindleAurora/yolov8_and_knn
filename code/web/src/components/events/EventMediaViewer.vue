<template>
  <section ref="rootElement" class="event-media">
    <header class="event-media__header">
      <div>
        <p class="event-media__eyebrow">事件可视区</p>
        <strong>{{ mediaTitle }}</strong>
      </div>
      <button class="ghost-button" type="button" @click="refreshMedia">
        刷新画面
      </button>
    </header>

    <div class="event-media__stack">
      <div class="event-media__panel">
        <p class="event-media__label">检测结果</p>
        <div class="event-media__stage">
          <img
            v-if="previewUrl"
            class="event-media__image"
            :src="previewUrl"
            :alt="`${event.behavior_type} 检测结果图`"
          />

          <div v-if="previewUrl && loading" class="event-media__overlay">
            <div class="event-media__overlay-card">
              <strong>{{ previewRefreshLabel }}</strong>
              <p>{{ previewErrorMessage || '当前结果保持显示，新的结果图就绪后会自动替换。' }}</p>
            </div>
          </div>

          <div v-else-if="showDeferredPlaceholder" class="event-media__empty">
            <strong>结果图按需加载</strong>
            <p>滚动到当前事件卡片时会自动获取结果图，也可以立即手动加载。</p>
            <button class="ghost-button" type="button" @click="activatePreviewLoading">
              立即加载结果图
            </button>
          </div>

          <div v-else-if="!previewUrl" class="event-media__empty">
            <strong>{{ loading ? '正在生成结果图...' : '暂无检测结果图' }}</strong>
            <p>{{ previewErrorMessage || '请确认源文件路径存在，或为该事件补充截图地址。' }}</p>
          </div>
        </div>
        <p v-if="previewUrl && previewErrorMessage && !loading" class="error-text">
          {{ previewErrorMessage }}
        </p>
      </div>

      <div v-if="canLoadSourceMedia" class="event-media__panel">
        <p class="event-media__label">原始媒体</p>
        <div class="event-media__stage">
          <template v-if="mediaUrl">
            <video
              v-if="mediaKind === 'video'"
              class="event-media__video"
              :src="mediaUrl"
              controls
              preload="metadata"
            />
            <img
              v-else
              class="event-media__image"
              :src="mediaUrl"
              :alt="`${event.behavior_type} 原始画面`"
            />
          </template>
          <div v-else class="event-media__empty">
            <strong>{{ mediaLoading ? '正在加载原始媒体...' : '原始媒体按需加载' }}</strong>
            <p>{{ sourceErrorMessage || '为加快事件中心打开速度，原始图片或视频改为在需要时再加载。' }}</p>
            <button class="ghost-button" type="button" :disabled="mediaLoading" @click="loadSourceMedia()">
              {{ mediaLoading ? '加载中...' : '查看原始媒体' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <p class="event-media__caption">
      {{ mediaDescription }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue';

import { fetchEventPreview, fetchEventSourceMedia } from '@/api/media';
import type { BehaviorEventSummary } from '@/types/event';

const props = withDefaults(
  defineProps<{
    event: BehaviorEventSummary;
    lazy?: boolean;
  }>(),
  {
    lazy: false,
  },
);

const rootElement = ref<HTMLElement | null>(null);
const previewUrl = ref('');
const mediaUrl = ref('');
const loading = ref(false);
const mediaLoading = ref(false);
const previewErrorMessage = ref('');
const sourceErrorMessage = ref('');
const mediaKind = ref<'image' | 'video'>('image');
const sourceRequested = ref(false);
const previewRequested = ref(!props.lazy);
const previewEventId = ref<number | null>(null);

let previewRequestToken = 0;
let sourceRequestToken = 0;
let previewObserver: IntersectionObserver | null = null;

const canLoadSourceMedia = computed(() =>
  props.event.source_type === 'image' || props.event.source_type === 'video',
);
const showDeferredPlaceholder = computed(() =>
  props.lazy && !previewRequested.value && !previewUrl.value,
);
const previewRefreshLabel = computed(() =>
  previewEventId.value === props.event.id ? '正在刷新结果图...' : '正在加载最新结果图...',
);

const mediaTitle = computed(() => {
  if (props.event.source_type === 'video') {
    return '视频回看';
  }
  if (props.event.source_type === 'stream') {
    return '流媒体抓帧';
  }
  if (props.event.source_type === 'edge-report') {
    return '边缘上报画面';
  }
  return '图片回看';
});

const mediaDescription = computed(() => {
  if (props.event.source_type === 'video') {
    return '上方展示带检测结果的关键帧，下方可直接回看原始视频。';
  }
  if (props.event.source_type === 'stream') {
    return '实时视频流当前以抓帧形式展示检测结果，便于快速确认现场状态。';
  }
  if (props.event.source_type === 'edge-report') {
    return '边缘上报优先展示检测结果图，用于快速核对该次识别输出。';
  }
  return '上方展示带检测框的结果图，下方保留原始图片，便于对照核验。';
});

function revokePreviewUrl() {
  if (!previewUrl.value) {
    return;
  }

  URL.revokeObjectURL(previewUrl.value);
  previewUrl.value = '';
}

function revokeSourceUrl() {
  if (!mediaUrl.value) {
    return;
  }

  URL.revokeObjectURL(mediaUrl.value);
  mediaUrl.value = '';
}

function teardownPreviewObserver() {
  if (!previewObserver) {
    return;
  }

  previewObserver.disconnect();
  previewObserver = null;
}

function activatePreviewLoading() {
  previewRequested.value = true;
  teardownPreviewObserver();
  void loadMedia({ force: true });
}

async function loadMedia(options: { force?: boolean } = {}) {
  if ((loading.value && !options.force) || (props.lazy && !previewRequested.value)) {
    return;
  }

  loading.value = true;
  previewErrorMessage.value = '';
  const requestToken = ++previewRequestToken;
  const targetEventId = props.event.id;

  try {
    const previewBlob = await fetchEventPreview(targetEventId);
    const previewObjectUrl = URL.createObjectURL(previewBlob);
    if (requestToken !== previewRequestToken) {
      URL.revokeObjectURL(previewObjectUrl);
      return;
    }

    const previousPreviewUrl = previewUrl.value;
    previewUrl.value = previewObjectUrl;
    previewEventId.value = targetEventId;
    if (previousPreviewUrl) {
      URL.revokeObjectURL(previousPreviewUrl);
    }
  } catch (error) {
    if (requestToken !== previewRequestToken) {
      return;
    }

    previewErrorMessage.value = error instanceof Error ? error.message : '无法加载事件预览。';
  } finally {
    if (requestToken === previewRequestToken) {
      loading.value = false;
    }
  }
}

async function loadSourceMedia(force = false) {
  if (!canLoadSourceMedia.value || (mediaLoading.value && !force)) {
    return;
  }

  mediaLoading.value = true;
  sourceRequested.value = true;
  sourceErrorMessage.value = '';
  const requestToken = ++sourceRequestToken;

  try {
    const sourceBlob = await fetchEventSourceMedia(props.event.id);
    const sourceObjectUrl = URL.createObjectURL(sourceBlob);
    if (requestToken !== sourceRequestToken) {
      URL.revokeObjectURL(sourceObjectUrl);
      return;
    }

    const previousMediaUrl = mediaUrl.value;
    mediaUrl.value = sourceObjectUrl;
    mediaKind.value = props.event.source_type === 'video' ? 'video' : 'image';
    if (previousMediaUrl) {
      URL.revokeObjectURL(previousMediaUrl);
    }
  } catch (error) {
    if (requestToken !== sourceRequestToken) {
      return;
    }

    sourceErrorMessage.value = error instanceof Error ? error.message : '无法加载事件原始媒体。';
  } finally {
    if (requestToken === sourceRequestToken) {
      mediaLoading.value = false;
    }
  }
}

async function refreshMedia() {
  activatePreviewLoading();
  if (sourceRequested.value) {
    await loadSourceMedia(true);
  }
}

function preparePreviewLoading() {
  previewRequested.value = !props.lazy;
  if (previewRequested.value) {
    void loadMedia({ force: true });
    return;
  }

  void nextTick(() => {
    if (!rootElement.value || typeof IntersectionObserver === 'undefined') {
      activatePreviewLoading();
      return;
    }

    teardownPreviewObserver();
    previewObserver = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) {
          return;
        }

        activatePreviewLoading();
      },
      {
        threshold: 0.15,
      },
    );
    previewObserver.observe(rootElement.value);
  });
}

watch(
  () => props.event.id,
  () => {
    previewRequestToken += 1;
    sourceRequestToken += 1;
    loading.value = false;
    mediaLoading.value = false;
    previewErrorMessage.value = '';
    sourceErrorMessage.value = '';
    sourceRequested.value = false;
    revokeSourceUrl();
    preparePreviewLoading();
  },
  { immediate: true },
);

watch(
  () => props.lazy,
  () => {
    preparePreviewLoading();
  },
);

onBeforeUnmount(() => {
  previewRequestToken += 1;
  sourceRequestToken += 1;
  teardownPreviewObserver();
  revokePreviewUrl();
  revokeSourceUrl();
});
</script>
