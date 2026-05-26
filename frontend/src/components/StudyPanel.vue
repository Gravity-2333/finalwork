<script setup>
import { BrainCircuit, Play, RefreshCw, Trophy } from 'lucide-vue-next'
import MarkdownBlock from './MarkdownBlock.vue'

defineProps({
  chapters: { type: Array, default: () => [] },
  selectedChapter: { type: Object, default: null },
  selectedChapterId: { type: Number, default: null },
  loading: Boolean
})

defineEmits(['outline', 'select', 'content', 'quiz', 'wrong'])
</script>

<template>
  <section class="main-panel">
    <div class="toolbar">
      <button class="primary" :disabled="loading" @click="$emit('outline')">
        <RefreshCw :size="17" /> 生成课程大纲
      </button>
      <button :disabled="loading || !selectedChapter" @click="$emit('quiz')">
        <Play :size="17" /> 开始测验
      </button>
      <button :disabled="loading" @click="$emit('wrong')"><Trophy :size="17" /> 查看错题</button>
    </div>

    <div v-if="!chapters.length" class="empty-state">
      <BrainCircuit :size="34" />
      <h2>从知识库生成学习路径</h2>
      <p>上传资料后点击“生成课程大纲”，系统会创建章节、学习目标和后续测验入口。</p>
      <button class="primary" :disabled="loading" @click="$emit('outline')"><RefreshCw :size="17" /> 生成课程大纲</button>
    </div>

    <div v-else class="study-layout">
      <aside class="chapter-sidebar">
        <article
          v-for="chapter in chapters"
          :key="chapter.id"
          :class="['chapter-card', { selected: chapter.id === selectedChapterId }]"
          @click="$emit('select', chapter.id)"
        >
          <div>
            <span>{{ chapter.content ? '已生成' : '待学习' }}</span>
            <h3>{{ chapter.title }}</h3>
            <p>{{ chapter.objective }}</p>
          </div>
          <div class="progress-line"><span :style="{ width: `${chapter.progress}%` }"></span></div>
          <button :disabled="loading" @click.stop="$emit('content', chapter)">生成学习内容</button>
        </article>
      </aside>

      <article v-if="selectedChapter" class="content-panel">
        <div class="content-heading">
          <div>
            <h2>{{ selectedChapter.title }}</h2>
            <p class="objective">{{ selectedChapter.objective }}</p>
          </div>
          <button class="primary" :disabled="loading" @click="$emit('content', selectedChapter)">生成内容</button>
        </div>
        <MarkdownBlock
          :content="selectedChapter.content"
          empty="点击“生成内容”，系统将结合知识库生成本章学习材料。"
        />
      </article>
    </div>
  </section>
</template>
