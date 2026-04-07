<template>
  <section class="event-media">
    <header class="event-media__header">
      <div>
        <p class="event-media__eyebrow">事件可视化</p>
        <strong>{{ mediaTitle }}</strong>
      </div>
      <button class="ghost-button" type="button" @click="loadMedia">
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
          <div v-else class="event-media__empty">
            <strong>{{ loading ? '正在生成结果图...' : '暂无检测结果图' }}</strong>
            <p>{{ errorMessage || '请确认源文件路径存在，或为该事件补充截图地址。' }}</p>
          </div>
        </div>
      </div>

      <div v-if="mediaUrl" class="event-media__panel">
        <p class="event-media__label">原始媒体</p>
        <div class="event-media__stage">
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
        </div>
      </div>
    </div>

    <p class="event-media__caption">
      {{ mediaDescription }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';

import { fetchEventPreview, fetchEventSourceMedia } from '@/api/media';
import type { BehaviorEventSummary } from '@/types/event';

const props = defineProps<{
  event: BehaviorEventSummary;
}>();

const previewUrl = ref('');
const mediaUrl = ref('');
const loading = ref(false);
const errorMessage = ref('');
const mediaKind = ref<'image' | 'video'>('image');

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
    return '边缘上报优先展示检测结果图，用于快速核对该次识别输入。';
  }
  return '上方展示带检测框的结果图，下方保留原始图片，便于对照核验。';
});

function revokeUrls() {
  if (previewUrl.value) {
    URL.revokeObjectURL(previewUrl.value);
    previewUrl.value = '';
  }
  if (mediaUrl.value) {
    URL.revokeObjectURL(mediaUrl.value);
    mediaUrl.value = '';
  }
}

async function loadMedia() {
  loading.value = true;
  errorMessage.value = '';

  try {
    const previewBlob = await fetchEventPreview(props.event.id);
    const previewObjectUrl = URL.createObjectURL(previewBlob);
    if (previewUrl.value) {
      URL.revokeObjectURL(previewUrl.value);
    }
    previewUrl.value = previewObjectUrl;
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '无法加载事件预览。';
  }

  if (props.event.source_type === 'image' || props.event.source_type === 'video') {
    try {
      const sourceBlob = await fetchEventSourceMedia(props.event.id);
      const sourceObjectUrl = URL.createObjectURL(sourceBlob);
      if (mediaUrl.value) {
        URL.revokeObjectURL(mediaUrl.value);
      }
      mediaUrl.value = sourceObjectUrl;
      mediaKind.value = props.event.source_type === 'video' ? 'video' : 'image';
    } catch (error) {
      if (!errorMessage.value) {
        errorMessage.value = error instanceof Error ? error.message : '无法加载事件原始媒体。';
      }
    }
  } else {
    if (mediaUrl.value) {
      URL.revokeObjectURL(mediaUrl.value);
      mediaUrl.value = '';
    }
    mediaKind.value = 'image';
  }

  loading.value = false;
}

watch(
  () => props.event.id,
  () => {
    revokeUrls();
    void loadMedia();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  revokeUrls();
});
</script>
