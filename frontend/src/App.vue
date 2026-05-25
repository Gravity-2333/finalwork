<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import {
  Bot,
  BrainCircuit,
  CheckCircle2,
  FileUp,
  Mic,
  Play,
  RefreshCw,
  ScanFace,
  ShieldAlert,
  Sparkles,
  Trophy
} from 'lucide-vue-next'
import {
  createChapterContent,
  createOutline,
  createQuiz,
  faceLogin,
  health,
  listDocuments,
  listWrongAnswers,
  seedDocument,
  submitQuiz,
  uploadDocument
} from './api'
import { useVoiceCommands } from './useVoice'

const status = reactive({
  loading: false,
  message: '系统已就绪，可先载入示例资料或上传课程资料。',
  warning: ''
})

const config = reactive({
  provider: 'mock',
  model: '',
  base_url: '',
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
const face = reactive({
  ok: false,
  message: '请完成人脸核验后进入学习工作台。',
  cameraReady: 'mediaDevices' in navigator
})

const providerDefaults = {
  mock: {
    model: 'mock-assistant',
    base_url: '本地演示，无需地址',
    hint: 'Mock Provider 可离线演示完整学习流程。'
  },
  local_ollama: {
    model: 'qwen2.5:7b',
    base_url: 'http://localhost:11434',
    hint: '本地 Ollama 默认连接 http://localhost:11434，无需 API Key。'
  },
  cloud_ollama: {
    model: 'qwen2.5:7b',
    base_url: 'https://your-ollama.example.com/v1',
    hint: '云端 Ollama 使用 OpenAI-compatible 接口，API Key 从 OLLAMA_API_KEY 读取。'
  },
  deepseek: {
    model: 'deepseek-chat',
    base_url: 'https://api.deepseek.com/v1',
    hint: 'DeepSeek API Key 从 DEEPSEEK_API_KEY 读取。'
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

const providerHint = computed(() => {
  if (config.provider === 'deepseek' && !env.deepseek_key_ready) return '未检测到 DEEPSEEK_API_KEY，调用时会自动使用 Mock fallback。'
  if (config.provider === 'cloud_ollama' && !env.ollama_key_ready) return '未检测到 OLLAMA_API_KEY，云端 Ollama 将友好降级。'
  return providerDefaults[config.provider].hint
})
const modelPlaceholder = computed(() => providerDefaults[config.provider].model)
const baseUrlPlaceholder = computed(() => providerDefaults[config.provider].base_url)

const { listening, supported, transcript, start } = useVoiceCommands({
  seed: loadSample,
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
  await loadWrongs()
  const params = new URLSearchParams(window.location.search)
  if (params.get('demo') === '1') {
    await demoFlow()
  }
})

watch(
  () => config.provider,
  () => applyProviderDefaults()
)

async function runTask(message, task) {
  status.loading = true
  status.message = message
  status.warning = ''
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

async function verifyFace() {
  const data = await runTask('正在进行人脸核验...', faceLogin)
  if (data?.ok) {
    face.ok = true
    face.message = data.message
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

async function loadSample() {
  const data = await runTask('正在载入示例课程资料...', seedDocument)
  if (data) {
    status.message = `示例资料已就绪，共 ${data.document.chunk_count} 个片段。`
    await refreshDocuments()
  }
}

async function generateOutline() {
  const data = await runTask('正在通过 LangGraph 生成课程大纲...', () => createOutline(config))
  if (data) {
    chapters.value = data.chapters
    selectedChapterId.value = chapters.value[0]?.id || null
    status.message = '课程大纲已生成，可继续生成章节学习内容。'
  }
}

async function generateContent(chapter) {
  const data = await runTask(`正在生成《${chapter.title}》学习内容...`, () => createChapterContent(chapter.id, config))
  if (data) {
    const index = chapters.value.findIndex((item) => item.id === chapter.id)
    chapters.value[index] = data.chapter
    selectedChapterId.value = chapter.id
    status.message = '章节内容已生成，学习进度已记录。'
  }
}

async function generateQuizForSelected() {
  if (!selectedChapter.value) return
  const data = await runTask('正在生成在线测验...', () => createQuiz(selectedChapter.value.id, config))
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

async function demoFlow() {
  await verifyFace()
  if (!documents.value.length) await loadSample()
  await generateOutline()
  if (selectedChapter.value) await generateContent(selectedChapter.value)
  await generateQuizForSelected()
}

function applyProviderDefaults() {
  const defaults = providerDefaults[config.provider]
  const knownModels = Object.values(providerDefaults).map((item) => item.model)
  const knownBaseUrls = Object.values(providerDefaults).map((item) => item.base_url)
  if (!config.model || knownModels.includes(config.model)) {
    config.model = defaults.model
  }
  if (!config.base_url || knownBaseUrls.includes(config.base_url)) {
    config.base_url = defaults.base_url
  }
}
</script>

<template>
  <main class="app-shell">
    <section class="hero">
      <div class="hero-copy">
        <div class="eyebrow"><BrainCircuit :size="17" /> LangChain · LangGraph · 可选 LangSmith</div>
        <h1>AI 学习助手</h1>
        <p>把课程资料转成可学习、可测验、可复盘的个人知识库。</p>
      </div>
      <div class="hero-actions">
        <button :class="['face-button', { verified: face.ok }]" :disabled="status.loading" @click="verifyFace">
          <ScanFace :size="18" /> {{ face.ok ? '已核验' : '人脸核验' }}
        </button>
        <button :class="{ active: listening }" :disabled="!supported" @click="start">
          <Mic :size="18" /> 语音控制
        </button>
      </div>
    </section>

    <section class="provider-panel">
      <div class="runtime-state">
        <span :class="['state-dot', face.ok ? 'ok' : '']"></span>
        <strong>{{ face.ok ? '已登录' : '待核验' }}</strong>
        <small>{{ status.message }}</small>
      </div>
      <div class="provider-fields">
        <label>
          <span>模型来源</span>
          <select v-model="config.provider">
            <option value="mock">Mock</option>
            <option value="local_ollama">本地 Ollama</option>
            <option value="cloud_ollama">云端 Ollama</option>
            <option value="deepseek">DeepSeek</option>
          </select>
        </label>
        <label>
          <span>模型</span>
          <input v-model="config.model" :placeholder="modelPlaceholder" />
        </label>
        <label>
          <span>地址</span>
          <input v-model="config.base_url" :placeholder="baseUrlPlaceholder" />
        </label>
        <label class="toggle">
          <input v-model="config.langsmith_enabled" type="checkbox" />
          追踪
        </label>
      </div>
      <p :class="{ warning: status.warning }">
        <ShieldAlert v-if="status.warning" :size="16" />
        <Bot v-else :size="16" />
        {{ status.warning || providerHint }}
      </p>
    </section>

    <section class="dashboard">
      <div class="metric">
        <strong>{{ uniqueDocuments.length }}</strong>
        <span>知识库资料</span>
      </div>
      <div class="metric">
        <strong>{{ chapters.length }}</strong>
        <span>学习章节</span>
      </div>
      <div class="metric">
        <strong>{{ progress }}%</strong>
        <span>整体进度</span>
      </div>
      <div class="metric">
        <strong>{{ wrongs.length }}</strong>
        <span>错题归档</span>
      </div>
    </section>

    <section class="workspace">
      <aside class="side-panel">
        <div class="panel-title">
          <FileUp :size="19" />
          <h2>资料与知识库</h2>
        </div>
        <label class="upload-box">
          <input type="file" accept=".txt,.md,.docx,.pdf" @change="handleUpload" />
          <span>上传课程资料</span>
          <small>支持 txt / md / docx / pdf</small>
        </label>
        <button class="ghost" @click="loadSample"><Sparkles :size="17" /> 载入示例资料</button>
        <div class="doc-list">
          <article v-for="doc in uniqueDocuments" :key="doc.id">
            <strong>{{ doc.filename }}</strong>
            <span>{{ doc.chunk_count }} 个切片 · 已入库</span>
          </article>
          <p v-if="!uniqueDocuments.length" class="empty">暂无资料，先上传或载入示例。</p>
        </div>
      </aside>

      <section class="main-panel">
        <div class="toolbar">
          <button class="primary" :disabled="status.loading" @click="generateOutline">
            <RefreshCw :size="17" /> 生成课程大纲
          </button>
          <button :disabled="!selectedChapter" @click="generateQuizForSelected">
            <Play :size="17" /> 开始测验
          </button>
          <button @click="loadWrongs"><Trophy :size="17" /> 查看错题</button>
        </div>

        <div class="chapter-grid">
          <article
            v-for="chapter in chapters"
            :key="chapter.id"
            :class="['chapter-card', { selected: chapter.id === selectedChapterId }]"
            @click="selectedChapterId = chapter.id"
          >
            <div>
              <h3>{{ chapter.title }}</h3>
              <p>{{ chapter.objective }}</p>
            </div>
            <div class="progress-line"><span :style="{ width: `${chapter.progress}%` }"></span></div>
            <button @click.stop="generateContent(chapter)">生成学习内容</button>
          </article>
        </div>

        <div v-if="!chapters.length" class="empty-state">
          <BrainCircuit :size="34" />
          <h2>从知识库生成学习路径</h2>
          <p>载入资料后点击“生成课程大纲”，系统会创建章节、学习目标和后续测验入口。</p>
          <button class="primary" @click="generateOutline"><RefreshCw :size="17" /> 生成课程大纲</button>
        </div>

        <article v-if="selectedChapter" class="content-panel">
          <h2>{{ selectedChapter.title }}</h2>
          <p class="objective">{{ selectedChapter.objective }}</p>
          <pre>{{ selectedChapter.content || '点击“生成学习内容”，系统将结合知识库生成本章学习材料。' }}</pre>
        </article>
      </section>

      <aside class="quiz-panel">
        <div class="panel-title">
          <Trophy :size="19" />
          <h2>测验与错题</h2>
        </div>
        <div v-if="quizzes.length" class="quiz-list">
          <article v-for="quiz in quizzes" :key="quiz.id">
            <h3>{{ quiz.question }}</h3>
            <label v-for="option in quiz.options" :key="option">
              <input v-model="answers[quiz.id]" type="radio" :name="`quiz-${quiz.id}`" :value="option" />
              {{ option }}
            </label>
          </article>
          <button class="primary" @click="submitCurrentQuiz">提交测验</button>
          <p v-if="result" class="score">得分 {{ result.score }} / {{ result.total }}</p>
        </div>
        <p v-else class="empty">选择章节后点击“开始测验”。</p>

        <div class="wrong-list">
          <h3>错题归档</h3>
          <article v-for="item in visibleWrongs" :key="item.id">
            <strong>{{ item.chapter_title }}</strong>
            <p>{{ item.question }}</p>
            <small>你的答案：{{ item.selected || '未选择' }}；正确答案：{{ item.answer }}</small>
          </article>
          <p v-if="!wrongs.length" class="empty">暂无错题，完成测验后自动记录。</p>
        </div>
      </aside>
    </section>

    <section class="voice-strip">
      <Mic :size="18" />
      <span>语音识别：{{ transcript }}</span>
      <small>可说“生成大纲”“开始测验”“查看错题”“切换 mock 模型”。</small>
    </section>
  </main>
</template>
