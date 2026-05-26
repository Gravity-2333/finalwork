import { reactive, ref } from 'vue'

const COMMANDS = [
  { name: '上传资料', keywords: ['上传资料', '上传文件', '添加资料', '资料上传'], action: 'upload', type: 'navigate', description: '打开知识库上传区。' },
  { name: '打开知识库', keywords: ['知识库', '资料库'], action: 'library', type: 'navigate', description: '查看已上传资料。' },
  { name: '打开学习路径', keywords: ['学习路径', '课程大纲页面', '章节页面'], action: 'study', type: 'navigate', description: '查看大纲和章节内容。' },
  { name: '打开测验复盘', keywords: ['测验复盘', '测验页面', '考试页面'], action: 'quizPage', type: 'navigate', description: '查看测验与错题。' },
  { name: '查看错题', keywords: ['查看错题', '错题', '复盘'], action: 'wrong', type: 'navigate', description: '跳转到错题归档。' },
  { name: '模型设置', keywords: ['模型设置', '模型配置'], action: 'settings', type: 'navigate', description: '打开模型 Provider 配置。' },
  { name: '系统设置', keywords: ['系统设置', '提示词设置', '打开设置'], action: 'systemSettings', type: 'navigate', description: '打开资料处理和提示词设置。' },
  { name: '生成课程大纲', keywords: ['生成大纲', '生成课程大纲', '创建大纲'], action: 'outline', type: 'execute', description: '有资料时自动生成学习大纲。' },
  { name: '生成章节内容', keywords: ['生成章节', '生成内容', '学习内容'], action: 'content', type: 'execute', description: '为当前章节生成学习内容。' },
  { name: '开始测验', keywords: ['开始测验', '生成测验', '开始考试', '出题'], action: 'quiz', type: 'execute', description: '为当前章节生成测验题。' },
  { name: '测试模型连接', keywords: ['测试模型', '测试连接', '模型测试'], action: 'providerTest', type: 'execute', description: '打开模型设置并测试连接。' },
  { name: '获取云端模型', keywords: ['获取云端模型', '刷新模型列表', '模型列表'], action: 'cloudModels', type: 'execute', description: '获取并测试云端 Ollama 模型。' },
  { name: '麦克风测试', keywords: ['麦克风测试', '测试麦克风', '检查麦克风'], action: 'microphoneTest', type: 'execute', description: '检测麦克风权限和音量。' },
  { name: '切换 Mock 模型', keywords: ['切换mock', '切换 mock', 'mock模型', 'mock 模型'], action: 'mock', type: 'execute', description: '切换到离线演示模型。' },
  { name: '切换本地 Ollama', keywords: ['本地ollama', '本地 ollama'], action: 'localOllama', type: 'execute', description: '切换到本地 Ollama。' },
  { name: '切换云端 Ollama', keywords: ['云端ollama', '云端 ollama'], action: 'cloudOllama', type: 'execute', description: '切换到云端 Ollama。' },
  { name: '切换兼容模型', keywords: ['兼容模型', 'deepseek', '切换deepseek'], action: 'openaiCompatible', type: 'execute', description: '切换到 OpenAI 兼容接口。' }
]

export const VOICE_COMMAND_GROUPS = [
  { title: '页面跳转', items: COMMANDS.filter((command) => command.type === 'navigate') },
  { title: '自动执行', items: COMMANDS.filter((command) => command.type === 'execute') }
]

export function useVoiceCommands(handlers) {
  const listening = ref(false)
  const supported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
  const transcript = ref(supported ? '语音待命' : '当前浏览器不支持语音识别，可使用按钮完成相同操作。')
  const voiceStatus = reactive({
    permission: '未测试',
    volume: 0,
    volumeText: '未测试',
    lastText: '',
    matchedCommand: '',
    diagnostic: supported ? '点击开始语音识别或麦克风测试。' : '浏览器不支持 Web Speech API。',
    testingMicrophone: false,
    deviceText: '未检测'
  })

  let recognition = null
  let lastFinalText = ''
  let lastRecognizedText = ''
  let audioContext = null
  let audioStream = null
  let audioTimer = null
  let audioStopTimer = null

  refreshMicrophoneState()

  function start() {
    if (!supported) return
    if (listening.value) {
      stop(true)
      return
    }
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    recognition = new Recognition()
    recognition.lang = 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = true
    listening.value = true
    lastFinalText = ''
    lastRecognizedText = ''
    transcript.value = '正在聆听，请说出命令...'
    voiceStatus.diagnostic = '正在监听，识别到命令会自动停止并执行。'
    recognition.onresult = (event) => {
      let interim = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const text = event.results[index][0].transcript.trim()
        if (event.results[index].isFinal) {
          lastFinalText = text
          voiceStatus.lastText = text
        } else {
          interim = text
        }
      }
      const currentText = lastFinalText || interim
      if (currentText) {
        lastRecognizedText = currentText
        voiceStatus.lastText = currentText
        transcript.value = currentText
        const matched = matchCommand(currentText)
        if (matched) {
          voiceStatus.matchedCommand = matched.name
          voiceStatus.diagnostic = `已识别命令：${matched.name}`
          void executeCommand(matched)
          stop(false)
        }
      }
    }
    recognition.onerror = (event) => {
      const reason = speechErrorMessage(event.error)
      transcript.value = reason
      voiceStatus.diagnostic = reason
      listening.value = false
    }
    recognition.onend = () => {
      listening.value = false
      recognition = null
    }
    try {
      recognition.start()
    } catch {
      listening.value = false
      transcript.value = '语音识别启动失败，请稍后重试。'
      voiceStatus.diagnostic = '语音识别启动失败，可能是浏览器正在占用识别会话。'
    }
  }

  function stop(processLastText = true) {
    const textToProcess = lastFinalText || lastRecognizedText
    if (processLastText && textToProcess) {
      const matched = matchCommand(textToProcess)
      if (matched) {
        voiceStatus.matchedCommand = matched.name
        voiceStatus.diagnostic = `停止时执行命令：${matched.name}`
        void executeCommand(matched)
      } else {
        voiceStatus.diagnostic = '已停止，但最后一句没有命中命令。'
      }
    } else if (processLastText) {
      voiceStatus.diagnostic = '已停止，但没有识别到有效语音。'
    }
    if (recognition) recognition.stop()
    listening.value = false
    transcript.value = textToProcess || '语音已停止'
  }

  async function testMicrophone() {
    if (voiceStatus.testingMicrophone) {
      voiceStatus.diagnostic = '麦克风测试正在进行。'
      return
    }
    if (listening.value) stop(false)
    if (!navigator.mediaDevices?.getUserMedia) {
      voiceStatus.permission = '不可用'
      voiceStatus.diagnostic = '当前环境不支持麦克风访问。'
      return
    }
    try {
      stopMicrophoneTest()
      voiceStatus.testingMicrophone = true
      voiceStatus.permission = '请求中'
      voiceStatus.volume = 0
      voiceStatus.volumeText = '等待输入'
      voiceStatus.diagnostic = '正在请求浏览器麦克风权限。'
      await refreshMicrophoneState()
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })
      await refreshMicrophoneState()
      voiceStatus.permission = '已授权'
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      if (!AudioContextClass) {
        throw new Error('当前浏览器不支持 AudioContext，无法读取麦克风音量。')
      }
      audioContext = new AudioContextClass()
      if (audioContext.state === 'suspended') await audioContext.resume()
      const source = audioContext.createMediaStreamSource(audioStream)
      const analyser = audioContext.createAnalyser()
      analyser.fftSize = 2048
      source.connect(analyser)
      const data = new Uint8Array(analyser.fftSize)
      clearInterval(audioTimer)
      audioTimer = setInterval(() => {
        analyser.getByteTimeDomainData(data)
        const rms = Math.sqrt(data.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / data.length)
        const volume = Math.min(100, Math.round(rms * 260))
        voiceStatus.volume = volume
        voiceStatus.volumeText = volume < 8 ? '音量偏低' : volume < 25 ? '音量正常' : '音量清晰'
        voiceStatus.diagnostic = volume < 8 ? '麦克风已授权，但声音偏小或没有输入。' : '麦克风有输入，若仍无法识别，多半是语音识别服务或环境问题。'
      }, 180)
      audioStopTimer = setTimeout(stopMicrophoneTest, 8000)
    } catch (error) {
      stopMicrophoneTest()
      voiceStatus.testingMicrophone = false
      voiceStatus.volumeText = '无法测试'
      applyMicrophoneError(error)
    }
  }

  function stopMicrophoneTest() {
    if (audioStopTimer) clearTimeout(audioStopTimer)
    if (audioTimer) clearInterval(audioTimer)
    if (audioStream) audioStream.getTracks().forEach((track) => track.stop())
    if (audioContext && audioContext.state !== 'closed') audioContext.close().catch?.(() => {})
    voiceStatus.testingMicrophone = false
    audioStopTimer = null
    audioTimer = null
    audioStream = null
    audioContext = null
  }

  function matchCommand(text) {
    const normalized = text.toLowerCase()
    return COMMANDS.find((command) => command.keywords.some((keyword) => normalized.includes(keyword.toLowerCase())))
  }

  async function executeCommand(command) {
    const result = await handlers[command.action]?.()
    if (result?.message) voiceStatus.diagnostic = result.message
  }

  async function refreshMicrophoneState() {
    if (!navigator.mediaDevices?.enumerateDevices) return
    try {
      const permission = await queryMicrophonePermission()
      if (permission) voiceStatus.permission = permission
      const devices = await navigator.mediaDevices.enumerateDevices()
      const audioInputs = devices.filter((device) => device.kind === 'audioinput')
      voiceStatus.deviceText = audioInputs.length ? `${audioInputs.length} 个输入设备` : '未发现输入设备'
      if (!audioInputs.length && voiceStatus.permission !== '已拒绝') {
        voiceStatus.diagnostic = '浏览器未发现麦克风输入设备，请检查系统默认输入设备。'
      }
    } catch {
      voiceStatus.deviceText = '无法检测'
    }
  }

  async function queryMicrophonePermission() {
    if (!navigator.permissions?.query) return ''
    try {
      const status = await navigator.permissions.query({ name: 'microphone' })
      if (status.state === 'granted') return '浏览器已允许'
      if (status.state === 'denied') return '浏览器已拒绝'
      return '浏览器待授权'
    } catch {
      return ''
    }
  }

  function applyMicrophoneError(error) {
    const name = error?.name || ''
    if (name === 'NotAllowedError' || name === 'SecurityError') {
      voiceStatus.permission = '浏览器已拒绝'
      voiceStatus.diagnostic = '浏览器站点权限未允许麦克风。请点击地址栏左侧图标，允许当前站点使用麦克风后刷新页面。'
      return
    }
    if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
      voiceStatus.permission = '未发现设备'
      voiceStatus.diagnostic = '系统允许浏览器使用麦克风，但浏览器没有发现可用输入设备。请检查默认输入设备或重新插拔麦克风。'
      return
    }
    if (name === 'NotReadableError' || name === 'TrackStartError') {
      voiceStatus.permission = '设备不可读'
      voiceStatus.diagnostic = '麦克风可能被其他程序占用，或驱动暂时不可读。请关闭占用麦克风的软件后重试。'
      return
    }
    if (name === 'OverconstrainedError') {
      voiceStatus.permission = '约束不支持'
      voiceStatus.diagnostic = '当前麦克风不支持浏览器请求的音频参数，请切换输入设备后重试。'
      return
    }
    if (name === 'AbortError') {
      voiceStatus.permission = '设备中断'
      voiceStatus.diagnostic = '麦克风访问被系统中断，请重新点击麦克风测试。'
      return
    }
    voiceStatus.permission = '测试失败'
    voiceStatus.diagnostic = error?.message || '麦克风测试失败，请检查浏览器站点权限、系统输入设备和设备占用情况。'
  }

  function speechErrorMessage(error) {
    if (error === 'no-speech') return '没有检测到语音，请靠近麦克风或提高音量。'
    if (error === 'audio-capture') return '浏览器没有捕获到麦克风输入，请先运行麦克风测试。'
    if (error === 'not-allowed') return '浏览器未允许语音识别使用麦克风，请检查站点权限。'
    if (error === 'network') return '语音识别服务网络不可用。请检查网络，或先用麦克风测试确认本地输入正常。'
    if (error === 'aborted') return '语音识别已中断，请重新开始。'
    return `语音识别错误：${error}`
  }

  return { listening, supported, transcript, voiceStatus, start, stop, testMicrophone, stopMicrophoneTest, refreshMicrophoneState }
}
