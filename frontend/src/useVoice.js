import { reactive, ref } from 'vue'

const COMMANDS = [
  { name: '生成大纲', keywords: ['大纲', '学习路径'], action: 'outline' },
  { name: '开始测验', keywords: ['测验', '考试', '出题'], action: 'quiz' },
  { name: '查看错题', keywords: ['错题', '复盘'], action: 'wrong' },
  { name: '切换 Mock 模型', keywords: ['mock', '模型'], action: 'mock' }
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
    testingMicrophone: false
  })

  let recognition = null
  let lastFinalText = ''
  let lastRecognizedText = ''
  let audioContext = null
  let audioStream = null
  let audioTimer = null
  let audioStopTimer = null

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
    if (!navigator.mediaDevices?.getUserMedia) {
      voiceStatus.permission = '不可用'
      voiceStatus.diagnostic = '当前环境不支持麦克风访问。'
      return
    }
    try {
      stopMicrophoneTest()
      voiceStatus.testingMicrophone = true
      audioStream = await navigator.mediaDevices.getUserMedia({ audio: true })
      voiceStatus.permission = '已授权'
      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      audioContext = new AudioContextClass()
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
    } catch {
      voiceStatus.testingMicrophone = false
      voiceStatus.permission = '未授权'
      voiceStatus.volumeText = '无法测试'
      voiceStatus.diagnostic = '未获得麦克风权限，请检查浏览器权限或系统输入设备。'
    }
  }

  function stopMicrophoneTest() {
    if (audioStopTimer) clearTimeout(audioStopTimer)
    if (audioTimer) clearInterval(audioTimer)
    if (audioStream) audioStream.getTracks().forEach((track) => track.stop())
    if (audioContext?.state !== 'closed') audioContext.close().catch?.(() => {})
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

  return { listening, supported, transcript, voiceStatus, start, stop, testMicrophone, stopMicrophoneTest }
}
