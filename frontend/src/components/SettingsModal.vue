<script setup>
import { X } from 'lucide-vue-next'

defineProps({
  settings: { type: Object, required: true },
  defaultPrompts: { type: Object, required: true }
})

defineEmits(['close', 'save', 'reset'])
</script>

<template>
  <div class="modal-backdrop" @click.self="$emit('close')">
    <section class="settings-modal" role="dialog" aria-modal="true" aria-label="系统设置">
      <header class="modal-header">
        <div>
          <h2>系统设置</h2>
          <p>资料会先转成文本知识库，再按任务取片段拼入提示词。</p>
        </div>
        <button class="icon-action" title="关闭" @click="$emit('close')"><X :size="18" /></button>
      </header>

      <div class="settings-grid">
        <article class="settings-section">
          <h3>资料处理</h3>
          <ul>
            <li>支持 txt / md / docx / pdf。</li>
            <li>PDF 逐页提取文字，docx 读取段落文字，普通文本直接读取。</li>
            <li>入库后按 650 字左右切片，调用 AI 时检索相关片段，不直接发送原文件。</li>
            <li>图片和 PPT 暂不开放上传，避免缺少 OCR 或视觉模型时识别失败。</li>
          </ul>
        </article>

        <article class="settings-section">
          <h3>上传限制</h3>
          <label>
            <span>单批文件数</span>
            <input v-model.number="settings.upload.maxFiles" type="number" min="1" max="20" disabled />
          </label>
          <label>
            <span>单文件大小</span>
            <input v-model="settings.upload.maxSizeText" disabled />
          </label>
        </article>

        <article class="settings-section prompt-section">
          <h3>AI 提示词模板</h3>
          <p class="token-help" v-pre>可用变量：{{context}}、{{chapter_title}}、{{chapter_objective}}</p>
          <label>
            <span>课程大纲</span>
            <textarea v-model="settings.prompts.outline" :placeholder="defaultPrompts.outline"></textarea>
          </label>
          <label>
            <span>章节内容</span>
            <textarea v-model="settings.prompts.chapter" :placeholder="defaultPrompts.chapter"></textarea>
          </label>
          <label>
            <span>测验出题</span>
            <textarea v-model="settings.prompts.quiz" :placeholder="defaultPrompts.quiz"></textarea>
          </label>
        </article>
      </div>

      <footer class="modal-actions">
        <button @click="$emit('reset')">恢复默认提示词</button>
        <button class="primary" @click="$emit('save')">保存设置</button>
      </footer>
    </section>
  </div>
</template>
