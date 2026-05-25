<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Camera, LogIn, ScanFace, ShieldCheck, UserPlus } from 'lucide-vue-next'

const props = defineProps({
  loading: Boolean,
  message: { type: String, default: '' },
  enrolled: Boolean,
  allowReenroll: Boolean,
  needsUpgrade: Boolean,
  username: { type: String, default: '杨翰飞' }
})

const emit = defineEmits(['verify', 'enroll', 'cancel', 'username-change'])
const video = ref(null)
const username = ref(props.username || '杨翰飞')
const cameraMessage = ref('请开启摄像头采集账号本人面部。')
const cameraReady = ref(false)
const faceDetected = ref(false)
const descriptor = ref(null)
const modelsLoaded = ref(false)
let stream = null
let detectTimer = null
let loadingModels = false
let modelPromise = null
let faceapi = null
let usernameTimer = null

watch(
  () => props.username,
  (value) => {
    if (value && value !== username.value) username.value = value
  }
)

watch(username, (value) => {
  if (props.allowReenroll) return
  clearTimeout(usernameTimer)
  usernameTimer = setTimeout(() => {
    const normalized = normalizeUsername(value)
    emit('username-change', normalized)
  }, 260)
})

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraMessage.value = '当前环境无法访问摄像头，不能进行人脸识别登录。'
    return
  }
  try {
    await loadModels()
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    video.value.srcObject = stream
    cameraReady.value = true
    cameraMessage.value = '正在进行人脸检测与特征提取，请保持面部在画面中央。'
    startDetection()
  } catch {
    cameraMessage.value = '摄像头未授权、模型加载失败或设备不可用，无法完成安全登录。'
  }
}

async function loadModels() {
  if (modelsLoaded.value) return
  if (loadingModels && modelPromise) return modelPromise
  loadingModels = true
  cameraMessage.value = '正在加载人脸识别模型，请稍候。'
  if (!faceapi) faceapi = await import('face-api.js')
  modelPromise = Promise.all([
    faceapi.nets.tinyFaceDetector.loadFromUri('/models'),
    faceapi.nets.faceLandmark68Net.loadFromUri('/models'),
    faceapi.nets.faceRecognitionNet.loadFromUri('/models')
  ])
  try {
    await modelPromise
    modelsLoaded.value = true
  } finally {
    loadingModels = false
  }
}

async function enroll() {
  if (props.enrolled && !props.allowReenroll && !props.needsUpgrade) {
    cameraMessage.value = '该账号已录入授权人脸，未登录状态下不能覆盖模板。'
    return
  }
  const currentDescriptor = await captureStableDescriptor()
  if (!currentDescriptor) {
    cameraMessage.value = '请先采集到清晰人脸后再录入。'
    return
  }
  emit('enroll', { username: normalizeUsername(username.value), descriptor: currentDescriptor })
}

async function verify() {
  const currentDescriptor = await captureStableDescriptor()
  if (!currentDescriptor) {
    cameraMessage.value = '请先采集到清晰人脸后再登录。'
    return
  }
  emit('verify', { username: normalizeUsername(username.value), descriptor: currentDescriptor })
}

function startDetection() {
  if (detectTimer) clearInterval(detectTimer)
  detectTimer = setInterval(async () => {
    if (!video.value || video.value.readyState < 2) return
    try {
      const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.55 })
      const faces = await faceapi.detectAllFaces(video.value, options).withFaceLandmarks().withFaceDescriptors()
      faceDetected.value = faces.length === 1
      if (!faceDetected.value) {
        descriptor.value = null
        cameraMessage.value = faces.length > 1 ? '检测到多张人脸，请仅保留账号本人。' : '未检测到人脸，请正对摄像头。'
        return
      }
      descriptor.value = createCompositeDescriptor(faces[0])
      cameraMessage.value = '已完成活体画面中的人脸检测与特征提取，可录入或登录。'
    } catch {
      cameraMessage.value = '人脸检测失败，请调整光线或重新开启摄像头。'
    }
  }, 900)
}

async function captureCurrentDescriptor() {
  if (!video.value || video.value.readyState < 2 || !faceapi) return null
  try {
    const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.58 })
    const faces = await faceapi.detectAllFaces(video.value, options).withFaceLandmarks().withFaceDescriptors()
    if (faces.length !== 1) {
      descriptor.value = null
      faceDetected.value = false
      cameraMessage.value = faces.length > 1 ? '当前画面有多张人脸，不能登录。' : '当前画面未检测到人脸。'
      return null
    }
    const freshDescriptor = createCompositeDescriptor(faces[0])
    descriptor.value = freshDescriptor
    faceDetected.value = true
    cameraMessage.value = '已重新采集当前帧人脸特征，正在提交比对。'
    return freshDescriptor
  } catch {
    cameraMessage.value = '当前帧人脸采集失败，请正对摄像头并保持光线充足。'
    return null
  }
}

async function captureStableDescriptor() {
  cameraMessage.value = '正在连续采集当前人脸，请保持不动。'
  const samples = []
  for (let index = 0; index < 5; index += 1) {
    const current = await captureCurrentDescriptor()
    if (!current) return null
    samples.push(current)
    await wait(160)
  }
  const averaged = averageDescriptors(samples)
  const maxDrift = Math.max(...samples.map((item) => descriptorDistance(item, averaged)))
  if (maxDrift > 0.18) {
    descriptor.value = null
    cameraMessage.value = '连续采集的人脸特征不稳定，请保持面部居中并重新尝试。'
    return null
  }
  descriptor.value = averaged
  cameraMessage.value = '已完成多帧稳定采样，正在提交比对。'
  return averaged
}

function averageDescriptors(samples) {
  return samples[0].map((_, index) => {
    const value = samples.reduce((sum, item) => sum + item[index], 0) / samples.length
    if (index >= 128) return value >= 0.5 ? 1 : 0
    return Number(value.toFixed(6))
  })
}

function descriptorDistance(left, right) {
  return Math.sqrt(left.slice(0, 128).reduce((sum, item, index) => sum + (item - right[index]) ** 2, 0))
}

function createCompositeDescriptor(face) {
  const modelDescriptor = Array.from(face.descriptor).map((item) => Number(item.toFixed(6)))
  return [...modelDescriptor, ...createFaceHash(face.detection.box)]
}

function createFaceHash(box) {
  const canvas = document.createElement('canvas')
  const size = 16
  canvas.width = size
  canvas.height = size
  const context = canvas.getContext('2d', { willReadFrequently: true })
  const padX = box.width * 0.18
  const padY = box.height * 0.22
  const sx = Math.max(0, box.x - padX)
  const sy = Math.max(0, box.y - padY)
  const sw = Math.min(video.value.videoWidth - sx, box.width + padX * 2)
  const sh = Math.min(video.value.videoHeight - sy, box.height + padY * 2)
  context.drawImage(video.value, sx, sy, sw, sh, 0, 0, size, size)
  const data = context.getImageData(0, 0, size, size).data
  const grays = []
  for (let index = 0; index < data.length; index += 4) {
    grays.push(data[index] * 0.299 + data[index + 1] * 0.587 + data[index + 2] * 0.114)
  }
  const mean = grays.reduce((sum, item) => sum + item, 0) / grays.length
  return grays.map((item) => (item >= mean ? 1 : 0))
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function normalizeUsername(value) {
  return value.trim() || '杨翰飞'
}

onBeforeUnmount(() => {
  if (stream) stream.getTracks().forEach((track) => track.stop())
  if (detectTimer) clearInterval(detectTimer)
  clearTimeout(usernameTimer)
})
</script>

<template>
  <main class="login-shell">
    <section class="login-card">
      <div class="login-copy">
        <div class="eyebrow"><ShieldCheck :size="17" /> 人脸安全登录</div>
        <h1>AI 学习助手</h1>
        <p>{{ allowReenroll ? '重新采集账号本人脸部模板，保存后后续登录将使用新模板。' : '首次使用需录入账号本人脸部模板；之后登录必须通过当前摄像头人脸比对。' }}</p>
        <label class="account-field">
          <span>账号</span>
          <input v-model="username" :disabled="allowReenroll" placeholder="请输入账号姓名" />
        </label>
        <p class="enroll-state">{{ needsUpgrade ? '该账号人脸模板版本较旧，请重新录入一次升级模板。' : enrolled ? (allowReenroll ? '已登录，可重新录入授权人脸。' : '该账号已录入授权人脸，请直接核验登录。') : '该账号尚未录入授权人脸，请先录入。' }}</p>
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
        <button :disabled="loading || (enrolled && !allowReenroll && !needsUpgrade) || !descriptor" @click="enroll">
          <UserPlus :size="18" /> {{ allowReenroll ? '保存新模板' : needsUpgrade ? '升级模板' : '录入人脸' }}
        </button>
        <button v-if="!allowReenroll" class="primary" :disabled="loading || !enrolled || needsUpgrade || !descriptor" @click="verify">
          <LogIn :size="18" /> 人脸识别登录
        </button>
        <button v-else class="primary" @click="$emit('cancel')">
          返回工作台
        </button>
      </div>
      <p class="login-tip">{{ message || cameraMessage }}</p>
    </section>
  </main>
</template>
