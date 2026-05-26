<script setup>
import { computed } from 'vue'
import { CheckCircle2, CircleX, RotateCcw, Trophy } from 'lucide-vue-next'

const props = defineProps({
  quizzes: { type: Array, default: () => [] },
  answers: { type: Object, required: true },
  result: { type: Object, default: null },
  wrongs: { type: Array, default: () => [] },
  loading: Boolean
})

defineEmits(['submit', 'study', 'review', 'retry', 'next'])

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
        <div class="quiz-tags">
          <small>{{ quiz.type || '综合题' }}</small>
          <small>{{ quiz.difficulty || 'normal' }}</small>
        </div>
        <h3>{{ quiz.question }}</h3>
        <label v-for="option in quiz.options" :key="option" :class="{ selected: answers[quiz.id] === option }">
          <input v-model="answers[quiz.id]" type="radio" :name="`quiz-${quiz.id}`" :value="option" />
          {{ option }}
        </label>
      </article>
      <button class="primary" :disabled="loading || !answeredAll" @click="$emit('submit')">提交测验</button>
      <div v-if="result" class="score-card">
        <div>
          <strong>测验完成：{{ result.score }} / {{ result.total }}</strong>
          <span>正确率 {{ result.accuracy }}% · {{ result.level }} · 本次错题 {{ result.wrong_count }} 道，已自动加入错题归档。</span>
        </div>
        <p>{{ result.advice }}</p>
        <div class="result-actions">
          <button @click="$emit('review')">查看错题</button>
          <button @click="$emit('study')">返回学习路径</button>
          <button @click="$emit('next')">学习下一章</button>
          <button @click="$emit('retry')"><RotateCcw :size="15" /> 重新测验</button>
        </div>
        <section class="answer-review">
          <article v-for="(item, index) in result.details" :key="item.id" :class="{ correct: item.correct, wrong: !item.correct }">
            <strong>{{ item.correct ? '正确' : '错误' }} · 第 {{ index + 1 }} 题</strong>
            <p>{{ item.question }}</p>
            <small>你的答案：{{ item.selected || '未选择' }}</small>
            <small>正确答案：{{ item.answer }}</small>
            <p class="explanation">{{ item.explanation }}</p>
          </article>
        </section>
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
        <div class="quiz-tags">
          <small>{{ item.type || '综合题' }}</small>
          <small>{{ item.difficulty || 'normal' }}</small>
        </div>
        <p>{{ item.question }}</p>
        <small>你的答案：{{ item.selected || '未选择' }}</small>
        <small>正确答案：{{ item.answer }}</small>
        <p class="explanation">{{ item.explanation }}</p>
        <p class="review-advice">复盘建议：回到章节《{{ item.chapter_title }}》的重点难点和易错点部分重新阅读，再尝试复述本题考察的概念。</p>
      </article>
      <div v-if="!wrongs.length" class="empty-positive">
        <CheckCircle2 :size="18" />
        <span>暂无错题，继续保持。</span>
      </div>
    </div>
  </aside>
</template>
