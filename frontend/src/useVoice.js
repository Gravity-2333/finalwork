import { reactive, ref } from 'vue'

const COMMANDS = [
  { name: '上传资料', keywords: ['上传', '资料', '文件'], action: 'upload' },
  { name: '生成大纲', keywords: ['大纲', '学习路径'], action: 'outline' },
  { name: '开始测验', keywords: ['测验', '考试', '出题'], action: 'quiz' },
  { name: '查看错题', keywords: ['错题', '复盘'], action: 'wrong' },
  { name: '模型设置', keywords: ['模型设置', '模型配置', '设置'], action: 'settings' },
  { name: '切换 Mock 模型', keywords: ['mock'], action: 'mock' }
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
          executeCommand(matched)
          stop(false)
        }
      }
    }
    recognition.onerror = (event) => {
      const reason = event.error === 'no-speech' ? '没有检测到语音，请靠近麦克风或提高音量。' : `语音识别错误：${event.error}`
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
        executeCommand(matched)
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

  function executeCommand(command) {
    handlers[command.action]?.()
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

  return { listening, supported, transcript, voiceStatus, start, stop, testMicrophone, stopMicrophoneTest, refreshMicrophoneState }
}
