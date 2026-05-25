import { ref } from 'vue'

export function useVoiceCommands(handlers) {
  const listening = ref(false)
  const supported = 'webkitSpeechRecognition' in window || 'SpeechRecognition' in window
  const transcript = ref(supported ? '语音待命' : '当前浏览器不支持语音识别，可使用按钮完成相同操作。')

  function start() {
    if (!supported) return
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition
    const recognition = new Recognition()
    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = false
    listening.value = true
    transcript.value = '正在聆听...'
    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript
      transcript.value = text
      if (text.includes('大纲')) handlers.outline?.()
      if (text.includes('测验') || text.includes('考试')) handlers.quiz?.()
      if (text.includes('错题')) handlers.wrong?.()
      if (text.includes('模型') || text.includes('mock')) handlers.mock?.()
    }
    recognition.onerror = () => {
      transcript.value = '语音识别失败，可继续使用页面按钮。'
    }
    recognition.onend = () => {
      listening.value = false
    }
    recognition.start()
  }

  return { listening, supported, transcript, start }
}
