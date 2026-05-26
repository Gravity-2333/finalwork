<script setup>
import { Database, FileUp, UploadCloud, Trash2 } from 'lucide-vue-next'

defineProps({
  documents: { type: Array, default: () => [] },
  loading: Boolean
})

const emit = defineEmits(['upload', 'delete', 'clear'])

function onUpload(event) {
  emit('upload', event)
}
</script>

<template>
  <aside class="side-panel">
    <div class="panel-title">
      <Database :size="19" />
      <div>
        <h2>知识库</h2>
        <p>上传后自动切分并入库</p>
      </div>
      <button class="icon-action" :disabled="loading || !documents.length" title="清空资料库" @click="$emit('clear')">
        <Trash2 :size="16" />
      </button>
    </div>
    <label class="upload-box">
      <input type="file" multiple accept=".txt,.md,.docx,.pdf" :disabled="loading" @change="onUpload" />
      <UploadCloud :size="30" />
      <span>选择文件上传</span>
      <small>txt / md / docx / pdf · 单批 20 个 · 单个 25MB</small>
    </label>
    <div class="doc-list">
      <article v-for="doc in documents" :key="doc.id">
        <div>
          <strong :title="doc.filename">{{ doc.filename }}</strong>
          <span>{{ doc.chunk_count }} 个切片 · 已入库</span>
          <small>{{ doc.summary }}</small>
        </div>
        <button class="icon-action danger" :disabled="loading" title="删除该资料" @click="$emit('delete', doc)">
          <Trash2 :size="15" />
        </button>
      </article>
      <div v-if="!documents.length" class="empty-state compact">
        <FileUp :size="30" />
        <h2>暂无资料</h2>
        <p>先上传课程资料，系统才会生成大纲、章节内容和测验。</p>
      </div>
    </div>
  </aside>
</template>
