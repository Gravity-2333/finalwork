<script setup>
import { computed } from 'vue'
import { Bot, RefreshCw, ShieldAlert, Wifi } from 'lucide-vue-next'

const props = defineProps({
  config: { type: Object, required: true },
  status: { type: Object, required: true },
  faceOk: Boolean,
  providerHint: { type: String, required: true },
  modelPlaceholder: { type: String, required: true },
  baseUrlPlaceholder: { type: String, required: true },
  apiKeyEnvPlaceholder: { type: String, required: true },
  cloudModels: { type: Array, default: () => [] },
  cloudLoading: Boolean,
  testMessage: { type: String, default: '' }
})

defineEmits(['test', 'load-cloud-models'])

const showApiKey = computed(() => ['cloud_ollama', 'openai_compatible'].includes(props.config.provider))
const showCloudModels = computed(() => props.config.provider === 'cloud_ollama' && props.cloudModels.length)
</script>

<template>
  <section class="provider-panel">
    <div class="runtime-state">
      <span :class="['state-dot', faceOk ? 'ok' : '']"></span>
      <strong>{{ faceOk ? '已登录' : '待核验' }}</strong>
      <small>{{ status.message }}</small>
    </div>

    <div class="provider-fields">
      <label>
        <span>模型来源</span>
        <select v-model="config.provider">
          <option value="mock">Mock</option>
          <option value="local_ollama">本地 Ollama</option>
          <option value="cloud_ollama">云端 Ollama</option>
          <option value="openai_compatible">OpenAI 兼容</option>
        </select>
      </label>

      <label>
        <span>模型</span>
        <select v-if="showCloudModels" v-model="config.model">
          <option v-for="model in cloudModels" :key="model.id" :value="model.id">{{ model.name }}</option>
        </select>
        <input v-else v-model="config.model" :placeholder="modelPlaceholder" />
      </label>

      <label>
        <span>地址</span>
        <input v-model="config.base_url" :placeholder="baseUrlPlaceholder" />
      </label>

      <label v-if="showApiKey">
        <span>Key 模式</span>
        <select v-model="config.key_mode">
          <option value="env">环境变量</option>
          <option value="manual">手动填写</option>
        </select>
      </label>

      <label v-if="showApiKey">
        <span>{{ config.key_mode === 'manual' ? 'API Key' : '变量名' }}</span>
        <input
          v-if="config.key_mode === 'manual'"
          v-model="config.api_key"
          type="password"
          placeholder="sk-..."
        />
        <input v-else v-model="config.api_key_env" :placeholder="apiKeyEnvPlaceholder" />
      </label>

      <label class="toggle">
        <input v-model="config.langsmith_enabled" type="checkbox" />
        追踪
      </label>

      <button v-if="config.provider === 'cloud_ollama'" :disabled="cloudLoading" @click="$emit('load-cloud-models')">
        <RefreshCw :size="16" /> 模型列表
      </button>

      <button class="primary" :disabled="status.loading" @click="$emit('test')">
        <Wifi :size="16" /> 测试
      </button>
    </div>

    <p :class="{ warning: status.warning }">
      <ShieldAlert v-if="status.warning" :size="16" />
      <Bot v-else :size="16" />
      {{ testMessage || status.warning || providerHint }}
    </p>
  </section>
</template>
