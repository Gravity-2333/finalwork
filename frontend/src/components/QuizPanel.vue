<script setup>
import { Trophy } from 'lucide-vue-next'

defineProps({
  quizzes: { type: Array, default: () => [] },
  answers: { type: Object, required: true },
  result: { type: Object, default: null },
  wrongs: { type: Array, default: () => [] }
})

defineEmits(['submit'])
</script>

<template>
  <aside class="quiz-panel">
    <div class="panel-title">
      <Trophy :size="19" />
      <h2>测验与错题</h2>
    </div>
    <div v-if="quizzes.length" class="quiz-list">
      <article v-for="quiz in quizzes" :key="quiz.id">
        <h3>{{ quiz.question }}</h3>
        <label v-for="option in quiz.options" :key="option">
          <input v-model="answers[quiz.id]" type="radio" :name="`quiz-${quiz.id}`" :value="option" />
          {{ option }}
        </label>
      </article>
      <button class="primary" @click="$emit('submit')">提交测验</button>
      <p v-if="result" class="score">得分 {{ result.score }} / {{ result.total }}</p>
    </div>
    <p v-else class="empty">选择章节后点击“开始测验”。</p>

    <div class="wrong-list">
      <h3>错题归档</h3>
      <article v-for="item in wrongs" :key="item.id">
        <strong>{{ item.chapter_title }}</strong>
        <p>{{ item.question }}</p>
        <small>你的答案：{{ item.selected || '未选择' }}；正确答案：{{ item.answer }}</small>
      </article>
      <p v-if="!wrongs.length" class="empty">暂无错题，完成测验后自动记录。</p>
    </div>
  </aside>
</template>

