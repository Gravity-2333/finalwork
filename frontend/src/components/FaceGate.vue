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
const modelsLoaded = ref(false)
let stream = null
let detectTimer = null
let loadingModels = false
let modelPromise = null
let faceapi = null

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
      const options = new faceapi.TinyFaceDetectorOptions({ inputSize: 320, scoreThreshold: 0.55 })
      const faces = await faceapi.detectAllFaces(video.value, options).withFaceLandmarks().withFaceDescriptors()
      faceDetected.value = faces.length === 1
      if (!faceDetected.value) {
        descriptor.value = null
        cameraMessage.value = faces.length > 1 ? '检测到多张人脸，请仅保留账号本人。' : '未检测到人脸，请正对摄像头。'
        return
      }
      descriptor.value = Array.from(faces[0].descriptor).map((item) => Number(item.toFixed(6)))
      cameraMessage.value = '已完成活体画面中的人脸检测与特征提取，可录入或登录。'
    } catch {
      cameraMessage.value = '人脸检测失败，请调整光线或重新开启摄像头。'
    }
  }, 900)
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
