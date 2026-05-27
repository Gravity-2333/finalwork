<script setup>
import { Database, FileUp, PauseCircle, PlayCircle, UploadCloud, Trash2 } from 'lucide-vue-next'

defineProps({
  documents: { type: Array, default: () => [] },
  loading: Boolean,
  initializing: Boolean,
  initializationStep: { type: String, default: '' }
})

const emit = defineEmits(['upload', 'delete', 'clear', 'initialize', 'pause'])

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
        <p>先整理资料，确认后再生成学习路径</p>
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
    <div class="library-actions">
      <button v-if="initializing" class="danger-soft wide" @click="$emit('pause')">
        <PauseCircle :size="16" />
        暂停初始化
      </button>
      <button v-else class="primary" :disabled="loading || !documents.length" @click="$emit('initialize')">
        <PlayCircle :size="16" />
        生成课程学习路径
      </button>
      <small>{{ initializing ? initializationStep || '正在初始化课程' : '系统将基于已入库资料生成课程大纲、章节内容和测验。' }}</small>
    </div>
    <div class="doc-list">
      <article v-for="doc in documents" :key="doc.id">
        <div>
          <strong :title="doc.filename">{{ doc.filename }}</strong>
          <span>{{ doc.chunk_count }} 个切片 · 已入库</span>
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
