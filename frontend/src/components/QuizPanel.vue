<script setup>
import { computed } from 'vue'
import { CheckCircle2, CircleX, Trophy } from 'lucide-vue-next'

const props = defineProps({
  quizzes: { type: Array, default: () => [] },
  answers: { type: Object, required: true },
  result: { type: Object, default: null },
  wrongs: { type: Array, default: () => [] },
  loading: Boolean
})

defineEmits(['submit', 'study'])

const answeredAll = computed(() => props.quizzes.length > 0 && props.quizzes.every((quiz) => props.answers[quiz.id]))
</script>

<template>
  <aside class="quiz-panel">
    <div class="panel-title">
      <Trophy :size="19" />
      <h2>测验与错题</h2>
    </div>
    <div v-if="quizzes.length" class="quiz-list">
      <article v-for="(quiz, index) in quizzes" :key="quiz.id">
        <span class="question-index">第 {{ index + 1 }} / {{ quizzes.length }} 题</span>
        <h3>{{ quiz.question }}</h3>
        <label v-for="option in quiz.options" :key="option" :class="{ selected: answers[quiz.id] === option }">
          <input v-model="answers[quiz.id]" type="radio" :name="`quiz-${quiz.id}`" :value="option" />
          {{ option }}
        </label>
      </article>
      <button class="primary" :disabled="loading || !answeredAll" @click="$emit('submit')">提交测验</button>
      <div v-if="result" class="score-card">
        <strong>得分 {{ result.score }} / {{ result.total }}</strong>
        <span>{{ result.score === result.total ? '全部正确，继续保持。' : '已记录错题，可在下方复盘。' }}</span>
      </div>
    </div>
    <div v-else class="empty-state compact">
      <Trophy :size="30" />
      <h2>暂无测验</h2>
      <p>请先在学习路径中选择章节并生成测验。</p>
      <button @click="$emit('study')">打开学习路径</button>
    </div>

    <div class="wrong-list">
      <h3>错题归档</h3>
      <article v-for="item in wrongs" :key="item.id">
        <strong><CircleX :size="15" /> {{ item.chapter_title }}</strong>
        <p>{{ item.question }}</p>
        <small>你的答案：{{ item.selected || '未选择' }}</small>
        <small>正确答案：{{ item.answer }}</small>
        <p class="explanation">{{ item.explanation }}</p>
      </article>
      <div v-if="!wrongs.length" class="empty-positive">
        <CheckCircle2 :size="18" />
        <span>暂无错题，继续保持。</span>
      </div>
    </div>
  </aside>
</template>
