<script setup>
import { ArrowRight, Sparkles } from 'lucide-vue-next'

defineProps({
  title: { type: String, required: true },
  description: { type: String, required: true },
  action: { type: String, required: true },
  secondary: { type: String, default: '' },
  disabled: Boolean
})

defineEmits(['primary', 'secondary'])
</script>

<template>
  <section class="next-action">
    <div class="next-action-copy">
      <span><Sparkles :size="16" /> 下一步建议</span>
      <strong>{{ title }}</strong>
      <p>{{ description }}</p>
    </div>
    <div class="next-action-buttons">
      <button class="primary" :disabled="disabled" @click="$emit('primary')">
        {{ action }} <ArrowRight :size="16" />
      </button>
      <button v-if="secondary" class="secondary" @click="$emit('secondary')">{{ secondary }}</button>
    </div>
  </section>
</template>
