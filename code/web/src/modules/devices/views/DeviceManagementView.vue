<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">设备资产管理</p>
        <h2>设备管理</h2>
        <p class="page-header__text">
          统一维护采集设备的基础档案、运行状态、视频流地址与扩展配置。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="loadDevices">刷新列表</button>
    </header>

    <div class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>设备清单</h3>
          <span class="panel__badge">{{ devices.length }} 条</span>
        </header>

        <p v-if="loadError" class="error-text">{{ loadError }}</p>

        <div class="stack-list">
          <article v-for="device in devices" :key="device.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ device.name }}</strong>
                <p>{{ device.code }} / {{ formatDeviceType(device.device_type) }}</p>
              </div>
              <span :class="['service-badge', `service-badge--${device.status === 'online' ? 'up' : 'down'}`]">
                {{ formatDeviceStatus(device.status) }}
              </span>
            </div>

            <dl class="entity-grid">
              <div>
                <dt>视频流</dt>
                <dd>{{ device.stream_url }}</dd>
              </div>
              <div>
                <dt>安装位置</dt>
                <dd>{{ device.install_location || '未设置' }}</dd>
              </div>
              <div>
                <dt>是否启用</dt>
                <dd>{{ device.is_enabled ? '是' : '否' }}</dd>
              </div>
              <div>
                <dt>区域数量</dt>
                <dd>{{ device.zone_count }}</dd>
              </div>
            </dl>

            <div class="entity-actions">
              <button
                v-if="authStore.isAdmin"
                class="ghost-button"
                type="button"
                @click="startEdit(device)"
              >
                编辑
              </button>
              <button
                v-if="authStore.isAdmin"
                class="ghost-button"
                type="button"
                @click="toggleDevice(device)"
              >
                {{ device.is_enabled ? '停用' : '启用' }}
              </button>
              <button
                v-if="authStore.isAdmin"
                class="ghost-button ghost-button--danger"
                type="button"
                @click="removeDevice(device)"
              >
                删除
              </button>
              <span v-if="!authStore.isAdmin" class="entity-note">普通用户模式：设备仅可查看</span>
            </div>
          </article>
        </div>
      </article>

      <article v-if="authStore.isAdmin" class="panel">
        <header class="panel__header">
          <h3>{{ editingId ? '编辑设备' : '新增设备' }}</h3>
          <button class="ghost-button" type="button" @click="resetForm">重置表单</button>
        </header>
        <p class="entity-note">设备编号、设备名称和视频流地址为必填项，扩展配置需为合法 JSON 对象。</p>

        <form class="form-grid" @submit.prevent="submitForm">
          <label class="field">
            <span>设备编号</span>
            <input
              v-model.trim="form.code"
              type="text"
              placeholder="例如：CAM-003"
              minlength="2"
              maxlength="64"
              required
            />
          </label>
          <label class="field">
            <span>设备名称</span>
            <input
              v-model.trim="form.name"
              type="text"
              placeholder="例如：北侧牛舍摄像头"
              minlength="2"
              maxlength="120"
              required
            />
          </label>
          <label class="field">
            <span>设备类型</span>
            <select v-model="deviceTypeMode">
              <option v-for="option in deviceTypeOptions" :key="option.value" :value="option.value">
                {{ option.label }}
              </option>
            </select>
          </label>
          <label v-if="deviceTypeMode === 'custom'" class="field">
            <span>自定义设备类型</span>
            <input
              v-model.trim="customDeviceType"
              type="text"
              placeholder="请输入自定义设备类型"
              maxlength="32"
              required
            />
          </label>
          <label class="field">
            <span>运行状态</span>
            <select v-model="form.status">
              <option value="online">在线</option>
              <option value="offline">离线</option>
              <option value="disabled">停用</option>
            </select>
          </label>
          <label class="field field--full">
            <span>视频流地址</span>
            <input
              v-model.trim="form.stream_url"
              type="text"
              placeholder="例如：rtsp://demo.local/cam-003"
              minlength="4"
              required
            />
          </label>
          <label class="field">
            <span>安装位置</span>
            <input
              v-model.trim="form.install_location"
              type="text"
              placeholder="例如：北侧牛舍"
              maxlength="255"
            />
          </label>
          <label class="field">
            <span>启用开关</span>
            <select v-model="enabledValue">
              <option value="true">启用</option>
              <option value="false">停用</option>
            </select>
          </label>
          <label class="field field--full">
            <span>扩展配置 JSON</span>
            <textarea
              v-model="form.configJson"
              rows="6"
              placeholder='{"分辨率":"1080p","模型绑定":"默认流程"}'
            />
          </label>

          <button class="primary-button" type="submit" :disabled="submitting">
            {{ submitting ? '保存中...' : editingId ? '保存设备' : '创建设备' }}
          </button>
        </form>

        <p v-if="submitMessage" class="success-text">{{ submitMessage }}</p>
        <p v-if="submitError" class="error-text">{{ submitError }}</p>
      </article>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue';

import { createDevice, deleteDevice, listDevices, updateDevice, updateDeviceStatus } from '@/api/devices';
import { useAuthStore } from '@/stores/auth';
import type { DevicePayload, DeviceSummary } from '@/types/device';

interface DeviceFormState {
  code: string;
  name: string;
  stream_url: string;
  install_location: string;
  status: string;
  configJson: string;
}

type DeviceTypeMode = 'camera' | 'edge-agent' | 'drone' | 'custom';

const authStore = useAuthStore();

const devices = ref<DeviceSummary[]>([]);
const loadError = ref('');
const submitError = ref('');
const submitMessage = ref('');
const submitting = ref(false);
const editingId = ref<number | null>(null);
const enabledValue = ref('true');
const deviceTypeMode = ref<DeviceTypeMode>('camera');
const customDeviceType = ref('');

const deviceTypeOptions: Array<{ label: string; value: DeviceTypeMode }> = [
  { label: '摄像头', value: 'camera' },
  { label: '边缘设备', value: 'edge-agent' },
  { label: '无人机', value: 'drone' },
  { label: '自定义类型', value: 'custom' },
];

const DEVICE_CODE_MIN_LENGTH = 2;
const DEVICE_CODE_MAX_LENGTH = 64;
const DEVICE_NAME_MIN_LENGTH = 2;
const DEVICE_NAME_MAX_LENGTH = 120;
const DEVICE_TYPE_MAX_LENGTH = 32;
const INSTALL_LOCATION_MAX_LENGTH = 255;
const STREAM_URL_MIN_LENGTH = 4;

const form = reactive<DeviceFormState>(createEmptyForm());

function createEmptyForm(): DeviceFormState {
  return {
    code: '',
    name: '',
    stream_url: '',
    install_location: '',
    status: 'online',
    configJson: '{\n  "分辨率": "1080p"\n}',
  };
}

function formatDeviceStatus(status: string) {
  if (status === 'online') {
    return '在线';
  }
  if (status === 'offline') {
    return '离线';
  }
  if (status === 'disabled') {
    return '停用';
  }
  return status;
}

function formatDeviceType(deviceType: string) {
  if (deviceType === 'camera') {
    return '摄像头';
  }
  if (deviceType === 'edge-agent') {
    return '边缘设备';
  }
  if (deviceType === 'drone') {
    return '无人机';
  }
  return deviceType;
}

function syncDeviceType(deviceType: string) {
  if (deviceType === 'camera' || deviceType === 'edge-agent' || deviceType === 'drone') {
    deviceTypeMode.value = deviceType;
    customDeviceType.value = '';
    return;
  }

  deviceTypeMode.value = 'custom';
  customDeviceType.value = deviceType;
}

function resolveDeviceType() {
  if (deviceTypeMode.value === 'custom') {
    const value = customDeviceType.value.trim();
    if (!value) {
      throw new Error('请输入自定义设备类型。');
    }
    if (value.length > DEVICE_TYPE_MAX_LENGTH) {
      throw new Error(`自定义设备类型不能超过 ${DEVICE_TYPE_MAX_LENGTH} 个字符。`);
    }
    return value;
  }

  return deviceTypeMode.value;
}

function normalizeConfig(): Record<string, unknown> {
  let parsed: unknown;

  try {
    parsed = JSON.parse(form.configJson);
  } catch {
    throw new Error('扩展配置 JSON 格式不正确，请检查引号、逗号和括号。');
  }

  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('扩展配置 JSON 必须是对象。');
  }
  return parsed as Record<string, unknown>;
}

function validateTextField(
  value: string,
  label: string,
  minLength: number,
  maxLength?: number,
) {
  const normalizedValue = value.trim();
  if (normalizedValue.length < minLength) {
    throw new Error(`${label}至少需要 ${minLength} 个字符。`);
  }
  if (maxLength && normalizedValue.length > maxLength) {
    throw new Error(`${label}不能超过 ${maxLength} 个字符。`);
  }
  return normalizedValue;
}

function buildPayload(): DevicePayload {
  const code = validateTextField(form.code, '设备编号', DEVICE_CODE_MIN_LENGTH, DEVICE_CODE_MAX_LENGTH);
  const name = validateTextField(form.name, '设备名称', DEVICE_NAME_MIN_LENGTH, DEVICE_NAME_MAX_LENGTH);
  const streamUrl = validateTextField(form.stream_url, '视频流地址', STREAM_URL_MIN_LENGTH);
  const installLocation = form.install_location.trim();

  if (installLocation.length > INSTALL_LOCATION_MAX_LENGTH) {
    throw new Error(`安装位置不能超过 ${INSTALL_LOCATION_MAX_LENGTH} 个字符。`);
  }

  return {
    code,
    name,
    device_type: resolveDeviceType(),
    stream_url: streamUrl,
    install_location: installLocation || null,
    status: form.status,
    is_enabled: enabledValue.value === 'true',
    config: normalizeConfig(),
  };
}

function resetForm() {
  editingId.value = null;
  enabledValue.value = 'true';
  syncDeviceType('camera');
  Object.assign(form, createEmptyForm());
  submitError.value = '';
  submitMessage.value = '';
}

function startEdit(device: DeviceSummary) {
  editingId.value = device.id;
  enabledValue.value = String(device.is_enabled);
  syncDeviceType(device.device_type);
  Object.assign(form, {
    code: device.code,
    name: device.name,
    stream_url: device.stream_url,
    install_location: device.install_location ?? '',
    status: device.status,
    configJson: JSON.stringify(device.config, null, 2),
  });
  submitError.value = '';
  submitMessage.value = '';
}

async function loadDevices() {
  loadError.value = '';
  try {
    devices.value = await listDevices();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载设备列表。';
  }
}

async function submitForm() {
  submitting.value = true;
  submitError.value = '';
  submitMessage.value = '';

  try {
    const payload = buildPayload();
    if (editingId.value) {
      await updateDevice(editingId.value, payload);
      submitMessage.value = '设备更新成功。';
    } else {
      await createDevice(payload);
      submitMessage.value = '设备创建成功。';
    }
    await loadDevices();
    resetForm();
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法保存设备。';
  } finally {
    submitting.value = false;
  }
}

async function toggleDevice(device: DeviceSummary) {
  submitError.value = '';
  submitMessage.value = '';

  try {
    await updateDeviceStatus(device.id, {
      status: device.is_enabled ? 'disabled' : 'online',
      is_enabled: !device.is_enabled,
    });
    submitMessage.value = device.is_enabled ? '设备已停用。' : '设备已启用。';
    await loadDevices();
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法更新设备状态。';
  }
}

async function removeDevice(device: DeviceSummary) {
  if (!window.confirm(`确认删除设备“${device.name}”吗？`)) {
    return;
  }

  submitError.value = '';
  submitMessage.value = '';
  try {
    await deleteDevice(device.id);
    submitMessage.value = '设备删除成功。';
    if (editingId.value === device.id) {
      resetForm();
    }
    await loadDevices();
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法删除设备。';
  }
}

const adminHint = computed(() => authStore.isAdmin);

onMounted(async () => {
  if (adminHint.value) {
    resetForm();
  }
  await loadDevices();
});
</script>
