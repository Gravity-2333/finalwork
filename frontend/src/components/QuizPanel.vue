<script setup>
import { computed } from 'vue'
import { BookmarkPlus, BookmarkX, RotateCcw, Trophy } from 'lucide-vue-next'

const props = defineProps({
  quizzes: { type: Array, default: () => [] },
  answers: { type: Object, required: true },
  result: { type: Object, default: null },
  loading: Boolean
})

defineEmits(['submit', 'study', 'review', 'retry', 'next', 'toggle-wrong'])

const answeredAll = computed(() => props.quizzes.length > 0 && props.quizzes.every((quiz) => props.answers[quiz.id]))
const reviewById = computed(() => {
  const entries = props.result?.details || []
  return Object.fromEntries(entries.map((item) => [item.id, item]))
})
</script>

<template>
  <aside class="quiz-panel">
    <div class="panel-title">
      <Trophy :size="19" />
      <h2>测验与错题</h2>
    </div>
    <div v-if="result" class="score-card">
      <div>
        <strong>测验完成：{{ result.score }} / {{ result.total }}</strong>
        <span>正确率 {{ result.accuracy }}% · {{ result.level }} · 本次错题 {{ result.wrong_count }} 道，已自动加入错题归档。</span>
      </div>
      <p>{{ result.advice }}</p>
      <div class="result-actions">
        <button @click="$emit('study')">返回学习路径</button>
        <button @click="$emit('next')">学习下一章</button>
        <button @click="$emit('retry')"><RotateCcw :size="15" /> 重新测验</button>
      </div>
    </div>
    <div v-if="quizzes.length" class="quiz-list">
      <article v-for="(quiz, index) in quizzes" :key="quiz.id">
        <span class="question-index">第 {{ index + 1 }} / {{ quizzes.length }} 题</span>
        <div class="quiz-tags">
          <small>{{ quiz.type || '综合题' }}</small>
          <small>{{ quiz.difficulty || 'normal' }}</small>
        </div>
        <h3>{{ quiz.question }}</h3>
        <label v-for="option in quiz.options" :key="option" :class="{ selected: answers[quiz.id] === option }">
          <input v-model="answers[quiz.id]" type="radio" :name="`quiz-${quiz.id}`" :value="option" :disabled="Boolean(result)" />
          {{ option }}
        </label>
        <section
          v-if="reviewById[quiz.id]"
          :class="['inline-review', { correct: reviewById[quiz.id].correct, wrong: !reviewById[quiz.id].correct }]"
        >
          <div>
            <strong>{{ reviewById[quiz.id].correct ? '回答正确' : '回答错误' }}</strong>
            <button :disabled="loading" @click="$emit('toggle-wrong', reviewById[quiz.id])">
              <component :is="reviewById[quiz.id].wrong_answer_id ? BookmarkX : BookmarkPlus" :size="15" />
              {{ reviewById[quiz.id].wrong_answer_id ? '取消错题' : '加入错题' }}
            </button>
          </div>
          <small>你的答案：{{ reviewById[quiz.id].selected || '未选择' }}</small>
          <small>正确答案：{{ reviewById[quiz.id].answer }}</small>
          <p>{{ reviewById[quiz.id].explanation }}</p>
        </section>
      </article>
      <button v-if="!result" class="primary" :disabled="loading || !answeredAll" @click="$emit('submit')">提交测验</button>
    </div>
    <div v-else class="empty-state compact">
      <Trophy :size="30" />
      <h2>暂无测验</h2>
      <p>请先在学习路径中选择章节并生成测验。</p>
      <button @click="$emit('study')">打开学习路径</button>
    </div>
  </aside>
</template>
