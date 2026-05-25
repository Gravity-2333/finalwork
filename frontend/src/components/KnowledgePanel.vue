<script setup>
import { FileUp } from 'lucide-vue-next'

defineProps({
  documents: { type: Array, default: () => [] }
})

const emit = defineEmits(['upload'])

function onUpload(event) {
  emit('upload', event)
}
</script>

<template>
  <aside class="side-panel">
    <div class="panel-title">
      <FileUp :size="19" />
      <h2>资料与知识库</h2>
    </div>
    <label class="upload-box">
      <input type="file" multiple accept=".txt,.md,.docx,.pdf" @change="onUpload" />
      <span>批量上传课程资料</span>
      <small>支持 txt / md / docx / pdf，单个文件不超过 25MB</small>
    </label>
    <div class="doc-list">
      <article v-for="doc in documents" :key="doc.id">
        <strong>{{ doc.filename }}</strong>
        <span>{{ doc.chunk_count }} 个切片 · 已入库</span>
      </article>
      <p v-if="!documents.length" class="empty">暂无资料，请先上传课程资料。</p>
    </div>
  </aside>
</template>
