<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' }
})

const emit = defineEmits(['update:modelValue'])
const textarea = ref(null)
const minHeight = 220
const maxHeight = 420

onMounted(resize)

watch(
  () => props.modelValue,
  () => nextTick(resize)
)

function handleInput(event) {
  emit('update:modelValue', event.target.value)
  nextTick(resize)
}

function resize() {
  const el = textarea.value
  if (!el) return
  el.style.height = `${minHeight}px`
  const nextHeight = Math.min(Math.max(el.scrollHeight, minHeight), maxHeight)
  el.style.height = `${nextHeight}px`
  el.style.overflowY = el.scrollHeight > maxHeight ? 'auto' : 'hidden'
}
</script>

<template>
  <textarea
    ref="textarea"
    class="prompt-textarea"
    :value="modelValue"
    :placeholder="placeholder"
    @input="handleInput"
  ></textarea>
</template>
