<script setup>
import { onBeforeUnmount, ref } from 'vue'
import { Camera, LogIn, ScanFace, ShieldCheck, UserPlus } from 'lucide-vue-next'

defineProps({
  loading: Boolean,
  message: { type: String, default: '' },
  enrolled: Boolean
})

const emit = defineEmits(['verify', 'enroll'])
const video = ref(null)
const username = ref('杨翰飞')
const cameraMessage = ref('请开启摄像头采集账号本人面部。')
const cameraReady = ref(false)
const faceDetected = ref(false)
const descriptor = ref(null)
const detectorSupported = 'FaceDetector' in window
let stream = null
let detectTimer = null
let detector = null

async function startCamera() {
  if (!detectorSupported) {
    cameraMessage.value = '当前浏览器不支持 FaceDetector，无法进行真实人脸识别。请使用 Chrome/Edge 新版本。'
    return
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraMessage.value = '当前环境无法访问摄像头，不能进行人脸识别登录。'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    video.value.srcObject = stream
    detector = new window.FaceDetector({ fastMode: false, maxDetectedFaces: 1 })
    cameraReady.value = true
    cameraMessage.value = '正在检测人脸，请保持面部在画面中央。'
    startDetection()
  } catch {
    cameraMessage.value = '摄像头未授权或不可用，无法完成安全登录。'
  }
}

function enroll() {
  if (!descriptor.value) {
    cameraMessage.value = '请先采集到清晰人脸后再录入。'
    return
  }
  emit('enroll', { username: username.value, descriptor: descriptor.value })
}

function verify() {
  if (!descriptor.value) {
    cameraMessage.value = '请先采集到清晰人脸后再登录。'
    return
  }
  emit('verify', { username: username.value, descriptor: descriptor.value })
}

function startDetection() {
  if (detectTimer) clearInterval(detectTimer)
  detectTimer = setInterval(async () => {
    if (!video.value || video.value.readyState < 2) return
    try {
      const faces = await detector.detect(video.value)
      faceDetected.value = faces.length === 1
      if (!faceDetected.value) {
        descriptor.value = null
        cameraMessage.value = faces.length > 1 ? '检测到多张人脸，请仅保留账号本人。' : '未检测到人脸，请正对摄像头。'
        return
      }
      descriptor.value = extractDescriptor(video.value, faces[0].boundingBox)
      cameraMessage.value = '已采集到人脸特征，可录入或登录。'
    } catch {
      cameraMessage.value = '人脸检测失败，请调整光线或重新开启摄像头。'
    }
  }, 900)
}

function extractDescriptor(source, box) {
  const canvas = document.createElement('canvas')
  const size = 32
  canvas.width = size
  canvas.height = size
  const context = canvas.getContext('2d', { willReadFrequently: true })
  const padX = box.width * 0.18
  const padY = box.height * 0.24
  const sx = Math.max(0, box.x - padX)
  const sy = Math.max(0, box.y - padY)
  const sw = Math.min(source.videoWidth - sx, box.width + padX * 2)
  const sh = Math.min(source.videoHeight - sy, box.height + padY * 2)
  context.drawImage(source, sx, sy, sw, sh, 0, 0, size, size)
  const data = context.getImageData(0, 0, size, size).data
  const values = []
  for (let index = 0; index < data.length; index += 4) {
    values.push((data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114) / 255)
  }
  const mean = values.reduce((sum, item) => sum + item, 0) / values.length
  const variance = values.reduce((sum, item) => sum + (item - mean) ** 2, 0) / values.length
  const std = Math.sqrt(variance) || 1
  return values.map((item) => Number(((item - mean) / std).toFixed(6)))
}

onBeforeUnmount(() => {
  if (stream) stream.getTracks().forEach((track) => track.stop())
  if (detectTimer) clearInterval(detectTimer)
})
</script>

<template>
  <main class="login-shell">
    <section class="login-card">
      <div class="login-copy">
        <div class="eyebrow"><ShieldCheck :size="17" /> 人脸安全登录</div>
        <h1>AI 学习助手</h1>
        <p>首次使用需录入账号本人脸部模板；之后登录必须通过当前摄像头人脸比对。</p>
        <label class="account-field">
          <span>账号</span>
          <input v-model="username" placeholder="请输入账号姓名" />
        </label>
        <p class="enroll-state">{{ enrolled ? '该账号已录入授权人脸。' : '该账号尚未录入授权人脸，请先录入。' }}</p>
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
        <button :disabled="loading || !descriptor" @click="enroll">
          <UserPlus :size="18" /> 录入人脸
        </button>
        <button class="primary" :disabled="loading || !enrolled || !descriptor" @click="verify">
          <LogIn :size="18" /> 人脸识别登录
        </button>
      </div>
      <p class="login-tip">{{ message || cameraMessage }}</p>
    </section>
  </main>
</template>

