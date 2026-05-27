<script setup>
import { BrainCircuit, Play, RefreshCw, Trophy } from 'lucide-vue-next'
import MarkdownBlock from './MarkdownBlock.vue'
import { computed } from 'vue'

const props = defineProps({
  chapters: { type: Array, default: () => [] },
  selectedChapter: { type: Object, default: null },
  selectedChapterId: { type: Number, default: null },
  quizGeneratingIds: { type: Array, default: () => [] },
  loading: Boolean
})

defineEmits(['outline', 'select', 'content', 'quiz', 'wrong'])

const selectedQuizGenerating = computed(() => props.selectedChapter && props.quizGeneratingIds.includes(props.selectedChapter.id))
const selectedQuizReady = computed(() => Number(props.selectedChapter?.quiz_count || 0) > 0)
const quizBlockedReason = computed(() => {
  if (!props.selectedChapter) return '请先选择章节'
  if (selectedQuizGenerating.value) return '测验正在后台生成'
  if (!props.selectedChapter.content) return '请先生成章节内容'
  if (!selectedQuizReady.value) return '测验尚未生成完成'
  return ''
})
</script>

<template>
  <section class="main-panel">
    <div class="toolbar">
      <button class="primary" :disabled="loading" @click="$emit('outline')">
        <RefreshCw :size="17" /> {{ chapters.length ? '重新生成大纲' : '生成课程大纲' }}
      </button>
      <button :disabled="loading || Boolean(quizBlockedReason)" :title="quizBlockedReason" @click="$emit('quiz')">
        <Play :size="17" /> 开始测验
      </button>
      <button :disabled="loading" @click="$emit('wrong')"><Trophy :size="17" /> 查看错题</button>
      <span v-if="quizBlockedReason" class="toolbar-hint">{{ quizBlockedReason }}</span>
    </div>

    <div v-if="!chapters.length" class="empty-state">
      <BrainCircuit :size="34" />
      <h2>从知识库生成学习路径</h2>
      <p>上传资料后点击“生成课程学习路径”，系统会创建章节、学习目标和后续测验入口。</p>
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
            <small v-if="quizGeneratingIds.includes(chapter.id)">测验生成中</small>
            <small v-else-if="chapter.quiz_count">测验已就绪</small>
            <h3>{{ chapter.title }}</h3>
            <p>{{ chapter.objective }}</p>
          </div>
          <div class="progress-line"><span :style="{ width: `${chapter.progress}%` }"></span></div>
          <button :disabled="loading" @click.stop="$emit('content', chapter)">{{ chapter.content ? '重新生成内容' : '生成学习内容' }}</button>
        </article>
      </aside>

      <article v-if="selectedChapter" class="content-panel">
        <div class="content-heading">
          <div>
            <h2>{{ selectedChapter.title }}</h2>
            <p class="objective">{{ selectedChapter.objective }}</p>
          </div>
          <button class="primary" :disabled="loading" @click="$emit('content', selectedChapter)">{{ selectedChapter.content ? '重新生成内容' : '生成学习内容' }}</button>
        </div>
        <MarkdownBlock
          :content="selectedChapter.content"
          empty="点击“生成内容”，系统将结合知识库生成本章学习材料。"
        />
      </article>
    </div>
  </section>
</template>
