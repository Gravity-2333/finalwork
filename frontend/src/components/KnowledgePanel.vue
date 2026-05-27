<script setup>
import { Database, FileSearch, FileUp, PauseCircle, PlayCircle, Search, UploadCloud, Trash2 } from 'lucide-vue-next'

defineProps({
  documents: { type: Array, default: () => [] },
  searchQuery: { type: String, default: '' },
  searchResults: { type: Array, default: () => [] },
  loading: Boolean,
  initializing: Boolean,
  initializationStep: { type: String, default: '' }
})

const emit = defineEmits(['upload', 'delete', 'clear', 'initialize', 'pause', 'search', 'update:searchQuery'])

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
    <section class="knowledge-search">
      <div class="search-heading">
        <FileSearch :size="17" />
        <div>
          <strong>本地知识库检索</strong>
          <span>从已入库切片中检索关键词，结果只来自本机资料库。</span>
        </div>
      </div>
      <form class="search-bar" @submit.prevent="$emit('search')">
        <input
          :value="searchQuery"
          type="search"
          placeholder="输入关键词，例如：卷积神经网络、过拟合、Keras"
          :disabled="loading || !documents.length"
          @input="$emit('update:searchQuery', $event.target.value)"
        />
        <button class="primary" :disabled="loading || !documents.length || !searchQuery.trim()">
          <Search :size="16" />
          检索
        </button>
      </form>
      <div v-if="searchResults.length" class="search-results">
        <article v-for="item in searchResults" :key="item.id">
          <div>
            <strong :title="item.filename">{{ item.filename }}</strong>
            <span>片段 #{{ item.id }}<template v-if="item.page !== null && item.page !== undefined"> · 第 {{ Number(item.page) + 1 }} 页</template></span>
          </div>
          <p>{{ item.content }}</p>
        </article>
      </div>
      <p v-else class="search-empty">上传资料后，可在这里检索本地专属知识库片段。</p>
    </section>
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
