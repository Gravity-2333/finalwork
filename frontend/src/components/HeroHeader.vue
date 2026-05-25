<script setup>
import { BrainCircuit, Mic, ScanFace } from 'lucide-vue-next'

defineProps({
  faceOk: Boolean,
  loading: Boolean,
  listening: Boolean,
  supported: Boolean
})

defineEmits(['verify', 'voice'])
</script>

<template>
  <section class="hero">
    <div class="hero-copy">
      <div class="eyebrow"><BrainCircuit :size="17" /> LangChain · LangGraph · 可选 LangSmith</div>
      <h1>AI 学习助手</h1>
      <p>把课程资料转成可学习、可测验、可复盘的个人知识库。</p>
    </div>
    <div class="hero-actions">
      <button :class="['face-button', { verified: faceOk }]" :disabled="loading" @click="$emit('verify')">
        <ScanFace :size="18" /> {{ faceOk ? '已核验' : '人脸核验' }}
      </button>
      <button :class="{ active: listening }" :disabled="!supported" @click="$emit('voice')">
        <Mic :size="18" /> 语音控制
      </button>
    </div>
  </section>
</template>

