import { computed, reactive, ref } from 'vue'

const COMMANDS = [
  { name: '上传资料', keywords: ['上传资料', '上传文件', '添加资料', '资料上传'], action: 'upload', type: 'navigate', description: '打开知识库上传区。' },
  { name: '打开知识库', keywords: ['知识库', '资料库'], action: 'library', type: 'navigate', description: '查看已上传资料。' },
  { name: '打开学习路径', keywords: ['学习路径', '课程大纲页面', '章节页面'], action: 'study', type: 'navigate', description: '查看大纲和章节内容。' },
  { name: '打开测验复盘', keywords: ['测验复盘', '测验页面', '考试页面'], action: 'quizPage', type: 'navigate', description: '查看测验与错题。' },
  { name: '查看错题', keywords: ['查看错题', '错题', '复盘'], action: 'wrong', type: 'navigate', description: '跳转到错题归档。' },
  { name: '模型设置', keywords: ['模型设置', '模型配置'], action: 'settings', type: 'navigate', description: '打开模型 Provider 配置。' },
  { name: '系统设置', keywords: ['系统设置', '提示词设置', '打开设置'], action: 'systemSettings', type: 'navigate', description: '打开资料处理和提示词设置。' },
  { name: '初始化课程', keywords: ['初始化课程', '完成上传', '开始初始化', '生成全部内容'], action: 'initialize', type: 'execute', description: '确认资料后生成大纲、章节内容和测验。' },
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

export function useVoiceCommands(handlers, options = {}) {
  const listening = ref(false)
  const browserSpeechSupported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
  const supported = computed(() => voiceProvider() === 'xfyun' || browserSpeechSupported)
  const transcript = ref(browserSpeechSupported ? '语音待命' : '当前浏览器不支持 Web Speech，可切换讯飞 API 服务或使用按钮。')
  const audioInputs = ref([])
  const selectedInputDeviceId = ref('')
  const voiceStatus = reactive({
    permission: '未测试',
    volume: 0,
    volumeText: '未测试',
    lastText: '',
    matchedCommand: '',
    diagnostic: browserSpeechSupported ? '点击开始语音识别或麦克风测试。' : '浏览器不支持 Web Speech API，可切换讯飞 API 服务。',
    testingMicrophone: false,
    inputMonitoring: false,
    deviceText: '未检测'
  })

  let recognition = null
  let lastFinalText = ''
  let lastRecognizedText = ''
  let audioContext = null
  let audioStream = null
  let audioTimer = null
  let audioStopTimer = null
  let recordingChunks = []
  let recordingSampleRate = 48000
  let recordingProcessor = null
  let recordingSource = null

  refreshMicrophoneState()
  navigator.mediaDevices?.addEventListener?.('devicechange', () => {
    void refreshMicrophoneState()
  })

  // 启动或停止语音识别。
  // 功能：根据系统设置选择 Web Speech 或讯飞 API 模式；正在监听时再次点击会停止并处理最后语音。
  function start() {
    if (!supported.value) return
    if (listening.value) {
      stop(true)
      return
    }
    if (voiceProvider() === 'xfyun') {
      void startXfyunRecording()
      return
    }
    startWebSpeech()
  }

  // 启动浏览器 Web Speech 识别。
  // 功能：使用浏览器内置语音识别服务实时返回文本，命中固定命令后自动停止并执行。
  function startWebSpeech() {
    if (!browserSpeechSupported) {
      transcript.value = '当前浏览器不支持 Web Speech API，请切换讯飞 API 服务。'
      voiceStatus.diagnostic = transcript.value
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
    voiceStatus.matchedCommand = ''
    voiceStatus.volume = 0
    voiceStatus.volumeText = '等待输入'
    transcript.value = '正在聆听，请说出命令...'
    voiceStatus.diagnostic = '正在监听并检测音量，识别到命令会自动停止并执行。'
    if (voiceStatus.testingMicrophone) stopMicrophoneTest()
    void startInputMonitor('listen').catch((error) => {
      applyMicrophoneError(error)
      voiceStatus.diagnostic = `${voiceStatus.diagnostic} 语音识别仍会尝试启动，但无法显示实时音量。`
    })
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
      stopInputMonitor()
    }
    recognition.onend = () => {
      listening.value = false
      recognition = null
      stopInputMonitor()
    }
    try {
      recognition.start()
    } catch {
      listening.value = false
      transcript.value = '语音识别启动失败，请稍后重试。'
      voiceStatus.diagnostic = '语音识别启动失败，可能是浏览器正在占用识别会话。'
      stopInputMonitor()
    }
  }

  // 停止当前语音识别。
  // 功能：Web Speech 模式处理最后一句文本；讯飞模式停止录音、上传 PCM 并等待识别结果。
  function stop(processLastText = true) {
    if (voiceProvider() === 'xfyun' && listening.value) {
      void stopXfyunRecording(processLastText)
      return
    }
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
    stopInputMonitor()
  }

  // 启动讯飞 API 模式录音。
  // 功能：采集所选麦克风音频，实时显示音量，并缓存 Float32 音频样本等待停止后转码。
  async function startXfyunRecording() {
    if (!navigator.mediaDevices?.getUserMedia) {
      voiceStatus.permission = '不可用'
      voiceStatus.diagnostic = '当前环境不支持麦克风访问。'
      return
    }
    if (voiceStatus.testingMicrophone) stopMicrophoneTest()
    listening.value = true
    lastFinalText = ''
    lastRecognizedText = ''
    recordingChunks = []
    voiceStatus.matchedCommand = ''
    voiceStatus.volume = 0
    voiceStatus.volumeText = '等待输入'
    transcript.value = '正在录音，请说出命令...'
    voiceStatus.diagnostic = '讯飞 API 模式正在录音，点击停止后会上传到本地后端代理识别。'
    try {
      await startInputMonitor('record')
    } catch (error) {
      listening.value = false
      stopInputMonitor()
      applyMicrophoneError(error)
    }
  }

  // 停止讯飞录音并识别。
  // 功能：把缓存音频转为 16k PCM，提交后端讯飞代理，拿到文本后复用固定命令匹配逻辑。
  async function stopXfyunRecording(processLastText = true) {
    const pcmBlob = buildPcmBlob()
    listening.value = false
    stopInputMonitor()
    if (!processLastText) {
      transcript.value = '语音已停止'
      return
    }
    if (!pcmBlob.size) {
      transcript.value = '没有采集到有效语音'
      voiceStatus.diagnostic = '没有采集到有效语音，请重新录音。'
      return
    }
    transcript.value = '正在识别语音...'
    voiceStatus.diagnostic = '正在通过后端代理调用讯飞语音听写。'
    try {
      const data = await handlers.recognizeSpeech?.(pcmBlob)
      const text = (data?.text || '').trim()
      if (!text) {
        transcript.value = '未识别到文字'
        voiceStatus.lastText = ''
        voiceStatus.diagnostic = '讯飞返回为空，请靠近麦克风或提高音量后重试。'
        return
      }
      lastRecognizedText = text
      voiceStatus.lastText = text
      transcript.value = text
      const matched = matchCommand(text)
      if (matched) {
        voiceStatus.matchedCommand = matched.name
        voiceStatus.diagnostic = `已识别命令：${matched.name}`
        await executeCommand(matched)
      } else {
        voiceStatus.diagnostic = '已识别文本，但没有命中命令。'
      }
    } catch (error) {
      transcript.value = '讯飞语音识别失败'
      voiceStatus.diagnostic = error?.message || '讯飞语音识别失败，请检查后端服务和凭证。'
    }
  }

  // 麦克风测试。
  // 功能：只检测权限、输入设备和实时音量，不执行命令，用于排查“听不到”和“识别失败”的区别。
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
      await startInputMonitor('test', 8000)
    } catch (error) {
      stopMicrophoneTest()
      voiceStatus.testingMicrophone = false
      voiceStatus.volumeText = '无法测试'
      applyMicrophoneError(error)
    }
  }

  function stopMicrophoneTest() {
    stopInputMonitor()
    voiceStatus.testingMicrophone = false
  }

  // 打开麦克风输入监测。
  // 功能：创建 getUserMedia 音频流，用 AnalyserNode 计算音量；录音模式下额外缓存音频样本。
  async function startInputMonitor(mode = 'listen', autoStopMs = 0) {
    stopInputMonitor()
    const audioConstraints = {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    }
    if (selectedInputDeviceId.value) {
      audioConstraints.deviceId = { exact: selectedInputDeviceId.value }
    }
    audioStream = await navigator.mediaDevices.getUserMedia({
      audio: audioConstraints
    })
    await refreshMicrophoneState()
    voiceStatus.permission = '已授权'
    voiceStatus.inputMonitoring = true
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
    recordingSource = source
    if (mode === 'record') {
      recordingSampleRate = audioContext.sampleRate || 48000
      recordingProcessor = audioContext.createScriptProcessor(4096, 1, 1)
      recordingProcessor.onaudioprocess = (event) => {
        const input = event.inputBuffer.getChannelData(0)
        recordingChunks.push(new Float32Array(input))
      }
      source.connect(recordingProcessor)
      recordingProcessor.connect(audioContext.destination)
    }
    const data = new Uint8Array(analyser.fftSize)
    audioTimer = setInterval(() => {
      analyser.getByteTimeDomainData(data)
      const rms = Math.sqrt(data.reduce((sum, value) => sum + ((value - 128) / 128) ** 2, 0) / data.length)
      const volume = Math.min(100, Math.round(rms * 260))
      voiceStatus.volume = volume
      voiceStatus.volumeText = volume < 8 ? '音量偏低' : volume < 25 ? '音量正常' : '音量清晰'
      if (mode === 'test') {
        voiceStatus.diagnostic = volume < 8 ? '麦克风已授权，但声音偏小或没有输入。' : '麦克风有输入，若仍无法识别，多半是语音识别服务或环境问题。'
      } else if (mode === 'record') {
        voiceStatus.diagnostic = volume < 8 ? '讯飞模式录音中，当前音量偏低。' : '讯飞模式录音中，点击停止后会自动识别。'
      } else if (volume < 8) {
        voiceStatus.diagnostic = '正在监听，但当前音量偏低；请靠近麦克风或提高音量。'
      } else {
        voiceStatus.diagnostic = '麦克风有输入，正在等待浏览器返回识别文本。'
      }
    }, 180)
    if (autoStopMs) audioStopTimer = setTimeout(stopMicrophoneTest, autoStopMs)
  }

  function stopInputMonitor() {
    if (audioStopTimer) clearTimeout(audioStopTimer)
    if (audioTimer) clearInterval(audioTimer)
    if (recordingProcessor) {
      recordingProcessor.disconnect()
      recordingProcessor.onaudioprocess = null
    }
    if (recordingSource) recordingSource.disconnect()
    if (audioStream) audioStream.getTracks().forEach((track) => track.stop())
    if (audioContext && audioContext.state !== 'closed') audioContext.close().catch?.(() => {})
    voiceStatus.inputMonitoring = false
    audioStopTimer = null
    audioTimer = null
    audioStream = null
    audioContext = null
    recordingProcessor = null
    recordingSource = null
  }

  // 构建讯飞可接收的 PCM 音频。
  // 功能：合并录音样本、重采样到 16kHz，并转成 little-endian PCM 16bit。
  function buildPcmBlob() {
    const samples = mergeFloat32(recordingChunks)
    recordingChunks = []
    if (!samples.length) return new Blob([], { type: 'audio/pcm' })
    const downsampled = downsample(samples, recordingSampleRate, 16000)
    const pcm = floatTo16BitPcm(downsampled)
    return new Blob([pcm], { type: 'audio/pcm' })
  }

  // 匹配语音命令。
  // 功能：对识别文本做关键词包含匹配，命中后返回对应的页面跳转或自动执行命令。
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
      const inputs = devices.filter((device) => device.kind === 'audioinput')
      audioInputs.value = inputs.map((device, index) => ({
        deviceId: device.deviceId,
        label: device.label || `麦克风 ${index + 1}`
      }))
      if (!selectedInputDeviceId.value && audioInputs.value[0]) {
        selectedInputDeviceId.value = audioInputs.value[0].deviceId
      }
      if (selectedInputDeviceId.value && !audioInputs.value.some((device) => device.deviceId === selectedInputDeviceId.value)) {
        selectedInputDeviceId.value = audioInputs.value[0]?.deviceId || ''
      }
      const selected = audioInputs.value.find((device) => device.deviceId === selectedInputDeviceId.value)
      voiceStatus.deviceText = inputs.length ? `${inputs.length} 个输入设备 · ${selected?.label || '默认输入'}` : '未发现输入设备'
      if (!inputs.length && voiceStatus.permission !== '已拒绝') {
        voiceStatus.diagnostic = '浏览器未发现麦克风输入设备，请检查系统默认输入设备。'
      }
    } catch {
      voiceStatus.deviceText = '无法检测'
    }
  }

  // 切换麦克风输入设备。
  // 功能：更新测试和音量监测使用的设备；Web Speech 实际输入设备仍由浏览器服务接管。
  async function selectInputDevice(deviceId) {
    selectedInputDeviceId.value = deviceId
    const selected = audioInputs.value.find((device) => device.deviceId === deviceId)
    voiceStatus.deviceText = selected ? `${audioInputs.value.length} 个输入设备 · ${selected.label}` : voiceStatus.deviceText
    voiceStatus.diagnostic = selected
      ? `已选择输入设备：${selected.label}。麦克风测试会立即使用该设备；语音识别将使用浏览器当前可用输入。`
      : '已切换输入设备。'
    if (voiceStatus.testingMicrophone) {
      await startInputMonitor('test', 8000).catch(applyMicrophoneError)
    } else if (voiceStatus.inputMonitoring) {
      await startInputMonitor('listen').catch(applyMicrophoneError)
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

  function voiceProvider() {
    return options.voiceProvider?.value || options.voiceProvider || 'xfyun'
  }

  return {
    listening,
    supported,
    transcript,
    voiceStatus,
    audioInputs,
    selectedInputDeviceId,
    start,
    stop,
    testMicrophone,
    stopMicrophoneTest,
    refreshMicrophoneState,
    selectInputDevice
  }
}

// 合并录音分片。
// 功能：把 ScriptProcessor 多次回调得到的 Float32Array 拼成连续音频样本。
function mergeFloat32(chunks) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const result = new Float32Array(length)
  let offset = 0
  chunks.forEach((chunk) => {
    result.set(chunk, offset)
    offset += chunk.length
  })
  return result
}

// 音频重采样。
// 功能：将浏览器采集的原始采样率压到讯飞听写要求的 16kHz。
function downsample(samples, inputRate, outputRate) {
  if (inputRate === outputRate) return samples
  const ratio = inputRate / outputRate
  const length = Math.floor(samples.length / ratio)
  const result = new Float32Array(length)
  for (let index = 0; index < length; index += 1) {
    const start = Math.floor(index * ratio)
    const end = Math.floor((index + 1) * ratio)
    let sum = 0
    let count = 0
    for (let source = start; source < end && source < samples.length; source += 1) {
      sum += samples[source]
      count += 1
    }
    result[index] = count ? sum / count : 0
  }
  return result
}

// Float32 转 PCM 16bit。
// 功能：把 -1 到 1 的浮点音频样本转换为讯飞 WebAPI 使用的 PCM 二进制格式。
function floatTo16BitPcm(samples) {
  const buffer = new ArrayBuffer(samples.length * 2)
  const view = new DataView(buffer)
  for (let index = 0; index < samples.length; index += 1) {
    const sample = Math.max(-1, Math.min(1, samples[index]))
    view.setInt16(index * 2, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true)
  }
  return buffer
}
