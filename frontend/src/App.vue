<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { Activity, BookOpen, CheckCircle2, Compass, FolderOpen, MessageCircle, Mic, Radio, Settings, Trophy } from 'lucide-vue-next'
import DashboardMetrics from './components/DashboardMetrics.vue'
import FaceGate from './components/FaceGate.vue'
import HeroHeader from './components/HeroHeader.vue'
import KnowledgePanel from './components/KnowledgePanel.vue'
import NextActionCard from './components/NextActionCard.vue'
import ProviderPanel from './components/ProviderPanel.vue'
import QuizPanel from './components/QuizPanel.vue'
import SettingsModal from './components/SettingsModal.vue'
import StudyPanel from './components/StudyPanel.vue'
import {
  cancelInitialization,
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
  listQuiz,
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
  provider: 'openai_compatible',
  model: 'deepseek-chat',
  base_url: 'https://api.deepseek.com/v1',
  key_mode: 'env',
  api_key: '',
  api_key_env: 'DEEPSEEK_API_KEY',
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
const voiceCommandQuery = ref('')
const courseBootstrapping = ref(false)
const initializationStep = ref('')
const face = reactive({ ok: false })
const faceProfileState = reactive({ enrolled: false, username: '杨翰飞', needsUpgrade: false })
const faceManageOpen = ref(false)
const settingsOpen = ref(false)
const faceReplaceToken = ref('')
const maxUploadBytes = 25 * 1024 * 1024
const maxUploadFiles = 20
const promptVersion = 3
let faceProfileLookupId = 0
let initializationController = null
let activeInitializationId = ''

const defaultPrompts = {
  outline:
    '你是一个严谨的课程学习路径设计师。\n\n请基于给定课程资料，为学生设计一套系统化学习大纲。大纲要能覆盖资料的主要知识结构，而不是只概括前几页内容。\n\n资料规模信息：\n- 建议章节数量：{{chapter_count}} 章\n\n生成要求：\n1. 严格输出 {{chapter_count}} 行。\n2. 每行只表示一个学习章节。\n3. 每行格式必须为：章节标题 - 学习目标\n4. 章节标题要简洁明确，适合作为学习路径卡片标题。\n5. 学习目标要具体，说明学生学完本章应该掌握什么。\n6. 章节之间要有递进关系，从基础概念到实践应用，再到总结提升。\n7. 如果资料中存在目录、章节标题、学习路线图，请优先参考原资料结构。\n8. 不要只生成泛泛的“概述、基础、应用、总结”四类标题。\n9. 不要输出寒暄语。\n10. 不要输出“好的”“下面是”“这是为你生成的”等说明。\n11. 不要输出 Markdown 代码块。\n12. 不要输出额外解释。\n\n课程资料：\n{{context}}',
  chapter:
    '你是一个专业的课程章节讲义生成器。\n\n请严格基于课程资料，为章节《{{chapter_title}}》生成一份可以直接展示给学生学习的 Markdown 讲义。\n\n章节目标：\n{{chapter_objective}}\n\n内容质量要求：\n1. 内容必须有实际学习价值，不能只是几句话概括。\n2. 内容应当适合学生自学，讲解要清楚、分层、有逻辑。\n3. 要结合资料中的术语、概念、例子、章节结构，不要泛泛而谈。\n4. 对于教材类资料，应尽量还原教材知识脉络。\n5. 不要编造资料中完全没有的具体页码、作者观点或代码细节。\n6. 可以适度补充通用解释，但必须服务于理解资料内容。\n7. 输出内容建议不少于 900 个中文字符；如果资料上下文足够，建议 1200~1800 个中文字符。\n8. 不要输出寒暄语。\n9. 不要输出“好的”“下面是”“这是为你生成的”“以下内容”等开场白。\n10. 不要重复章节标题和章节目标。\n11. 不要使用 Markdown 代码围栏。\n\n输出结构必须包含以下二级标题：\n\n## 学习目标\n用 3~5 条项目符号说明本章学完后应掌握的能力。\n\n## 核心概念\n解释本章最重要的概念。每个概念都要有简明解释，不能只列名词。\n\n## 知识讲解\n按照由浅入深的方式展开说明。必要时使用有序列表、小标题和加粗突出重点。\n\n## 典型例子或应用场景\n结合资料内容说明这些知识可以解决什么问题，或者在实际项目中如何使用。\n\n## 重点难点\n列出本章容易混淆、容易忽视、需要重点理解的地方。\n\n## 易错点提醒\n列出学生学习或答题时容易犯的错误，并说明原因。\n\n## 本章小结\n用简洁语言总结本章核心内容。\n\n## 复盘建议\n给出学生复习本章时可以采用的方法，例如画图、对比、做题、复述、代码实践等。\n\n课程资料：\n{{context}}',
  quiz:
    '你是一个严谨的课程测验出题器。\n\n请严格基于课程资料和章节学习目标，为章节《{{chapter_title}}》生成一组用于检测学习成果的测验题。\n\n章节目标：\n{{chapter_objective}}\n\n出题要求：\n1. 生成 10 道单选题。\n2. 每题 4 个选项。\n3. 题目必须覆盖本章主要知识点，不要集中考同一个概念。\n4. 题目需要有难度层级：3 道基础记忆题、3 道概念理解题、2 道应用分析题、1 道易错辨析题、1 道拓展思考题。\n5. 选项不能过于明显，错误选项要有一定迷惑性。\n6. 正确答案必须与 options 中某一项完全一致。\n7. explanation 必须解释为什么正确，以及为什么其他选项不合适。\n8. 不要输出 Markdown 代码块。\n9. 不要输出任何解释文字。\n10. 只输出合法 JSON 数组。\n\nJSON 对象必须包含 type、difficulty、question、options、answer、explanation。\n\n课程资料：\n{{context}}'
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
const nextAction = computed(() => {
  if (courseBootstrapping.value) {
    return {
      title: '正在初始化课程',
      description: status.message || '正在初始化课程，请勿重复点击。',
      action: '初始化中',
      view: 'study',
      task: 'navigate',
      disabled: true
    }
  }
  if (!uniqueDocuments.value.length) {
    return {
      title: '先上传课程资料',
      description: '资料入库后，系统才能生成学习路径、章节内容和测验。',
      action: '上传资料',
      view: 'library',
      task: 'navigate'
    }
  }
  if (!chapters.value.length) {
    return {
      title: '初始化课程',
      description: '确认资料上传完成后，一次生成大纲、章节内容和测验。',
      action: '生成学习路径',
      view: 'library',
      task: 'initialize'
    }
  }
  if (!chapters.value.some((chapter) => chapter.content)) {
    return {
      title: '继续初始化课程',
      description: '当前课程还缺少章节内容，点击后补齐内容和测验。',
      action: '继续初始化',
      view: 'library',
      task: 'initialize'
    }
  }
  if (!quizzes.value.length || !result.value) {
    return {
      title: '开始章节测验',
      description: quizzes.value.length ? '测验已生成，请完成作答。' : '用测验检查掌握情况，错题会自动进入复盘。',
      action: quizzes.value.length ? '打开测验' : '生成测验',
      view: 'quiz',
      task: quizzes.value.length ? 'navigate' : 'quiz',
      secondary: '学习路径'
    }
  }
  return {
    title: wrongs.value.length ? '复盘错题' : '继续保持学习节奏',
    description: wrongs.value.length ? '查看错题解析，定位薄弱知识点。' : '当前暂无错题，可以继续学习下一章。',
    action: wrongs.value.length ? '查看错题' : '打开测验',
    view: 'quiz',
    task: 'navigate',
    secondary: '学习路径'
  }
})
const providerHint = computed(() => providerDefaults[config.provider].hint)
const modelPlaceholder = computed(() => providerDefaults[config.provider].model)
const baseUrlPlaceholder = computed(() => providerDefaults[config.provider].base_url || '无需填写')
const apiKeyEnvPlaceholder = computed(() => providerDefaults[config.provider].api_key_env || '环境变量名')

const {
  listening,
  supported,
  transcript,
  voiceStatus,
  audioInputs,
  selectedInputDeviceId,
  start,
  testMicrophone,
  stopMicrophoneTest,
  refreshMicrophoneState,
  selectInputDevice
} = useVoiceCommands({
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
  initialize: () => {
    if (!documents.value.length) return voiceGuard('请先上传课程资料，再初始化课程。', 'library')
    void initializeCourse()
    return { message: '正在初始化课程。' }
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
const recommendedVoiceCommands = computed(() =>
  VOICE_COMMAND_GROUPS.flatMap((group) => group.items).filter((command) =>
    ['上传资料', '初始化课程', '开始测验', '查看错题', '模型设置', '麦克风测试'].includes(command.name)
  )
)
const filteredVoiceGroups = computed(() => {
  const keyword = voiceCommandQuery.value.trim().toLowerCase()
  return VOICE_COMMAND_GROUPS.map((group) => ({
    ...group,
    items: keyword
      ? group.items.filter((command) =>
          [command.name, command.description, ...command.keywords].some((item) => item.toLowerCase().includes(keyword))
        )
      : group.items
  })).filter((group) => group.items.length)
})

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
    if (documents.length) {
      activeView.value = 'library'
      status.message = `${status.message} 请确认资料无误后点击“生成课程学习路径”。`
    }
  }
}

function createInitializationId() {
  const randomPart =
    typeof crypto !== 'undefined' && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`
  return `init-${randomPart}`
}

function ensureInitializationActive(initializationId) {
  if (initializationId !== activeInitializationId || initializationController?.signal.aborted) {
    throw new Error('课程初始化已暂停。')
  }
}

async function pauseInitialization() {
  if (!courseBootstrapping.value || !activeInitializationId) return
  const pausedId = activeInitializationId
  initializationController?.abort()
  status.message = '正在暂停初始化并清理本次生成内容。'
  try {
    await cancelInitialization(pausedId)
  } catch (error) {
    status.warning = `暂停清理失败：${error.message}`
  } finally {
    activeInitializationId = ''
    initializationStep.value = ''
    courseBootstrapping.value = false
    status.loading = false
    chapters.value = []
    selectedChapterId.value = null
    quizzes.value = []
    result.value = null
    wrongs.value = []
    Object.keys(answers).forEach((key) => delete answers[key])
    await refreshChapters()
    await loadWrongs()
    status.message = '已暂停初始化，本次生成的大纲、章节内容和测验已清空。'
  }
}

async function initializeCourse() {
  if (!uniqueDocuments.value.length) {
    status.warning = '请先上传课程资料，再初始化课程。'
    activeView.value = 'library'
    return
  }
  if (chapters.value.length) {
    const confirmed = window.confirm('重新初始化会基于当前资料重建大纲、章节内容和测验，并清空已有测验记录。确认继续？')
    if (!confirmed) return
  }
  const initializationId = createInitializationId()
  activeInitializationId = initializationId
  initializationController = new AbortController()
  courseBootstrapping.value = true
  status.loading = true
  activeView.value = 'study'
  try {
    status.message = '正在根据当前资料初始化课程。'
    initializationStep.value = '正在生成课程大纲'
    status.message = initializationStep.value
    const outline = await createOutline(providerPayload(initializationId), { signal: initializationController.signal })
    ensureInitializationActive(initializationId)
    if (outline?.warning) status.warning = outline.warning
    let currentChapters = outline?.chapters || []
    chapters.value = currentChapters
    selectedChapterId.value = currentChapters[0]?.id || null
    for (let index = 0; index < currentChapters.length; index += 1) {
      const chapter = currentChapters[index]
      if (!chapter.content) {
        initializationStep.value = `正在生成第 ${index + 1}/${currentChapters.length} 章学习内容`
        status.message = `${initializationStep.value}。`
        const content = await createChapterContent(chapter.id, providerPayload(initializationId), {
          signal: initializationController.signal
        })
        ensureInitializationActive(initializationId)
        if (content?.warning) status.warning = content.warning
        const targetIndex = chapters.value.findIndex((item) => item.id === chapter.id)
        if (targetIndex >= 0) chapters.value[targetIndex] = content.chapter
        currentChapters[index] = content.chapter
      }
      ensureInitializationActive(initializationId)
      initializationStep.value = `正在检查第 ${index + 1}/${currentChapters.length} 章测验`
      status.message = `${initializationStep.value}。`
      const existingQuiz = await listQuiz(chapter.id).catch(() => ({ quizzes: [] }))
      if (!existingQuiz.quizzes?.length) {
        ensureInitializationActive(initializationId)
        initializationStep.value = `正在生成第 ${index + 1}/${currentChapters.length} 章测验`
        status.message = `${initializationStep.value}。`
        const quiz = await createQuiz(chapter.id, providerPayload(initializationId), { signal: initializationController.signal })
        ensureInitializationActive(initializationId)
        if (quiz?.warning) status.warning = quiz.warning
        if (index === 0) quizzes.value = quiz.quizzes || []
      } else if (index === 0) {
        quizzes.value = existingQuiz.quizzes
      }
    }
    selectedChapterId.value = currentChapters[0]?.id || null
    if (selectedChapterId.value && !quizzes.value.length) {
      const firstQuiz = await listQuiz(selectedChapterId.value).catch(() => ({ quizzes: [] }))
      quizzes.value = firstQuiz.quizzes || []
    }
    result.value = null
    Object.keys(answers).forEach((key) => delete answers[key])
    activeView.value = 'study'
    status.message = '课程初始化完成，可直接学习章节内容或开始测验。'
  } catch (error) {
    if (initializationController?.signal.aborted || !activeInitializationId) {
      status.warning = ''
    } else {
      status.warning = `课程初始化中断：${error.message}`
    }
  } finally {
    if (activeInitializationId === initializationId) {
      activeInitializationId = ''
      courseBootstrapping.value = false
      status.loading = false
      initializationStep.value = ''
      initializationController = null
    }
  }
}

async function removeDocument(doc) {
  if (!window.confirm(`确认删除资料“${doc.filename}”？删除后会同步清理学习大纲、测验和错题记录。`)) return
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
  if (!window.confirm('确认清空资料库？该操作会同步清理学习大纲、测验和错题记录。')) return
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

async function handleNextAction() {
  if (nextAction.value.disabled) return
  activeView.value = nextAction.value.view
  if (nextAction.value.task === 'outline') {
    await generateOutline()
  } else if (nextAction.value.task === 'initialize') {
    await initializeCourse()
  } else if (nextAction.value.task === 'content') {
    if (!selectedChapterId.value && chapters.value[0]) selectedChapterId.value = chapters.value[0].id
    if (selectedChapter.value) await generateContent(selectedChapter.value)
  } else if (nextAction.value.task === 'quiz') {
    await generateQuizForSelected()
  }
}

function handleNextSecondary() {
  activeView.value = 'study'
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

async function retryCurrentQuiz() {
  Object.keys(answers).forEach((key) => delete answers[key])
  result.value = null
  if (selectedChapter.value) await generateQuizForSelected()
}

function studyNextChapter() {
  if (!chapters.value.length || !selectedChapter.value) {
    activeView.value = 'study'
    return
  }
  const index = chapters.value.findIndex((chapter) => chapter.id === selectedChapter.value.id)
  const next = chapters.value[index + 1]
  if (next) {
    selectedChapterId.value = next.id
    activeView.value = 'study'
    status.message = `已切换到下一章《${next.title}》。`
  } else {
    activeView.value = 'study'
    status.message = '已经是最后一章，请复盘错题并整理课程总结。'
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

function providerPayload(initializationId = '') {
  ensurePromptCompatibility()
  return {
    provider: config.provider,
    model: config.model,
    base_url: config.base_url,
    api_key: config.key_mode === 'manual' ? config.api_key : '',
    api_key_env: config.key_mode === 'env' ? config.api_key_env : '',
    langsmith_enabled: config.langsmith_enabled,
    initialization_id: initializationId,
    prompt_templates: {
      outline: appSettings.prompts.outline,
      chapter: appSettings.prompts.chapter,
      quiz: appSettings.prompts.quiz
    }
  }
}

function ensurePromptCompatibility() {
  if (!appSettings.prompts.outline.includes('{{chapter_count}}')) {
    appSettings.prompts.outline = defaultPrompts.outline
  }
  if (/生成\s*3\s*道|3\s*道单选题/.test(appSettings.prompts.quiz)) {
    appSettings.prompts.quiz = defaultPrompts.quiz
  }
}

function loadSettings() {
  const raw = localStorage.getItem('ai-study-settings')
  if (!raw) return
  try {
    const saved = JSON.parse(raw)
    if (saved.promptVersion !== promptVersion) {
      localStorage.setItem('ai-study-settings', JSON.stringify({ promptVersion, prompts: appSettings.prompts }))
      return
    }
    Object.assign(appSettings.prompts, saved.prompts || {})
  } catch {
    localStorage.removeItem('ai-study-settings')
  }
}

function saveSettings() {
  localStorage.setItem('ai-study-settings', JSON.stringify({ promptVersion, prompts: appSettings.prompts }))
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
        <button v-if="courseBootstrapping" class="danger-soft" @click="pauseInitialization">暂停初始化</button>
        <button @click="settingsOpen = true"><Settings :size="16" /> 系统设置</button>
        <button @click="activeView = 'settings'"><Settings :size="16" /> 模型设置</button>
      </div>
    </section>

    <NextActionCard
      :title="nextAction.title"
      :description="nextAction.description"
      :action="nextAction.action"
      :secondary="nextAction.secondary"
      :disabled="nextAction.disabled"
      @primary="handleNextAction"
      @secondary="handleNextSecondary"
    />

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
        :initializing="courseBootstrapping"
        :initialization-step="initializationStep"
        @upload="handleUpload"
        @delete="removeDocument"
        @clear="removeAllDocuments"
        @initialize="initializeCourse"
        @pause="pauseInitialization"
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
        @study="activeView = 'study'"
        @review="activeView = 'quiz'"
        @retry="retryCurrentQuiz"
        @next="studyNextChapter"
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
          <article class="voice-device-card">
            <strong>麦克风</strong>
            <span>{{ voiceStatus.permission }} · {{ voiceStatus.deviceText }}</span>
            <select
              :value="selectedInputDeviceId"
              :disabled="!audioInputs.length"
              aria-label="选择麦克风输入设备"
              @change="selectInputDevice($event.target.value)"
            >
              <option v-if="!audioInputs.length" value="">未发现输入设备</option>
              <option v-for="device in audioInputs" :key="device.deviceId" :value="device.deviceId">
                {{ device.label }}
              </option>
            </select>
            <small>麦克风测试和音量监测使用所选设备；语音识别由浏览器服务接管。</small>
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
          <section class="voice-recommend">
            <h3><Compass :size="17" /> 推荐指令</h3>
            <div class="command-chips">
              <span v-for="command in recommendedVoiceCommands" :key="command.name">{{ command.name }}</span>
            </div>
            <input v-model="voiceCommandQuery" class="command-search" placeholder="搜索指令，例如：测验、模型、麦克风" />
          </section>
          <section v-for="group in filteredVoiceGroups" :key="group.title">
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
