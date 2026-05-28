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
const providerOptions = [
  { id: 'mock', title: 'Mock 演示', desc: '无密钥离线演示，适合课堂截图。' },
  { id: 'local_ollama', title: '本地 Ollama', desc: '连接本机 Ollama 服务。' },
  { id: 'cloud_ollama', title: '云端 Ollama', desc: '获取并测试云端模型列表。' },
  { id: 'openai_compatible', title: '兼容接口', desc: '适合 DeepSeek 等服务。' }
]
</script>

<template>
  <section class="provider-panel">
    <div class="runtime-state">
      <span :class="['state-dot', faceOk ? 'ok' : '']"></span>
      <strong>{{ faceOk ? '已登录' : '待核验' }}</strong>
      <small>{{ status.message }}</small>
    </div>

    <div class="provider-fields">
      <div class="provider-choice">
        <button
          v-for="option in providerOptions"
          :key="option.id"
          type="button"
          :class="{ selected: config.provider === option.id }"
          @click="config.provider = option.id"
        >
          <strong>{{ option.title }}</strong>
          <span>{{ option.desc }}</span>
        </button>
      </div>

      <label v-if="config.provider !== 'mock'">
        <span>模型</span>
        <select v-if="showCloudModels" v-model="config.model">
          <option v-for="model in cloudModels" :key="model.id" :value="model.id">{{ model.name }}</option>
        </select>
        <input v-else v-model="config.model" :placeholder="modelPlaceholder" />
      </label>

      <label v-if="config.provider !== 'mock'" class="url-field">
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

      <details class="advanced-settings">
        <summary>高级设置</summary>
        <label class="toggle">
        <input v-model="config.langsmith_enabled" type="checkbox" />
        <span>
          LangSmith 追踪
          <small>用于记录 LangChain / LangGraph 的调用链路、Prompt、模型返回和耗时，便于调试。需要配置 LANGSMITH_API_KEY，课堂演示一般保持关闭。</small>
        </span>
        </label>
      </details>

      <button v-if="config.provider === 'cloud_ollama'" :disabled="cloudLoading" @click="$emit('load-cloud-models')">
        <RefreshCw :size="16" /> 模型列表
      </button>

      <button class="primary provider-test" :disabled="status.loading" @click="$emit('test')">
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
