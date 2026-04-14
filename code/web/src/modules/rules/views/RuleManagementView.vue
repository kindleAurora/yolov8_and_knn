<template>
  <section class="page-shell">
    <header class="page-header">
      <div>
        <p class="page-header__eyebrow">规则配置</p>
        <h2>告警规则配置</h2>
        <p class="page-header__text">
          管理系统预设规则和最小自定义规则，控制哪些行为会被升级为告警。
        </p>
      </div>
      <button class="ghost-button" type="button" @click="refreshAll">刷新数据</button>
    </header>

    <section class="metrics-grid">
      <article class="metric-card">
        <span>规则总数</span>
        <strong>{{ rules.length }}</strong>
        <p>当前农场下已配置的告警规则总量。</p>
      </article>
      <article class="metric-card">
        <span>预设规则</span>
        <strong>{{ presetRuleCount }}</strong>
        <p>系统默认内置的基础规则模板。</p>
      </article>
      <article class="metric-card">
        <span>自定义规则</span>
        <strong>{{ customRuleCount }}</strong>
        <p>管理员按现场需要自行新增的规则。</p>
      </article>
      <article class="metric-card">
        <span>启用规则</span>
        <strong>{{ enabledRuleCount }}</strong>
        <p>当前仍会参与告警判断的规则数量。</p>
      </article>
    </section>

    <div class="content-grid">
      <article class="panel">
        <header class="panel__header">
          <h3>规则清单</h3>
          <span class="panel__badge">{{ rules.length }} 条</span>
        </header>

        <p v-if="loadError" class="error-text">{{ loadError }}</p>

        <div class="stack-list">
          <article v-for="rule in rules" :key="rule.id" class="entity-card">
            <div class="entity-card__header">
              <div>
                <strong>{{ rule.name }}</strong>
                <p>{{ formatRuleType(rule.rule_type) }} / {{ rule.source === 'preset' ? '预设规则' : '自定义规则' }}</p>
              </div>
              <div class="rule-pill-group">
                <span :class="['rule-pill', `rule-pill--${rule.severity}`]">{{ formatSeverity(rule.severity) }}</span>
                <span :class="['rule-pill', rule.is_enabled ? 'rule-pill--enabled' : 'rule-pill--disabled']">
                  {{ rule.is_enabled ? '启用中' : '已停用' }}
                </span>
              </div>
            </div>

            <dl class="entity-grid">
              <div>
                <dt>阈值</dt>
                <dd>{{ rule.threshold_minutes }} 分钟</dd>
              </div>
              <div>
                <dt>绑定设备</dt>
                <dd>{{ rule.device_name || '全部设备' }}</dd>
              </div>
              <div>
                <dt>目标区域</dt>
                <dd>{{ rule.zone_name || '未指定' }}</dd>
              </div>
              <div>
                <dt>目标行为</dt>
                <dd>{{ rule.behavior_type || '按规则类型自动判断' }}</dd>
              </div>
            </dl>

            <p class="entity-note">{{ rule.description || '暂无规则说明。' }}</p>

            <div class="entity-actions">
              <button
                v-if="authStore.isAdmin"
                class="ghost-button"
                type="button"
                @click="startEdit(rule)"
              >
                编辑
              </button>
              <button
                v-if="authStore.isAdmin"
                class="ghost-button"
                type="button"
                @click="toggleRule(rule)"
              >
                {{ rule.is_enabled ? '停用' : '启用' }}
              </button>
              <button
                v-if="authStore.isAdmin && rule.source === 'custom'"
                class="ghost-button ghost-button--danger"
                type="button"
                @click="removeRule(rule.id)"
              >
                删除
              </button>
              <span v-if="!authStore.isAdmin" class="entity-note">普通用户模式：规则仅可查看</span>
            </div>
          </article>
        </div>
      </article>

      <article class="panel">
        <header class="panel__header">
          <h3>{{ editingId ? '编辑规则' : '新增自定义规则' }}</h3>
          <button class="ghost-button" type="button" @click="resetForm">重置表单</button>
        </header>

        <p v-if="!authStore.isAdmin" class="entity-note">
          当前账号没有规则编辑权限，可以先浏览已有规则配置。
        </p>

        <form v-else class="form-grid" @submit.prevent="submitForm">
          <label class="field">
            <span>规则名称</span>
            <input v-model.trim="form.name" type="text" maxlength="120" required />
          </label>

          <label class="field">
            <span>规则类型</span>
            <select v-model="form.ruleType">
              <option value="lying_duration">持续躺卧超时</option>
              <option value="zone_dwell">区域停留超时</option>
              <option value="no_drinking">长时间未进入饮水区</option>
            </select>
          </label>

          <label class="field">
            <span>告警等级</span>
            <select v-model="form.severity">
              <option value="high">高</option>
              <option value="medium">中</option>
              <option value="low">低</option>
            </select>
          </label>

          <label class="field">
            <span>阈值（分钟）</span>
            <input v-model.number="form.thresholdMinutes" type="number" min="1" max="1440" required />
          </label>

          <label class="field">
            <span>绑定设备</span>
            <select v-model="form.deviceId">
              <option value="">全部设备</option>
              <option v-for="device in devices" :key="device.id" :value="String(device.id)">
                {{ device.name }}
              </option>
            </select>
          </label>

          <label class="field">
            <span>目标区域</span>
            <input v-model.trim="form.zoneName" type="text" maxlength="120" placeholder="例如：饮水区" />
          </label>

          <label class="field">
            <span>目标行为</span>
            <input v-model.trim="form.behaviorType" type="text" maxlength="64" placeholder="例如：躺卧" />
          </label>

          <label class="field">
            <span>启用状态</span>
            <select v-model="form.isEnabled">
              <option :value="true">启用</option>
              <option :value="false">停用</option>
            </select>
          </label>

          <label class="field field--full">
            <span>规则说明</span>
            <textarea v-model.trim="form.description" rows="4" />
          </label>

          <label class="field field--full">
            <span>扩展配置 JSON</span>
            <textarea v-model="form.configJson" rows="6" />
          </label>

          <button class="primary-button" type="submit" :disabled="submitting">
            {{ submitting ? '保存中...' : editingId ? '保存规则' : '创建规则' }}
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

import { listDevices } from '@/api/devices';
import { createRule, deleteRule, listRules, updateRule, updateRuleStatus } from '@/api/rules';
import { useAuthStore } from '@/stores/auth';
import type { DeviceSummary } from '@/types/device';
import type { AlertRulePayload, AlertRuleSummary, RuleSeverity, RuleType } from '@/types/rule';

interface RuleFormState {
  name: string;
  description: string;
  ruleType: RuleType;
  severity: RuleSeverity;
  thresholdMinutes: number;
  deviceId: string;
  zoneName: string;
  behaviorType: string;
  isEnabled: boolean;
  configJson: string;
}

const authStore = useAuthStore();

const devices = ref<DeviceSummary[]>([]);
const rules = ref<AlertRuleSummary[]>([]);
const loadError = ref('');
const submitError = ref('');
const submitMessage = ref('');
const submitting = ref(false);
const editingId = ref<number | null>(null);
const form = reactive<RuleFormState>(createEmptyForm());

const presetRuleCount = computed(() => rules.value.filter((rule) => rule.source === 'preset').length);
const customRuleCount = computed(() => rules.value.filter((rule) => rule.source === 'custom').length);
const enabledRuleCount = computed(() => rules.value.filter((rule) => rule.is_enabled).length);

function createEmptyForm(): RuleFormState {
  return {
    name: '',
    description: '',
    ruleType: 'lying_duration',
    severity: 'medium',
    thresholdMinutes: 30,
    deviceId: '',
    zoneName: '',
    behaviorType: '',
    isEnabled: true,
    configJson: '{\n  "remark": "自定义规则"\n}',
  };
}

function formatRuleType(ruleType: RuleType) {
  if (ruleType === 'lying_duration') {
    return '持续躺卧超时';
  }
  if (ruleType === 'zone_dwell') {
    return '区域停留超时';
  }
  return '长时间未进入饮水区';
}

function formatSeverity(value: string) {
  if (value === 'high') {
    return '高等级';
  }
  if (value === 'medium') {
    return '中等级';
  }
  return '低等级';
}

function parseConfigJson() {
  const parsed = JSON.parse(form.configJson) as unknown;
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('扩展配置 JSON 必须是对象。');
  }
  return parsed as Record<string, unknown>;
}

function buildPayload(): AlertRulePayload {
  return {
    name: form.name,
    description: form.description || null,
    rule_type: form.ruleType,
    severity: form.severity,
    threshold_minutes: form.thresholdMinutes,
    device_id: form.deviceId ? Number(form.deviceId) : null,
    zone_name: form.zoneName || null,
    behavior_type: form.behaviorType || null,
    is_enabled: form.isEnabled,
    config: parseConfigJson(),
  };
}

function resetForm() {
  Object.assign(form, createEmptyForm());
  editingId.value = null;
  submitError.value = '';
  submitMessage.value = '';
}

function startEdit(rule: AlertRuleSummary) {
  editingId.value = rule.id;
  form.name = rule.name;
  form.description = rule.description || '';
  form.ruleType = rule.rule_type;
  form.severity = rule.severity;
  form.thresholdMinutes = rule.threshold_minutes;
  form.deviceId = rule.device_id ? String(rule.device_id) : '';
  form.zoneName = rule.zone_name || '';
  form.behaviorType = rule.behavior_type || '';
  form.isEnabled = rule.is_enabled;
  form.configJson = JSON.stringify(rule.config, null, 2);
  submitError.value = '';
  submitMessage.value = '';
}

async function loadRuleList() {
  loadError.value = '';

  try {
    rules.value = await listRules();
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载规则列表。';
  }
}

async function refreshAll() {
  loadError.value = '';

  try {
    const [deviceList, ruleList] = await Promise.all([listDevices(), listRules()]);
    devices.value = deviceList;
    rules.value = ruleList;
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : '无法加载规则配置数据。';
  }
}

async function toggleRule(rule: AlertRuleSummary) {
  await updateRuleStatus(rule.id, !rule.is_enabled);
  await loadRuleList();
}

async function removeRule(ruleId: number) {
  await deleteRule(ruleId);
  if (editingId.value === ruleId) {
    resetForm();
  }
  await loadRuleList();
}

async function submitForm() {
  submitting.value = true;
  submitError.value = '';
  submitMessage.value = '';

  try {
    const payload = buildPayload();
    if (editingId.value) {
      await updateRule(editingId.value, payload);
      submitMessage.value = '规则已更新。';
    } else {
      await createRule(payload);
      submitMessage.value = '规则已创建。';
    }
    await loadRuleList();
    resetForm();
  } catch (error) {
    submitError.value = error instanceof Error ? error.message : '无法保存规则。';
  } finally {
    submitting.value = false;
  }
}

onMounted(async () => {
  await refreshAll();
});
</script>

<style scoped>
.rule-pill-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: end;
}

.rule-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.rule-pill--high {
  background: rgba(190, 48, 48, 0.12);
  color: #a42323;
}

.rule-pill--medium {
  background: rgba(238, 152, 54, 0.14);
  color: #9c5713;
}

.rule-pill--low {
  background: rgba(40, 117, 179, 0.12);
  color: #1f5f94;
}

.rule-pill--enabled {
  background: rgba(29, 135, 87, 0.12);
  color: #1f7c50;
}

.rule-pill--disabled {
  background: rgba(111, 124, 134, 0.14);
  color: #5c6b74;
}

@media (max-width: 760px) {
  .rule-pill-group {
    justify-content: start;
  }
}
</style>
