<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import DashboardMetrics from './components/DashboardMetrics.vue'
import FaceGate from './components/FaceGate.vue'
import HeroHeader from './components/HeroHeader.vue'
import KnowledgePanel from './components/KnowledgePanel.vue'
import ProviderPanel from './components/ProviderPanel.vue'
import QuizPanel from './components/QuizPanel.vue'
import StudyPanel from './components/StudyPanel.vue'
import {
  createChapterContent,
  createOutline,
  createQuiz,
  faceLogin,
  health,
  listCloudOllamaModels,
  listChapters,
  listDocuments,
  listWrongAnswers,
  submitQuiz,
  testProvider,
  uploadDocument
} from './api'
import { useVoiceCommands } from './useVoice'

const status = reactive({
  loading: false,
  message: '系统已就绪，请先上传课程资料。',
  warning: ''
})

const config = reactive({
  provider: 'mock',
  model: '',
  base_url: '',
  key_mode: 'env',
  api_key: '',
  api_key_env: '',
  langsmith_enabled: false
})

const env = reactive({
  langsmith_ready: false,
  ollama_key_ready: false,
  deepseek_key_ready: false
})

const documents = ref([])
const chapters = ref([])
const selectedChapterId = ref(null)
const quizzes = ref([])
const answers = reactive({})
const result = ref(null)
const wrongs = ref([])
const cloudModels = ref([])
const cloudLoading = ref(false)
const testMessage = ref('')
const face = reactive({ ok: false })

const providerDefaults = {
  mock: {
    model: 'mock-assistant',
    base_url: '',
    api_key_env: '',
    hint: 'Mock Provider 离线演示，不需要 API Key。'
  },
  local_ollama: {
    model: 'qwen2.5:7b',
    base_url: 'http://localhost:11434',
    api_key_env: '',
    hint: '本地 Ollama 使用 /api/chat，默认地址 http://localhost:11434。'
  },
  cloud_ollama: {
    model: 'qwen3-coder-next',
    base_url: 'https://ollama.com/v1',
    api_key_env: 'OLLAMA_API_KEY',
    hint: '云端 Ollama 会拉取并测试可用模型，API Key 可手填或读取 OLLAMA_API_KEY。'
  },
  openai_compatible: {
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    api_key_env: 'DEEPSEEK_API_KEY',
    hint: '通用 OpenAI-compatible 模式，可用于 DeepSeek 等兼容接口。'
  }
}

const selectedChapter = computed(() => chapters.value.find((item) => item.id === selectedChapterId.value))
const uniqueDocuments = computed(() => {
  const seen = new Set()
  return documents.value.filter((item) => {
    if (seen.has(item.filename)) return false
    seen.add(item.filename)
    return true
  })
})
const visibleWrongs = computed(() => wrongs.value.slice(0, 3))
const progress = computed(() => {
  if (!chapters.value.length) return 0
  return Math.round(chapters.value.reduce((sum, item) => sum + item.progress, 0) / chapters.value.length)
})
const providerHint = computed(() => providerDefaults[config.provider].hint)
const modelPlaceholder = computed(() => providerDefaults[config.provider].model)
const baseUrlPlaceholder = computed(() => providerDefaults[config.provider].base_url || '无需填写')

const { listening, supported, transcript, start } = useVoiceCommands({
  outline: generateOutline,
  quiz: generateQuizForSelected,
  wrong: loadWrongs,
  mock: () => {
    config.provider = 'mock'
    status.message = '已通过语音切换到 Mock Provider。'
  }
})

onMounted(async () => {
  applyProviderDefaults()
  await refreshHealth()
  await refreshDocuments()
  await refreshChapters()
  await loadWrongs()
  const params = new URLSearchParams(window.location.search)
  if (params.get('demo') === '1') await demoFlow()
})

watch(
  () => config.provider,
  () => {
    applyProviderDefaults()
    testMessage.value = ''
  }
)

async function runTask(message, task) {
  status.loading = true
  status.message = message
  status.warning = ''
  testMessage.value = ''
  try {
    const data = await task()
    if (data?.warning) status.warning = data.warning
    return data
  } catch (error) {
    status.warning = error.message
    return null
  } finally {
    status.loading = false
  }
}

async function refreshHealth() {
  const data = await health().catch(() => ({}))
  Object.assign(env, data)
}

async function refreshDocuments() {
  const data = await listDocuments().catch(() => ({ documents: [] }))
  documents.value = data.documents
}

async function refreshChapters() {
  const data = await listChapters().catch(() => ({ chapters: [] }))
  chapters.value = data.chapters
  selectedChapterId.value = chapters.value[0]?.id || null
}

async function verifyFace() {
  const data = await runTask('正在进行人脸核验...', faceLogin)
  if (data?.ok) {
    face.ok = true
    status.message = '人脸核验通过，可以开始学习。'
  }
}

async function handleUpload(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const data = await runTask('正在上传并切割课程资料...', () => uploadDocument(file))
  if (data) {
    status.message = `已构建知识库：${data.document.filename}，共 ${data.document.chunk_count} 个片段。`
    await refreshDocuments()
  }
}

async function generateOutline() {
  const data = await runTask('正在通过 LangGraph 生成课程大纲...', () => createOutline(providerPayload()))
  if (data) {
    chapters.value = data.chapters
    selectedChapterId.value = chapters.value[0]?.id || null
    status.message = '课程大纲已生成，可继续生成章节学习内容。'
  }
}

async function generateContent(chapter) {
  const data = await runTask(`正在生成《${chapter.title}》学习内容...`, () =>
    createChapterContent(chapter.id, providerPayload())
  )
  if (data) {
    const index = chapters.value.findIndex((item) => item.id === chapter.id)
    chapters.value[index] = data.chapter
    selectedChapterId.value = chapter.id
    status.message = '章节内容已生成，学习进度已记录。'
  }
}

async function generateQuizForSelected() {
  if (!selectedChapter.value) return
  const data = await runTask('正在生成在线测验...', () => createQuiz(selectedChapter.value.id, providerPayload()))
  if (data) {
    quizzes.value = data.quizzes
    result.value = null
    Object.keys(answers).forEach((key) => delete answers[key])
    status.message = '测验已生成，请完成作答。'
  }
}

async function submitCurrentQuiz() {
  if (!selectedChapter.value) return
  const data = await runTask('正在提交测验并归档错题...', () => submitQuiz(selectedChapter.value.id, answers))
  if (data) {
    result.value = data
    const index = chapters.value.findIndex((item) => item.id === data.chapter.id)
    chapters.value[index] = data.chapter
    status.message = `测验完成：${data.score}/${data.total}，错题已自动归档。`
    await loadWrongs()
  }
}

async function loadWrongs() {
  const data = await listWrongAnswers().catch(() => ({ wrong_answers: [] }))
  wrongs.value = data.wrong_answers
}

async function runProviderTest() {
  const data = await runTask('正在测试模型连接...', () => testProvider(providerPayload()))
  if (data?.ok) {
    testMessage.value = `连接成功：${data.provider} / ${data.message || 'OK'}`
    status.message = '模型连接测试通过。'
  }
}

async function loadCloudModels() {
  if (!navigator.onLine) {
    status.warning = '当前浏览器显示网络离线，无法获取云端 Ollama 模型列表。'
    testMessage.value = ''
    return
  }
  cloudLoading.value = true
  try {
    const data = await runTask('正在获取并测试云端 Ollama 模型...', () => listCloudOllamaModels(providerPayload()))
    if (data?.models?.length) {
      cloudModels.value = data.models
      config.model = data.models[0].id
      status.message = `已获取 ${data.models.length} 个可用云端 Ollama 模型。`
    } else if (data) {
      status.warning = '云端 Ollama 暂无已测试可用的项目模型，请检查账号权限或更换 API Key。'
    }
  } finally {
    cloudLoading.value = false
  }
}

async function demoFlow() {
  await verifyFace()
  if (uniqueDocuments.value.length) {
    await generateOutline()
    if (selectedChapter.value) await generateContent(selectedChapter.value)
    await generateQuizForSelected()
  }
}

function providerPayload() {
  return {
    provider: config.provider,
    model: config.model,
    base_url: config.base_url,
    api_key: config.key_mode === 'manual' ? config.api_key : '',
    api_key_env: config.key_mode === 'env' ? config.api_key_env : '',
    langsmith_enabled: config.langsmith_enabled
  }
}

function applyProviderDefaults() {
  const defaults = providerDefaults[config.provider]
  const knownModels = Object.values(providerDefaults).map((item) => item.model)
  const knownBaseUrls = Object.values(providerDefaults).map((item) => item.base_url)
  const knownKeyEnvs = Object.values(providerDefaults).map((item) => item.api_key_env)
  if (!config.model || knownModels.includes(config.model)) config.model = defaults.model
  if (!config.base_url || knownBaseUrls.includes(config.base_url)) config.base_url = defaults.base_url
  if (!config.api_key_env || knownKeyEnvs.includes(config.api_key_env)) config.api_key_env = defaults.api_key_env
  if (config.provider === 'mock' || config.provider === 'local_ollama') config.api_key = ''
}
</script>

<template>
  <FaceGate v-if="!face.ok" :loading="status.loading" :message="status.warning || status.message" @verify="verifyFace" />
  <main v-else class="app-shell">
    <HeroHeader
      :face-ok="face.ok"
      :loading="status.loading"
      :listening="listening"
      :supported="supported"
      @verify="verifyFace"
      @voice="start"
    />

    <ProviderPanel
      :config="config"
      :status="status"
      :face-ok="face.ok"
      :provider-hint="providerHint"
      :model-placeholder="modelPlaceholder"
      :base-url-placeholder="baseUrlPlaceholder"
      :cloud-models="cloudModels"
      :cloud-loading="cloudLoading"
      :test-message="testMessage"
      @test="runProviderTest"
      @load-cloud-models="loadCloudModels"
    />

    <DashboardMetrics
      :document-count="uniqueDocuments.length"
      :chapter-count="chapters.length"
      :progress="progress"
      :wrong-count="wrongs.length"
    />

    <section class="workspace">
      <KnowledgePanel :documents="uniqueDocuments" @upload="handleUpload" />
      <StudyPanel
        :chapters="chapters"
        :selected-chapter="selectedChapter"
        :selected-chapter-id="selectedChapterId"
        :loading="status.loading"
        @outline="generateOutline"
        @select="selectedChapterId = $event"
        @content="generateContent"
        @quiz="generateQuizForSelected"
        @wrong="loadWrongs"
      />
      <QuizPanel
        :quizzes="quizzes"
        :answers="answers"
        :result="result"
        :wrongs="visibleWrongs"
        @submit="submitCurrentQuiz"
      />
    </section>

    <section class="voice-strip">
      <span>语音识别：{{ transcript }}</span>
      <small>可说“生成大纲”“开始测验”“查看错题”“切换 mock 模型”。</small>
    </section>
  </main>
</template>
