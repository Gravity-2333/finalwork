<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { Camera, LogIn, ScanFace, ShieldCheck } from 'lucide-vue-next'

defineProps({
  loading: Boolean,
  message: { type: String, default: '' }
})

const emit = defineEmits(['verify'])
const video = ref(null)
const cameraMessage = ref('请开启摄像头完成人脸核验。')
const cameraReady = ref(false)
const faceDetected = ref(false)
const detectorSupported = 'FaceDetector' in window
let stream = null
let detectTimer = null

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraMessage.value = '当前浏览器不支持摄像头访问，可使用演示核验。'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    video.value.srcObject = stream
    cameraReady.value = true
    cameraMessage.value = detectorSupported ? '正在检测人脸，请保持面部在画面中央。' : '摄像头已开启，当前浏览器不支持原生人脸检测，可使用演示核验。'
    if (detectorSupported) startDetection()
  } catch {
    cameraMessage.value = '摄像头未授权或不可用，可使用演示核验。'
  }
}

function verify() {
  emit('verify', { cameraReady: cameraReady.value, faceDetected: faceDetected.value, detectorSupported })
}

onBeforeUnmount(() => {
  if (stream) stream.getTracks().forEach((track) => track.stop())
  if (detectTimer) clearInterval(detectTimer)
})

function startDetection() {
  const detector = new window.FaceDetector({ fastMode: true, maxDetectedFaces: 1 })
  detectTimer = setInterval(async () => {
    if (!video.value || video.value.readyState < 2) return
    try {
      const faces = await detector.detect(video.value)
      faceDetected.value = faces.length > 0
      cameraMessage.value = faceDetected.value ? '已检测到人脸，可以登录。' : '未检测到人脸，请正对摄像头。'
    } catch {
      cameraMessage.value = '人脸检测不可用，可使用演示核验。'
    }
  }, 900)
}
</script>

<template>
  <main class="login-shell">
    <section class="login-card">
      <div class="login-copy">
        <div class="eyebrow"><ShieldCheck :size="17" /> 安全登录</div>
        <h1>AI 学习助手</h1>
        <p>请先完成人脸识别核验，核验通过后进入课程知识库与学习工作台。</p>
      </div>

      <div class="camera-panel">
        <video ref="video" autoplay muted playsinline></video>
        <div v-if="!cameraReady || !faceDetected" class="camera-placeholder">
          <ScanFace :size="42" />
          <span>{{ cameraMessage }}</span>
        </div>
      </div>

      <div class="login-actions">
        <button @click="startCamera"><Camera :size="18" /> 开启摄像头</button>
        <button class="primary" :disabled="loading || (detectorSupported && !faceDetected)" @click="verify">
          <LogIn :size="18" /> {{ detectorSupported ? '人脸核验登录' : '演示核验登录' }}
        </button>
      </div>
      <p class="login-tip">{{ message || cameraMessage }}</p>
    </section>
  </main>
</template>
