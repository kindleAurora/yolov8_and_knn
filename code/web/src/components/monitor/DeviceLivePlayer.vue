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
      <span :class="['service-badge', `service-badge--${playbackTone}`]">
        {{ playbackLabel }}
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
      <div v-if="liveStreamUrl" class="monitor-preview__pan-layer" :style="panStyle">
        <video
          ref="videoElement"
          class="monitor-preview__video"
          :style="mediaStyle"
          autoplay
          muted
          playsinline
          @loadedmetadata="handleLoadedMetadata"
          @loadeddata="handleLoadedData"
          @playing="handlePlaying"
          @waiting="handleWaiting"
          @stalled="handleWaiting"
          @error="handleVideoError"
        />
      </div>

      <div v-if="showOverlay" class="monitor-preview__overlay">
        <strong>{{ overlayTitle }}</strong>
        <p>{{ overlayDescription }}</p>
        <div class="monitor-preview__actions">
          <button v-if="liveStreamUrl" class="ghost-button" type="button" @click="reloadStream">
            重新连接
          </button>
        </div>
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
      <button class="ghost-button" type="button" @click="reloadStream">
        重连直播
      </button>
    </footer>
  </article>
</template>

<script setup lang="ts">
import type Hls from 'hls.js';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { useMediaViewportInteraction } from '@/composables/useMediaViewportInteraction';
import type { DeviceSummary } from '@/types/device';
import { resolveDeviceBrowserStreamUrl } from '@/utils/liveStream';

const props = withDefaults(
  defineProps<{
    device: DeviceSummary;
    compact?: boolean;
    showControls?: boolean;
  }>(),
  {
    compact: false,
    showControls: false,
  },
);

const videoElement = ref<HTMLVideoElement | null>(null);
const stageElement = ref<HTMLElement | null>(null);
const loading = ref(false);
const liveError = ref('');
const zoom = ref(1);
const fitMode = ref<'contain' | 'cover'>('contain');
const intrinsicSize = ref({ width: 0, height: 0 });
const offsetX = ref(0);
const offsetY = ref(0);
const isDragging = ref(false);

let hls: Hls | null = null;

const liveStreamUrl = computed(() => resolveDeviceBrowserStreamUrl(props.device));
const statusLabel = computed(() => {
  if (props.device.status === 'online') {
    return '设备在线';
  }
  if (props.device.status === 'offline') {
    return '设备离线';
  }
  return '设备停用';
});
const playbackLabel = computed(() => {
  if (!liveStreamUrl.value) {
    return '未配置直播';
  }
  if (loading.value) {
    return '直播连接中';
  }
  if (liveError.value) {
    return '直播异常';
  }
  return '实时直播';
});
const playbackTone = computed(() => {
  if (!liveStreamUrl.value || loading.value) {
    return 'unknown';
  }
  if (liveError.value || props.device.status !== 'online') {
    return 'down';
  }
  return 'up';
});
const showOverlay = computed(() => !liveStreamUrl.value || loading.value || Boolean(liveError.value));
const overlayTitle = computed(() => {
  if (!liveStreamUrl.value) {
    return '暂无可播放的浏览器直播地址';
  }
  if (liveError.value) {
    return '实时直播暂时不可用';
  }
  return '正在连接实时直播...';
});
const overlayDescription = computed(() => {
  if (!liveStreamUrl.value) {
    return '请确认设备 stream_url 指向 MediaMTX 发布的 RTSP 地址，或在扩展配置 JSON 中设置 browser_stream_url / hls_url。';
  }
  if (liveError.value) {
    return liveError.value;
  }
  return '放大后可以直接在画面里拖动查看细节，适应画面和填满窗口也会立即生效。';
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

function destroyPlayer() {
  if (hls) {
    hls.destroy();
    hls = null;
  }

  const video = videoElement.value;
  if (!video) {
    return;
  }

  video.pause();
  video.removeAttribute('src');
  video.load();
}

async function playVideo(video: HTMLVideoElement) {
  try {
    await video.play();
  } catch {
    // Autoplay can be blocked until the browser has enough buffered data.
  }
}

function handleLoadedMetadata() {
  const video = videoElement.value;
  if (!video) {
    return;
  }

  intrinsicSize.value = {
    width: video.videoWidth,
    height: video.videoHeight,
  };
}

function handleLoadedData() {
  if (!liveError.value) {
    loading.value = true;
  }
}

function handlePlaying() {
  handleLoadedMetadata();
  loading.value = false;
  liveError.value = '';
}

function handleWaiting() {
  if (!liveError.value) {
    loading.value = true;
  }
}

function handleVideoError() {
  loading.value = false;
  if (!liveError.value) {
    liveError.value = '视频元素播放失败，请检查 HLS 服务是否已启动。';
  }
}

function attachNativeSource(video: HTMLVideoElement, streamUrl: string) {
  video.src = streamUrl;
  void playVideo(video);
}

async function attachHlsSource(video: HTMLVideoElement, streamUrl: string) {
  const HlsModule = (await import('hls.js/dist/hls.mjs')).default;

  hls = new HlsModule({
    lowLatencyMode: true,
    backBufferLength: 90,
  });

  hls.on(HlsModule.Events.MEDIA_ATTACHED, () => {
    hls?.loadSource(streamUrl);
  });

  hls.on(HlsModule.Events.MANIFEST_PARSED, () => {
    loading.value = false;
    liveError.value = '';
    void playVideo(video);
  });

  hls.on(HlsModule.Events.ERROR, (_event, data) => {
    if (!data.fatal) {
      return;
    }

    if (data.type === HlsModule.ErrorTypes.NETWORK_ERROR) {
      loading.value = true;
      hls?.startLoad();
      return;
    }

    if (data.type === HlsModule.ErrorTypes.MEDIA_ERROR) {
      hls?.recoverMediaError();
      return;
    }

    loading.value = false;
    liveError.value = 'HLS 播放器无法恢复，请检查 MediaMTX 是否正在输出该路流。';
  });

  hls.attachMedia(video);
}

async function initializePlayer() {
  destroyPlayer();
  liveError.value = '';

  const video = videoElement.value;
  const streamUrl = liveStreamUrl.value;

  if (!video || !streamUrl) {
    loading.value = false;
    return;
  }

  loading.value = true;
  video.muted = true;
  video.autoplay = true;
  video.playsInline = true;

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    attachNativeSource(video, streamUrl);
    return;
  }

  const HlsModule = (await import('hls.js/dist/hls.mjs')).default;
  if (HlsModule.isSupported()) {
    await attachHlsSource(video, streamUrl);
    return;
  }

  loading.value = false;
  liveError.value = '当前浏览器不支持 HLS 播放，请使用最新版 Chrome 或 Edge。';
}

function reloadStream() {
  resetViewport();
  void initializePlayer();
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
  () => [props.device.id, props.device.stream_url, props.device.updated_at],
  () => {
    zoom.value = 1;
    fitMode.value = 'contain';
    intrinsicSize.value = { width: 0, height: 0 };
    resetViewport();
    void initializePlayer();
  },
);

onMounted(() => {
  void initializePlayer();
});

onBeforeUnmount(() => {
  destroyPlayer();
});
</script>
