<script setup>
import { computed } from 'vue'

const props = defineProps({
  content: { type: String, default: '' },
  empty: { type: String, default: '' }
})

const html = computed(() => renderMarkdown(props.content || props.empty))

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;')
}

function inlineMarkdown(value) {
  return escapeHtml(value)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`(.+?)`/g, '<code>$1</code>')
}

function renderMarkdown(value) {
  const lines = value.split(/\r?\n/)
  const parts = []
  let listType = ''

  function closeList(type = '') {
    if (listType && (!type || listType !== type)) {
      parts.push(`</${listType}>`)
      listType = ''
    }
    if (type && listType !== type) {
      parts.push(`<${type}>`)
      listType = type
    }
  }

  for (const rawLine of lines) {
    const line = rawLine.trim()
    if (!line) {
      closeList()
      continue
    }
    const heading = /^(#{1,4})\s+(.+)$/.exec(line)
    if (heading) {
      closeList()
      const level = Math.min(heading[1].length + 1, 4)
      parts.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`)
      continue
    }
    const ordered = /^\d+[.、]\s+(.+)$/.exec(line)
    const unordered = /^[-*]\s+(.+)$/.exec(line)
    const listText = ordered?.[1] || unordered?.[1]
    if (listText) {
      closeList(ordered ? 'ol' : 'ul')
      parts.push(`<li>${inlineMarkdown(listText)}</li>`)
      continue
    }
    closeList()
    parts.push(`<p>${inlineMarkdown(line)}</p>`)
  }
  closeList()
  return parts.join('')
}
</script>

<template>
  <div class="markdown-body" v-html="html"></div>
</template>
