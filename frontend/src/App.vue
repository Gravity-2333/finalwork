<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Activity, BookOpen, CheckCircle2, Compass, FolderOpen, MessageCircle, Mic, Radio, Settings, Trophy } from 'lucide-vue-next'
import DashboardMetrics from './components/DashboardMetrics.vue'
import FaceGate from './components/FaceGate.vue'
import HeroHeader from './components/HeroHeader.vue'
import KnowledgePanel from './components/KnowledgePanel.vue'
import ProviderPanel from './components/ProviderPanel.vue'
import QuizPanel from './components/QuizPanel.vue'
import SettingsModal from './components/SettingsModal.vue'
import StudyPanel from './components/StudyPanel.vue'
import {
  createChapterContent,
  createOutline,
  createQuiz,
  clearDocuments,
  deleteDocument,
  faceEnroll,
  faceLogin,
  faceProfile,
  health,
  listCloudOllamaModels,
  listChapters,
  listDocuments,
  listWrongAnswers,
  submitQuiz,
  testProvider,
  uploadDocuments
} from './api'
import { useVoiceCommands, VOICE_COMMAND_GROUPS } from './useVoice'

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
const activeView = ref('library')
const face = reactive({ ok: false })
const faceProfileState = reactive({ enrolled: false, username: '杨翰飞', needsUpgrade: false })
const faceManageOpen = ref(false)
const settingsOpen = ref(false)
const faceReplaceToken = ref('')
const maxUploadBytes = 25 * 1024 * 1024
const maxUploadFiles = 20
let faceProfileLookupId = 0

const defaultPrompts = {
  outline:
    '你是学习大纲生成器。请严格根据课程资料生成4个章节的学习大纲。\n只输出4行大纲，不要寒暄、不要解释、不要标题、不要 Markdown 代码块。\n每行格式必须为：章节标题 - 学习目标。\n章节标题简洁，学习目标适合学生复习。\n资料：\n{{context}}',
  chapter:
    '你是章节学习内容生成器。请为章节《{{chapter_title}}》生成可直接展示给学生的 Markdown 学习内容。\n章节目标：{{chapter_objective}}\n输出要求：\n1. 只输出正文 Markdown，不要出现“好的”“下面是”“这是为您生成的”等寒暄语。\n2. 不要重复章节标题和章节目标。\n3. 使用二级或三级标题、列表和加粗组织内容。\n4. 内容必须包含核心概念、学习步骤、重点难点和复盘建议。\n资料：\n{{context}}',
  quiz:
    '请基于以下资料为章节《{{chapter_title}}》生成3道单选题。\n输出 JSON 数组，每项包含 question/options/answer/explanation。\n章节目标：{{chapter_objective}}\n资料：\n{{context}}'
}

const appSettings = reactive({
  upload: {
    maxFiles: maxUploadFiles,
    maxSizeText: '25MB'
  },
  prompts: {
    outline: defaultPrompts.outline,
    chapter: defaultPrompts.chapter,
    quiz: defaultPrompts.quiz
  }
})

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
const navItems = [
  { id: 'library', label: '知识库', icon: FolderOpen },
  { id: 'study', label: '学习路径', icon: BookOpen },
  { id: 'quiz', label: '测验复盘', icon: Trophy },
  { id: 'voice', label: '语音助手', icon: Mic },
  { id: 'settings', label: '模型设置', icon: Settings }
]
const progress = computed(() => {
  if (!chapters.value.length) return 0
  return Math.round(chapters.value.reduce((sum, item) => sum + item.progress, 0) / chapters.value.length)
})
const providerHint = computed(() => providerDefaults[config.provider].hint)
const modelPlaceholder = computed(() => providerDefaults[config.provider].model)
const baseUrlPlaceholder = computed(() => providerDefaults[config.provider].base_url || '无需填写')
const apiKeyEnvPlaceholder = computed(() => providerDefaults[config.provider].api_key_env || '环境变量名')

const { listening, supported, transcript, voiceStatus, start, testMicrophone, stopMicrophoneTest, refreshMicrophoneState } = useVoiceCommands({
  upload: () => {
    activeView.value = 'library'
    status.message = '已切换到资料上传，请点击上传区域选择课程资料。'
    return { message: '已打开资料上传。' }
  },
  library: () => {
    activeView.value = 'library'
    status.message = '已切换到知识库。'
    return { message: '已打开知识库。' }
  },
  study: () => {
    activeView.value = 'study'
    status.message = '已切换到学习路径。'
    return { message: '已打开学习路径。' }
  },
  quizPage: () => {
    activeView.value = 'quiz'
    status.message = '已切换到测验复盘。'
    return { message: '已打开测验复盘。' }
  },
  outline: () => {
    if (!documents.value.length) return voiceGuard('请先上传课程资料，才能生成课程大纲。', 'library')
    void generateOutline()
    return { message: '正在生成课程大纲。' }
  },
  content: () => {
    if (!chapters.value.length) return voiceGuard('请先生成课程大纲，再生成章节内容。', 'study')
    if (!selectedChapter.value) return voiceGuard('请先选择一个章节。', 'study')
    void generateContent(selectedChapter.value)
    return { message: `正在生成《${selectedChapter.value.title}》学习内容。` }
  },
  quiz: () => {
    if (!chapters.value.length) return voiceGuard('请先生成课程大纲，再开始测验。', 'study')
    if (!selectedChapter.value) return voiceGuard('请先选择一个章节，再开始测验。', 'study')
    void generateQuizForSelected()
    return { message: '正在生成当前章节测验。' }
  },
  wrong: async () => {
    await loadWrongs()
    activeView.value = 'quiz'
    status.message = '已切换到测验复盘，可查看错题归档。'
    return { message: wrongs.value.length ? '已打开错题归档。' : '已打开测验复盘，当前暂无错题。' }
  },
  settings: () => {
    activeView.value = 'settings'
    status.message = '已切换到模型设置。'
    return { message: '已打开模型设置。' }
  },
  systemSettings: () => {
    settingsOpen.value = true
    status.message = '已打开系统设置。'
    return { message: '已打开系统设置。' }
  },
  providerTest: () => {
    activeView.value = 'settings'
    void runProviderTest()
    return { message: '正在测试模型连接。' }
  },
  cloudModels: () => {
    activeView.value = 'settings'
    if (config.provider !== 'cloud_ollama') return voiceGuard('请先切换到云端 Ollama，再获取模型列表。', 'settings')
    void loadCloudModels()
    return { message: '正在获取云端 Ollama 模型列表。' }
  },
  microphoneTest: () => {
    void testMicrophone()
    return { message: '正在测试麦克风。' }
  },
  mock: () => {
    config.provider = 'mock'
    status.message = '已通过语音切换到 Mock Provider。'
    return { message: '已切换到 Mock Provider。' }
  },
  localOllama: () => {
    config.provider = 'local_ollama'
    activeView.value = 'settings'
    status.message = '已通过语音切换到本地 Ollama。'
    return { message: '已切换到本地 Ollama。' }
  },
  cloudOllama: () => {
    config.provider = 'cloud_ollama'
    activeView.value = 'settings'
    status.message = '已通过语音切换到云端 Ollama。'
    return { message: '已切换到云端 Ollama。' }
  },
  openaiCompatible: () => {
    config.provider = 'openai_compatible'
    activeView.value = 'settings'
    status.message = '已通过语音切换到 OpenAI 兼容模型。'
    return { message: '已切换到 OpenAI 兼容模型。' }
  }
})

const voiceModeText = computed(() => (listening.value ? '正在监听' : voiceStatus.testingMicrophone ? '麦克风测试中' : '待命'))
const voiceDetail = computed(() => (voiceStatus.diagnostic === transcript.value ? '' : voiceStatus.diagnostic))

onMounted(async () => {
  loadSettings()
  applyProviderDefaults()
  await refreshFaceProfile()
  await refreshHealth()
  await refreshDocuments()
  await refreshChapters()
  await loadWrongs()
  await refreshMicrophoneState()
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

async function refreshFaceProfile(username = faceProfileState.username) {
  const normalized = (username || '杨翰飞').trim() || '杨翰飞'
  const lookupId = (faceProfileLookupId += 1)
  const data = await faceProfile(normalized).catch(() => ({ enrolled: false, username: normalized }))
  if (lookupId !== faceProfileLookupId) return
  faceProfileState.enrolled = data.enrolled
  faceProfileState.username = data.username
  faceProfileState.needsUpgrade = Boolean(data.needs_upgrade)
}

function handleFaceUsernameChange(username) {
  const normalized = (username || '杨翰飞').trim() || '杨翰飞'
  faceProfileState.username = normalized
  faceProfileState.enrolled = false
  faceProfileState.needsUpgrade = false
  refreshFaceProfile(normalized)
}

async function enrollFace(payload) {
  const data = await runTask('正在录入授权人脸模板...', () =>
    faceEnroll({ ...payload, allow_replace: face.ok, replace_token: face.ok ? faceReplaceToken.value : '' })
  )
  if (data?.ok) {
    faceProfileState.enrolled = true
    faceProfileState.username = data.username
    faceProfileState.needsUpgrade = false
    faceManageOpen.value = false
    status.message = face.ok ? '授权人脸已重新录入，后续登录将使用新模板。' : '授权人脸已录入，请点击人脸识别登录。'
  }
}

async function verifyFace(payload) {
  const data = await runTask('正在进行人脸特征比对...', () => faceLogin(payload))
  if (data?.ok) {
    face.ok = true
    faceProfileState.username = data.username
    faceReplaceToken.value = data.replace_token || ''
    status.message = Object.prototype.hasOwnProperty.call(data, 'distance')
      ? data.message || `人脸识别通过，模型距离 ${data.distance} / 阈值 ${data.threshold}，可以开始学习。`
      : `人脸识别通过，相似度 ${data.similarity}，可以开始学习。`
  } else if (data) {
    face.ok = false
    faceReplaceToken.value = ''
    status.warning = data.distance
      ? data.message || `人脸比对未通过，模型距离 ${data.distance} / 阈值 ${data.threshold}。`
      : data.message || '人脸比对未通过，请使用已录入账号本人登录。'
  }
}

function logout() {
  face.ok = false
  faceManageOpen.value = false
  faceReplaceToken.value = ''
  status.warning = ''
  status.message = '已退出登录，请重新进行人脸识别。'
}

async function handleUpload(event) {
  const files = Array.from(event.target.files || [])
  event.target.value = ''
  if (!files.length) return
  if (files.length > maxUploadFiles) {
    status.warning = `一次最多上传 ${maxUploadFiles} 个文件，请分批选择。`
    return
  }
  const oversized = files.filter((file) => file.size > maxUploadBytes)
  if (oversized.length) {
    status.warning = `单个文件不能超过 25MB：${oversized.map((file) => file.name).join('、')}`
    return
  }
  const data = await runTask(`正在上传并切割 ${files.length} 个课程资料...`, () => uploadDocuments(files))
  if (data) {
    const documents = data.documents || []
    const errors = data.errors || []
    const totalChunks = documents.reduce((sum, doc) => sum + doc.chunk_count, 0)
    status.message = `已入库 ${documents.length} 个资料，共 ${totalChunks} 个片段。`
    status.warning = errors.length ? `部分文件未入库：${errors.map((item) => `${item.filename} ${item.message}`).join('；')}` : ''
    await refreshDocuments()
    if (documents.length) activeView.value = 'study'
  }
}

async function removeDocument(doc) {
  const data = await runTask(`正在删除 ${doc.filename}...`, () => deleteDocument(doc.id))
  if (data?.ok) {
    status.message = data.message
    await refreshDocuments()
    await refreshChapters()
    await loadWrongs()
    quizzes.value = []
    result.value = null
    activeView.value = 'library'
  }
}

async function removeAllDocuments() {
  const data = await runTask('正在清空资料库...', clearDocuments)
  if (data?.ok) {
    status.message = data.message
    documents.value = []
    chapters.value = []
    selectedChapterId.value = null
    quizzes.value = []
    result.value = null
    wrongs.value = []
    activeView.value = 'library'
  }
}

async function generateOutline() {
  const data = await runTask('正在通过 LangGraph 生成课程大纲...', () => createOutline(providerPayload()))
  if (data) {
    chapters.value = data.chapters
    selectedChapterId.value = chapters.value[0]?.id || null
    status.message = '课程大纲已生成，可继续生成章节学习内容。'
    activeView.value = 'study'
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
    activeView.value = 'quiz'
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

function providerPayload() {
  return {
    provider: config.provider,
    model: config.model,
    base_url: config.base_url,
    api_key: config.key_mode === 'manual' ? config.api_key : '',
    api_key_env: config.key_mode === 'env' ? config.api_key_env : '',
    langsmith_enabled: config.langsmith_enabled,
    prompt_templates: {
      outline: appSettings.prompts.outline,
      chapter: appSettings.prompts.chapter,
      quiz: appSettings.prompts.quiz
    }
  }
}

function loadSettings() {
  const raw = localStorage.getItem('ai-study-settings')
  if (!raw) return
  try {
    const saved = JSON.parse(raw)
    Object.assign(appSettings.prompts, saved.prompts || {})
  } catch {
    localStorage.removeItem('ai-study-settings')
  }
}

function saveSettings() {
  localStorage.setItem('ai-study-settings', JSON.stringify({ prompts: appSettings.prompts }))
  settingsOpen.value = false
  status.message = '系统设置已保存，后续 AI 生成会使用当前提示词模板。'
}

function resetPrompts() {
  Object.assign(appSettings.prompts, defaultPrompts)
  status.message = '提示词模板已恢复默认。'
}

function voiceGuard(message, view) {
  activeView.value = view
  status.warning = `无法执行：${message}`
  return { ok: false, message: `无法执行：${message}` }
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
  <FaceGate
    v-if="!face.ok || faceManageOpen"
    :loading="status.loading"
    :message="status.warning || status.message"
    :enrolled="faceProfileState.enrolled"
    :needs-upgrade="faceProfileState.needsUpgrade"
    :username="faceProfileState.username"
    :allow-reenroll="face.ok"
    @verify="verifyFace"
    @enroll="enrollFace"
    @cancel="faceManageOpen = false"
    @username-change="handleFaceUsernameChange"
  />
  <main v-else class="app-shell">
    <HeroHeader
      :face-ok="face.ok"
      :loading="status.loading"
      :listening="listening"
      :supported="supported"
      @manage-face="faceManageOpen = true"
      @voice="start"
      @logout="logout"
    />

    <section class="app-status">
      <div>
        <strong>{{ status.warning ? '需要处理' : '运行状态' }}</strong>
        <span :class="{ warning: status.warning }">{{ status.warning || status.message }}</span>
      </div>
      <div class="status-actions">
        <button @click="settingsOpen = true"><Settings :size="16" /> 系统设置</button>
        <button @click="activeView = 'settings'"><Settings :size="16" /> 模型设置</button>
      </div>
    </section>

    <DashboardMetrics
      :document-count="uniqueDocuments.length"
      :chapter-count="chapters.length"
      :progress="progress"
      :wrong-count="wrongs.length"
    />

    <nav class="app-nav" aria-label="功能导航">
      <button v-for="item in navItems" :key="item.id" :class="{ selected: activeView === item.id }" @click="activeView = item.id">
        <component :is="item.icon" :size="17" /> {{ item.label }}
      </button>
    </nav>

    <section class="content-frame">
      <KnowledgePanel
        v-if="activeView === 'library'"
        :documents="uniqueDocuments"
        :loading="status.loading"
        @upload="handleUpload"
        @delete="removeDocument"
        @clear="removeAllDocuments"
      />
      <StudyPanel
        v-if="activeView === 'study'"
        :chapters="chapters"
        :selected-chapter="selectedChapter"
        :selected-chapter-id="selectedChapterId"
        :loading="status.loading"
        @outline="generateOutline"
        @select="selectedChapterId = $event"
        @content="generateContent"
        @quiz="generateQuizForSelected"
        @wrong="activeView = 'quiz'"
      />
      <QuizPanel
        v-if="activeView === 'quiz'"
        :quizzes="quizzes"
        :answers="answers"
        :result="result"
        :wrongs="visibleWrongs"
        :loading="status.loading"
        @submit="submitCurrentQuiz"
      />
      <section v-if="activeView === 'voice'" class="voice-page">
        <header class="voice-hero">
          <div>
            <div class="eyebrow"><Radio :size="16" /> 语音工作台</div>
            <h2>说出指令，系统自动导航或执行</h2>
            <p>支持页面跳转、资料学习、测验复盘和模型切换；无法执行时会给出原因并带你到对应页面。</p>
          </div>
          <div class="voice-state" :class="{ active: listening || voiceStatus.testingMicrophone }">
            <span>{{ voiceModeText }}</span>
            <strong>{{ voiceStatus.matchedCommand || '等待命令' }}</strong>
          </div>
        </header>

        <section class="voice-console">
          <div class="voice-transcript">
            <MessageCircle :size="22" />
            <div>
              <strong>{{ transcript }}</strong>
              <span v-if="voiceDetail">{{ voiceDetail }}</span>
            </div>
          </div>
          <div class="voice-actions">
            <button class="primary" :class="{ active: listening }" :disabled="!supported" @click="start">
              <Mic :size="17" /> {{ listening ? '停止并处理语音' : '开始语音识别' }}
            </button>
            <button :disabled="voiceStatus.testingMicrophone" @click="testMicrophone"><Activity :size="17" /> 麦克风测试</button>
            <button :disabled="!voiceStatus.testingMicrophone" @click="stopMicrophoneTest">停止测试</button>
          </div>
        </section>

        <div class="voice-diagnostics">
          <article>
            <strong>麦克风</strong>
            <span>{{ voiceStatus.permission }} · {{ voiceStatus.deviceText }}</span>
          </article>
          <article>
            <strong>输入音量</strong>
            <span>{{ voiceStatus.volumeText }} · {{ voiceStatus.volume }}%</span>
            <div class="volume-meter"><i :style="{ width: `${voiceStatus.volume}%` }"></i></div>
          </article>
          <article>
            <strong>识别文本</strong>
            <span>{{ voiceStatus.lastText || '暂无' }}</span>
          </article>
          <article>
            <strong>执行状态</strong>
            <span>{{ voiceStatus.matchedCommand ? '已命中' : '未命中' }}</span>
          </article>
        </div>

        <div class="voice-command-board">
          <section v-for="group in VOICE_COMMAND_GROUPS" :key="group.title">
            <h3><Compass :size="17" /> {{ group.title }}</h3>
            <div class="voice-command-grid">
              <article v-for="command in group.items" :key="command.name">
                <div>
                  <CheckCircle2 :size="16" />
                  <strong>{{ command.name }}</strong>
                </div>
                <p>{{ command.description }}</p>
                <span>{{ command.keywords.slice(0, 3).join(' / ') }}</span>
              </article>
            </div>
          </section>
        </div>
      </section>
      <ProviderPanel
        v-if="activeView === 'settings'"
        :config="config"
        :status="status"
        :face-ok="face.ok"
        :provider-hint="providerHint"
        :model-placeholder="modelPlaceholder"
        :base-url-placeholder="baseUrlPlaceholder"
        :api-key-env-placeholder="apiKeyEnvPlaceholder"
        :cloud-models="cloudModels"
        :cloud-loading="cloudLoading"
        :test-message="testMessage"
        @test="runProviderTest"
        @load-cloud-models="loadCloudModels"
      />
    </section>
    <SettingsModal
      v-if="settingsOpen"
      :settings="appSettings"
      :default-prompts="defaultPrompts"
      @close="settingsOpen = false"
      @save="saveSettings"
      @reset="resetPrompts"
    />
  </main>
</template>
