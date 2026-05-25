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
let stream = null

async function startCamera() {
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraMessage.value = '当前浏览器不支持摄像头访问，可使用演示核验。'
    return
  }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
    video.value.srcObject = stream
    cameraReady.value = true
    cameraMessage.value = '摄像头已开启，请保持面部在画面中央。'
  } catch {
    cameraMessage.value = '摄像头未授权或不可用，可使用演示核验。'
  }
}

function verify() {
  emit('verify', { cameraReady: cameraReady.value })
}

onBeforeUnmount(() => {
  if (stream) stream.getTracks().forEach((track) => track.stop())
})
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
        <div v-if="!cameraReady" class="camera-placeholder">
          <ScanFace :size="42" />
          <span>{{ cameraMessage }}</span>
        </div>
      </div>

      <div class="login-actions">
        <button @click="startCamera"><Camera :size="18" /> 开启摄像头</button>
        <button class="primary" :disabled="loading" @click="verify">
          <LogIn :size="18" /> 人脸核验登录
        </button>
      </div>
      <p class="login-tip">{{ message || cameraMessage }}</p>
    </section>
  </main>
</template>

