<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">语义区域</p>
        <h2>区域管理</h2>
        <p class="page-header__text">
          已登录用户可在可视化画布中为当前农场设备绘制、编辑和删除多边形区域。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <div class="content-grid zone-content-grid">
      <article class="panel panel--workspace">
        <header class="panel__header panel__header--stacked">
          <div>
            <h3>可视化绘制面板</h3>
            <p class="panel__description">
              先选择设备，再点击画布添加顶点；拖动画布中的圆点可微调位置。
            </p>
          </div>
          <label class="field zone-device-field">
            <span>当前设备</span>
            <select v-model="form.deviceId">
              <option value="" disabled>请选择设备</option>
              <option v-for="device in devices" :key="device.id" :value="String(device.id)">
                {{ device.name }}（{{ device.code }}）
              </option>
            </select>
          </label>
        </header>

        <div class="zone-toolbar__meta">
          <strong>{{ currentDeviceTitle }}</strong>
          <span>{{ currentDeviceSubtitle }}</span>
        </div>

        <div class="zone-canvas-shell">
          <div class="zone-stage">
            <div class="zone-stage__media">
              <video
                v-if="stageLiveStreamUrl"
                ref="stageVideoRef"
                :aria-label="stagePreviewAlt"
                class="zone-stage__video"
                autoplay
                muted
                playsinline
                @playing="handleStagePlaying"
                @waiting="handleStageWaiting"
                @stalled="handleStageWaiting"
                @error="handleStageVideoError"
              />
              <div v-else class="zone-stage__placeholder">
                <strong>{{ stagePreviewTitle }}</strong>
                <p>{{ stagePreviewMessage }}</p>
              </div>
              <div
                v-if="stageLiveStreamUrl && (stagePreviewLoading || stagePreviewError)"
                class="zone-stage__overlay"
              >
                <strong>{{ stagePreviewTitle }}</strong>
                <p>{{ stagePreviewMessage }}</p>
              </div>
            </div>

            <svg
              ref="stageRef"
              class="zone-canvas zone-canvas--overlay"
              viewBox="0 0 100 56.25"
              @pointerdown="handleCanvasPointerDown"
            >
              <defs>
                <pattern id="zone-grid-major" width="12.5" height="12.5" patternUnits="userSpaceOnUse">
                  <path
                    d="M 12.5 0 L 0 0 0 12.5"
                    fill="none"
                    stroke="rgba(24, 33, 41, 0.2)"
                    stroke-width="0.28"
                  />
                </pattern>
                <pattern id="zone-grid-minor" width="6.25" height="6.25" patternUnits="userSpaceOnUse">
                  <path
                    d="M 6.25 0 L 0 0 0 6.25"
                    fill="none"
                    stroke="rgba(24, 33, 41, 0.1)"
                    stroke-width="0.18"
                  />
                </pattern>
              </defs>

              <rect x="0" y="0" width="100" height="56.25" :fill="stageCanvasFill" />
              <rect x="0" y="0" width="100" height="56.25" fill="url(#zone-grid-minor)" />
              <rect x="0" y="0" width="100" height="56.25" fill="url(#zone-grid-major)" />

              <g v-for="zone in backgroundZones" :key="zone.id" class="zone-saved-layer">
                <polygon :points="toSvgPoints(zone.points)" class="zone-polygon zone-polygon--saved" />
                <text
                  class="zone-label"
                  :x="getZoneLabelPosition(zone).x"
                  :y="getZoneLabelPosition(zone).y"
                >
                  {{ zone.name }}
                </text>
              </g>

              <g v-if="draftPoints.length > 0">
                <polygon
                  v-if="draftPoints.length >= 3"
                  :points="toSvgPoints(draftPoints)"
                  class="zone-polygon zone-polygon--draft"
                />
                <polyline :points="toSvgPoints(draftPoints)" class="zone-polyline zone-polyline--draft" />

                <g v-for="(point, index) in draftPoints" :key="`draft-${index}`">
                  <circle
                    class="zone-point"
                    :cx="toSvgX(point.x)"
                    :cy="toSvgY(point.y)"
                    r="1.05"
                    @pointerdown.stop="startDraggingPoint(index, $event)"
                  />
                  <text
                    class="zone-point-label"
                    :x="toSvgX(point.x)"
                    :y="toSvgY(point.y) - 1.9"
                  >
                    {{ index + 1 }}
                  </text>
                </g>
              </g>

              <g v-if="!form.deviceId">
                <text class="zone-empty-text" x="50" y="28.125">请先选择设备，再开始绘制区域</text>
              </g>
              <g v-else-if="draftPoints.length === 0">
                <text class="zone-empty-text" x="50" y="28.125">点击画布即可添加第一个顶点</text>
              </g>
            </svg>
          </div>
        </div>

        <div class="zone-actions">
          <button class="ghost-button" type="button" :disabled="!currentDevice" @click="reloadStageStream">
            重连实时画面
          </button>
          <button class="ghost-button" type="button" :disabled="draftPoints.length === 0" @click="undoLastPoint">
            撤销最后一点
          </button>
          <button class="ghost-button" type="button" :disabled="draftPoints.length === 0" @click="clearDraftPoints">
            清空画布
          </button>
        </div>

        <p class="summary">
          当前设备已有 {{ displayedZones.length }} 个区域，当前草稿共有 {{ draftPoints.length }} 个点。
          保存前至少需要 3 个点。
        </p>

        <div class="stack-list">
          <article v-for="zone in displayedZones" :key="zone.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ zone.name }}</strong>
                <p>{{ formatZoneType(zone.zone_type) }} / {{ getDeviceName(zone.device_id) }}</p>
              </div>
              <span :class="['service-badge', `service-badge--${zone.is_enabled ? 'up' : 'down'}`]">
                {{ zone.is_enabled ? '已启用' : '已停用' }}
              </span>
            </div>

            <dl class="entity-grid">
              <div>
                <dt>形状</dt>
                <dd>多边形</dd>
              </div>
              <div>
                <dt>坐标点数</dt>
                <dd>{{ zone.points.length }}</dd>
              </div>
              <div>
                <dt>所属设备</dt>
                <dd>{{ getDeviceName(zone.device_id) }}</dd>
              </div>
              <div>
                <dt>更新时间</dt>
                <dd>{{ formatDate(zone.updated_at) }}</dd>
              </div>
            </dl>

            <div class="entity-actions">
              <button class="ghost-button" type="button" @click="startEdit(zone)">编辑</button>
              <button class="ghost-button ghost-button--danger" type="button" @click="removeZone(zone.id)">
                删除
              </button>
            </div>
          </article>

          <p v-if="displayedZones.length === 0" class="entity-note">
            当前设备还没有配置区域，可以直接在上方画布中开始绘制。
          </p>
        </div>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>{{ editingId ? '编辑区域' : '新增区域' }}</h3>
          <button class="ghost-button" type="button" @click="resetForm">重置表单</button>
        </header>

        <form class="form-grid" @submit.prevent="submitForm">
          <label class="field">
            <span>区域名称</span>
            <input v-model.trim="form.name" type="text" placeholder="例如：饮水区 1 号" />
          </label>

          <label class="field">
            <span>区域类型</span>
            <select v-model="zoneTypeMode">
              <option v-for="option in zoneTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>

          <label v-if="zoneTypeMode === 'custom'" class="field">
            <span>自定义区域类型</span>
            <input v-model.trim="customZoneType" type="text" placeholder="请输入自定义区域类型" />
          </label>

          <label class="field">
            <span>形状类型</span>
            <input type="text" value="多边形" disabled />
          </label>

          <label class="field">
            <span>启用状态</span>
            <select v-model="enabledValue">
              <option value="true">启用</option>
              <option value="false">停用</option>
            </select>
          </label>

          <div class="field field--full">
            <span>草稿点位</span>
            <div v-if="draftPoints.length === 0" class="entity-note">
              点击左侧画布开始绘制，或者编辑已有区域加载点位。
            </div>
            <div v-else class="zone-point-list">
              <div v-for="(point, index) in draftPoints" :key="`point-${index}`" class="zone-point-row">
                <strong>点 {{ index + 1 }}</strong>
                <label>
                  <span>X（%）</span>
                  <input
                    :value="formatPointPercent(point.x)"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    @input="updatePointInput(index, 'x', $event)"
                  />
                </label>
                <label>
                  <span>Y（%）</span>
                  <input
                    :value="formatPointPercent(point.y)"
                    type="number"
                    min="0"
                    max="100"
                    step="0.1"
                    @input="updatePointInput(index, 'y', $event)"
                  />
                </label>
                <button class="ghost-button ghost-button--danger" type="button" @click="removePoint(index)">
                  删除
                </button>
              </div>
            </div>
          </div>

          <button
            class="primary-button"
            type="submit"
            :disabled="submitting || !form.deviceId || draftPoints.length < 3"
          >
            {{ submitting ? '保存中...' : editingId ? '保存区域' : '创建区域' }}
          </button>
        </form>

        <p v-if="submitMessage" class="success-text">{{ submitMessage }}</p>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
        <p v-if="loadError" class="error-text">{{ loadError }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import type Hls from 'hls.js';
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';

import { listDevices } from '@/api/devices';
import { createZone, deleteZone, listZones, updateZone } from '@/api/zones';
import type { DeviceSummary } from '@/types/device';
import type { ZonePayload, ZonePoint, ZoneSummary } from '@/types/zone';
import { resolveDeviceBrowserStreamUrl } from '@/utils/liveStream';

interface ZoneFormState {
  deviceId: string;
  name: string;
}

type ZoneTypeMode = 'water' | 'feeding' | 'rest' | 'custom';

const STAGE_WIDTH = 100;
const STAGE_HEIGHT = 56.25;

const zoneTypeOptions: Array<{ label: string; value: ZoneTypeMode }> = [
  { label: '饮水区', value: 'water' },
  { label: '采食区', value: 'feeding' },
  { label: '休息区', value: 'rest' },
  { label: '自定义区域', value: 'custom' },
];

const devices = ref<DeviceSummary[]>([]);
const zones = ref<ZoneSummary[]>([]);
const loadError = ref('');
const submitError = ref('');
const submitMessage = ref('');
const submitting = ref(false);
const editingId = ref<number | null>(null);
const enabledValue = ref('true');
const zoneTypeMode = ref<ZoneTypeMode>('water');
const customZoneType = ref('');
const draftPoints = ref<ZonePoint[]>([]);
const draggingPointIndex = ref<number | null>(null);
const stageRef = ref<SVGSVGElement | null>(null);
const stageVideoRef = ref<HTMLVideoElement | null>(null);
const stagePreviewLoading = ref(false);
const stagePreviewError = ref('');

const form = reactive<ZoneFormState>(createEmptyForm());
let stageHls: Hls | null = null;

const currentDevice = computed(() =>
  devices.value.find((device) => String(device.id) === form.deviceId) ?? null,
);
const displayedZones = computed(() => {
  const deviceId = Number(form.deviceId);
  if (!deviceId) {
    return zones.value;
  }
  return zones.value.filter((zone) => zone.device_id === deviceId);
});
const backgroundZones = computed(() =>
  displayedZones.value.filter((zone) => zone.id !== editingId.value),
);
const stageLiveStreamUrl = computed(() =>
  currentDevice.value ? resolveDeviceBrowserStreamUrl(currentDevice.value) : null,
);
const currentDeviceTitle = computed(() =>
  currentDevice.value ? `${currentDevice.value.name}（${currentDevice.value.code}）` : '尚未选择设备',
);
const currentDeviceSubtitle = computed(() => {
  if (!currentDevice.value) {
    return '请选择一个设备后，再开始绘制或编辑区域。';
  }

  return currentDevice.value.install_location
    ? `安装位置：${currentDevice.value.install_location}`
    : '当前设备尚未填写安装位置。';
});
const stageCanvasFill = computed(() =>
  stageLiveStreamUrl.value ? 'rgba(7, 17, 22, 0.16)' : 'rgba(255, 255, 255, 0.9)',
);
const stagePreviewAlt = computed(() =>
  currentDevice.value ? `${currentDevice.value.name} 实时监控画面` : '设备实时监控画面',
);
const stagePreviewTitle = computed(() => {
  if (!currentDevice.value) {
    return '请先选择设备';
  }
  if (stagePreviewLoading.value) {
    return '正在连接实时画面...';
  }
  if (stagePreviewError.value) {
    return '实时画面暂时不可用';
  }
  return '暂无可用画面';
});
const stagePreviewMessage = computed(() => {
  if (!currentDevice.value) {
    return '选择设备后，这里会显示实时监控画面，便于在真实视角上绘制区域。';
  }
  if (!stageLiveStreamUrl.value) {
    return '当前设备还没有可供浏览器播放的直播地址，请先检查 stream_url 或补充 hls_url。';
  }
  if (stagePreviewError.value) {
    return stagePreviewError.value;
  }
  return '实时画面已接入，绘制区域时会持续跟随视频流更新。';
});

function createEmptyForm(): ZoneFormState {
  return {
    deviceId: '',
    name: '',
  };
}

function clonePoints(points: ZonePoint[]) {
  return points.map((point) => ({ ...point }));
}

function clamp(value: number) {
  return Math.min(1, Math.max(0, value));
}

function roundPointValue(value: number) {
  return Number(value.toFixed(4));
}

function toSvgX(value: number) {
  return Number((value * STAGE_WIDTH).toFixed(2));
}

function toSvgY(value: number) {
  return Number((value * STAGE_HEIGHT).toFixed(2));
}

function toSvgPoints(points: ZonePoint[]) {
  return points.map((point) => `${toSvgX(point.x)},${toSvgY(point.y)}`).join(' ');
}

function getZoneLabelPosition(zone: ZoneSummary) {
  const total = zone.points.reduce(
    (accumulator, point) => ({
      x: accumulator.x + toSvgX(point.x),
      y: accumulator.y + toSvgY(point.y),
    }),
    { x: 0, y: 0 },
  );

  return {
    x: total.x / zone.points.length,
    y: total.y / zone.points.length,
  };
}

function formatZoneType(zoneType: string) {
  if (zoneType === 'water') {
    return '饮水区';
  }
  if (zoneType === 'feeding') {
    return '采食区';
  }
  if (zoneType === 'rest') {
    return '休息区';
  }
  return zoneType;
}

function syncZoneType(zoneType: string) {
  if (zoneType === 'water' || zoneType === 'feeding' || zoneType === 'rest') {
    zoneTypeMode.value = zoneType;
    customZoneType.value = '';
    return;
  }

  zoneTypeMode.value = 'custom';
  customZoneType.value = zoneType;
}

function resolveZoneType() {
  if (zoneTypeMode.value === 'custom') {
    const value = customZoneType.value.trim();
    if (!value) {
      throw new Error('请输入自定义区域类型。');
    }
    return value;
  }

  return zoneTypeMode.value;
}

function resetForm() {
  const currentDeviceId =
    form.deviceId || (devices.value.length > 0 ? String(devices.value[0].id) : '');

  editingId.value = null;
  enabledValue.value = 'true';
  syncZoneType('water');
  draftPoints.value = [];
  submitError.value = '';
  submitMessage.value = '';
  Object.assign(form, {
    ...createEmptyForm(),
    deviceId: currentDeviceId,
  });
  void initializeStagePlayer();
}

function startEdit(zone: ZoneSummary) {
  editingId.value = zone.id;
  enabledValue.value = String(zone.is_enabled);
  syncZoneType(zone.zone_type);
  draftPoints.value = clonePoints(zone.points);
  Object.assign(form, {
    deviceId: String(zone.device_id),
    name: zone.name,
  });
  submitError.value = '';
  submitMessage.value = '';
  void initializeStagePlayer();
}

async function loadDevicesAndMaybeDefault() {
  devices.value = await listDevices();

  if (devices.value.length === 0) {
    form.deviceId = '';
    return;
  }

  const hasCurrentDevice = devices.value.some((device) => String(device.id) === form.deviceId);
  if (!hasCurrentDevice) {
    form.deviceId = String(devices.value[0].id);
  }
}

async function loadZones() {
  zones.value = await listZones();
}

async function refreshAll() {
  loadError.value = '';
  try {
    await Promise.all([loadDevicesAndMaybeDefault(), loadZones()]);
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载区域数据。';
  }
}

function getDeviceName(deviceId: number) {
  const device = devices.value.find((item) => item.id === deviceId);
  return device ? `${device.name}（${device.code}）` : `设备 #${deviceId}`;
}

function formatDate(value: string) {
  return new Date(value).toLocaleString();
}

function destroyStagePlayer() {
  if (stageHls) {
    stageHls.destroy();
    stageHls = null;
  }

  const video = stageVideoRef.value;
  if (!video) {
    return;
  }

  video.pause();
  video.removeAttribute('src');
  video.load();
}

async function playStageVideo(video: HTMLVideoElement) {
  try {
    await video.play();
  } catch {
    // Wait until the browser buffers enough data for autoplay.
  }
}

function handleStagePlaying() {
  stagePreviewLoading.value = false;
  stagePreviewError.value = '';
}

function handleStageWaiting() {
  if (!stagePreviewError.value) {
    stagePreviewLoading.value = true;
  }
}

function handleStageVideoError() {
  stagePreviewLoading.value = false;
  if (!stagePreviewError.value) {
    stagePreviewError.value = '浏览器无法播放当前视频流，请检查 HLS 输出是否可用。';
  }
}

function attachNativeStageSource(video: HTMLVideoElement, streamUrl: string) {
  video.src = streamUrl;
  void playStageVideo(video);
}

async function attachHlsStageSource(video: HTMLVideoElement, streamUrl: string) {
  const HlsModule = (await import('hls.js/dist/hls.mjs')).default;

  stageHls = new HlsModule({
    lowLatencyMode: true,
    backBufferLength: 90,
  });

  stageHls.on(HlsModule.Events.MEDIA_ATTACHED, () => {
    stageHls?.loadSource(streamUrl);
  });

  stageHls.on(HlsModule.Events.MANIFEST_PARSED, () => {
    stagePreviewLoading.value = false;
    stagePreviewError.value = '';
    void playStageVideo(video);
  });

  stageHls.on(HlsModule.Events.ERROR, (_event, data) => {
    if (!data.fatal) {
      return;
    }

    if (data.type === HlsModule.ErrorTypes.NETWORK_ERROR) {
      stagePreviewLoading.value = true;
      stageHls?.startLoad();
      return;
    }

    if (data.type === HlsModule.ErrorTypes.MEDIA_ERROR) {
      stageHls?.recoverMediaError();
      return;
    }

    stagePreviewLoading.value = false;
    stagePreviewError.value = 'HLS 播放器无法恢复，请检查 MediaMTX 是否正在输出该路直播流。';
  });

  stageHls.attachMedia(video);
}

async function initializeStagePlayer() {
  destroyStagePlayer();

  const video = stageVideoRef.value;
  const streamUrl = stageLiveStreamUrl.value;

  if (!currentDevice.value) {
    stagePreviewLoading.value = false;
    stagePreviewError.value = '';
    return;
  }

  if (!video || !streamUrl) {
    stagePreviewLoading.value = false;
    stagePreviewError.value = currentDevice.value.stream_url
      ? '当前设备没有可供浏览器播放的直播地址，请在设备配置中补充 hls_url 或 browser_stream_url。'
      : '当前设备未配置视频流地址，无法播放实时画面。';
    return;
  }

  stagePreviewLoading.value = true;
  stagePreviewError.value = '';
  video.muted = true;
  video.autoplay = true;
  video.playsInline = true;

  if (video.canPlayType('application/vnd.apple.mpegurl')) {
    attachNativeStageSource(video, streamUrl);
    return;
  }

  const HlsModule = (await import('hls.js/dist/hls.mjs')).default;
  if (HlsModule.isSupported()) {
    await attachHlsStageSource(video, streamUrl);
    return;
  }

  stagePreviewLoading.value = false;
  stagePreviewError.value = '当前浏览器不支持 HLS 播放，请使用最新版 Chrome 或 Edge。';
}

function reloadStageStream() {
  void initializeStagePlayer();
}

function clientToPoint(clientX: number, clientY: number) {
  if (!stageRef.value) {
    return null;
  }

  const rect = stageRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) {
    return null;
  }

  return {
    x: roundPointValue(clamp((clientX - rect.left) / rect.width)),
    y: roundPointValue(clamp((clientY - rect.top) / rect.height)),
  };
}

function handleCanvasPointerDown(event: PointerEvent) {
  if (!form.deviceId) {
    submitError.value = '请先选择设备，再开始绘制区域。';
    return;
  }

  const point = clientToPoint(event.clientX, event.clientY);
  if (!point) {
    return;
  }

  draftPoints.value = [...draftPoints.value, point];
  submitError.value = '';
  submitMessage.value = '';
}

function startDraggingPoint(index: number, event: PointerEvent) {
  draggingPointIndex.value = index;
  updatePointFromClient(index, event.clientX, event.clientY);
}

function updatePointFromClient(index: number, clientX: number, clientY: number) {
  const point = clientToPoint(clientX, clientY);
  if (!point) {
    return;
  }

  draftPoints.value = draftPoints.value.map((item, pointIndex) =>
    pointIndex === index ? point : item,
  );
}

function handleGlobalPointerMove(event: PointerEvent) {
  if (draggingPointIndex.value === null) {
    return;
  }

  updatePointFromClient(draggingPointIndex.value, event.clientX, event.clientY);
}

function handleGlobalPointerUp() {
  draggingPointIndex.value = null;
}

function undoLastPoint() {
  draftPoints.value = draftPoints.value.slice(0, -1);
}

function clearDraftPoints() {
  draftPoints.value = [];
}

function removePoint(index: number) {
  draftPoints.value = draftPoints.value.filter((_, pointIndex) => pointIndex !== index);
}

function formatPointPercent(value: number) {
  return (value * 100).toFixed(1);
}

function updatePointInput(
  index: number,
  axis: 'x' | 'y',
  event: Event,
) {
  const input = event.target as HTMLInputElement;
  const rawValue = Number(input.value);

  if (Number.isNaN(rawValue)) {
    return;
  }

  const normalizedValue = roundPointValue(clamp(rawValue / 100));
  draftPoints.value = draftPoints.value.map((point, pointIndex) =>
    pointIndex === index ? { ...point, [axis]: normalizedValue } : point,
  );
}

function buildPayload(): ZonePayload {
  const deviceId = Number(form.deviceId);
  if (!deviceId) {
    throw new Error('请选择设备。');
  }

  if (!form.name.trim()) {
    throw new Error('请输入区域名称。');
  }

  if (draftPoints.value.length < 3) {
    throw new Error('请至少绘制三个点后再保存区域。');
  }

  return {
    device_id: deviceId,
    name: form.name.trim(),
    zone_type: resolveZoneType(),
    shape_type: 'polygon',
    points: clonePoints(draftPoints.value),
    is_enabled: enabledValue.value === 'true',
  };
}

async function submitForm() {
  submitting.value = true;
  submitError.value = '';
  submitMessage.value = '';

  try {
    const payload = buildPayload();
    if (editingId.value) {
      await updateZone(editingId.value, payload);
      submitMessage.value = '区域更新成功。';
    } else {
      await createZone(payload);
      submitMessage.value = '区域创建成功。';
    }

    await loadZones();
    resetForm();
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法保存区域。';
  } finally {
    submitting.value = false;
  }
}

async function removeZone(zoneId: number) {
  if (!window.confirm('确认删除该区域吗？')) {
    return;
  }

  submitError.value = '';
  submitMessage.value = '';
  try {
    await deleteZone(zoneId);
    submitMessage.value = '区域删除成功。';
    if (editingId.value === zoneId) {
      resetForm();
    }
    await loadZones();
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法删除区域。';
  }
}

watch(
  () => [currentDevice.value?.id, currentDevice.value?.stream_url, currentDevice.value?.updated_at],
  () => {
    void initializeStagePlayer();
  },
  { immediate: true },
);

onMounted(async () => {
  window.addEventListener('pointermove', handleGlobalPointerMove);
  window.addEventListener('pointerup', handleGlobalPointerUp);

  await refreshAll();
  resetForm();
  void initializeStagePlayer();
});

onBeforeUnmount(() => {
  window.removeEventListener('pointermove', handleGlobalPointerMove);
  window.removeEventListener('pointerup', handleGlobalPointerUp);
  destroyStagePlayer();
});
</script>
