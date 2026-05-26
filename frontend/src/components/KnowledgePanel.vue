<script setup>
import { FileUp, Trash2 } from 'lucide-vue-next'

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
      <FileUp :size="19" />
      <h2>资料与知识库</h2>
      <button class="icon-action" :disabled="loading || !documents.length" title="清空资料库" @click="$emit('clear')">
        <Trash2 :size="16" />
      </button>
    </div>
    <label class="upload-box">
      <input type="file" multiple accept=".txt,.md,.docx,.pdf" :disabled="loading" @change="onUpload" />
      <span>批量上传课程资料</span>
      <small>支持 txt / md / docx / pdf，一次最多 20 个，单个不超过 25MB</small>
    </label>
    <div class="doc-list">
      <article v-for="doc in documents" :key="doc.id">
        <div>
          <strong>{{ doc.filename }}</strong>
          <span>{{ doc.chunk_count }} 个切片 · 已入库</span>
        </div>
        <button class="icon-action danger" :disabled="loading" title="删除该资料" @click="$emit('delete', doc)">
          <Trash2 :size="15" />
        </button>
      </article>
      <p v-if="!documents.length" class="empty">暂无资料，请先上传课程资料。</p>
    </div>
  </aside>
</template>
