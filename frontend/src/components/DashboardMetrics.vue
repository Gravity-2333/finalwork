<script setup>
defineProps({
  documentCount: Number,
  chapterCount: Number,
  progress: Number,
  wrongCount: Number
})
</script>

<template>
  <section class="dashboard">
    <div class="metric">
      <strong>{{ documentCount }}</strong>
      <span>知识库资料</span>
    </div>
    <div class="metric">
      <strong>{{ chapterCount }}</strong>
      <span>学习章节</span>
    </div>
    <div class="metric">
      <strong>{{ progress }}%</strong>
      <span>整体进度</span>
    </div>
    <div class="metric">
      <strong>{{ wrongCount }}</strong>
      <span>错题归档</span>
    </div>
  </section>
</template>

