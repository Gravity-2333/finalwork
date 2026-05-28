<script setup>
import { BrainCircuit, LogOut, Mic, ScanFace } from 'lucide-vue-next'

defineProps({
  faceOk: Boolean,
  loading: Boolean,
  listening: Boolean,
  supported: Boolean
})

defineEmits(['manage-face', 'voice', 'logout'])
</script>

<template>
  <header class="hero">
    <div class="hero-copy">
      <div class="eyebrow"><BrainCircuit :size="17" /> AI Learning Workspace</div>
      <h1>AI 学习助手</h1>
      <p>把课程资料转成学习路径、章节内容、测验与错题复盘。</p>
    </div>
    <div class="hero-actions">
      <button :class="['face-button', { verified: faceOk }]" :disabled="loading" @click="$emit('manage-face')">
        <ScanFace :size="18" /> {{ faceOk ? '重录人脸' : '人脸核验' }}
      </button>
      <button :class="{ active: listening }" :disabled="!supported" @click="$emit('voice')">
        <Mic :size="18" /> {{ listening ? '停止语音' : '语音控制' }}
      </button>
      <button :disabled="loading" @click="$emit('logout')">
        <LogOut :size="18" /> 退出登录
      </button>
    </div>
  </header>
</template>
