<script setup>
import { ref } from 'vue'
import { FileText, Mic, SlidersHorizontal, UploadCloud, X } from 'lucide-vue-next'
import PromptTextarea from './PromptTextarea.vue'

defineProps({
  settings: { type: Object, required: true },
  defaultPrompts: { type: Object, required: true }
})

defineEmits(['close', 'save', 'reset'])

const activeSection = ref('processing')
const sections = [
  { id: 'processing', label: '资料处理', icon: FileText },
  { id: 'upload', label: '上传限制', icon: UploadCloud },
  { id: 'voice', label: '语音识别', icon: Mic },
  { id: 'prompts', label: '提示词模板', icon: SlidersHorizontal }
]
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

      <div class="settings-body">
        <aside class="settings-sidebar" aria-label="设置分类">
          <button
            v-for="section in sections"
            :key="section.id"
            :class="{ selected: activeSection === section.id }"
            @click="activeSection = section.id"
          >
            <component :is="section.icon" :size="17" />
            {{ section.label }}
          </button>
        </aside>

        <div class="settings-content">
          <article v-if="activeSection === 'processing'" class="settings-section">
            <h3>资料处理</h3>
            <ul>
              <li>支持 txt / md / docx / pdf。</li>
              <li>PDF 逐页提取文字，docx 读取段落文字，普通文本直接读取。</li>
              <li>入库后按 650 字左右切片，调用 AI 时检索相关片段，不直接发送原文件。</li>
              <li>图片和 PPT 暂不开放上传，避免缺少 OCR 或视觉模型时识别失败。</li>
            </ul>
          </article>

          <article v-if="activeSection === 'upload'" class="settings-section">
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

          <article v-if="activeSection === 'voice'" class="settings-section">
            <h3>语音识别</h3>
            <label>
              <span>识别方式</span>
              <select v-model="settings.voice.provider">
                <option value="web_speech">浏览器 Web Speech</option>
                <option value="xfyun">讯飞 API 服务</option>
              </select>
            </label>
            <ul>
              <li>Web Speech 直接使用浏览器识别服务，配置简单，但受浏览器和网络环境影响。</li>
              <li>讯飞 API 服务会先在前端录音并转为 16k PCM，再由后端代理调用讯飞语音听写。</li>
              <li>讯飞凭证只从后端环境变量读取，避免密钥暴露到浏览器端。</li>
            </ul>
          </article>

          <article v-if="activeSection === 'prompts'" class="settings-section prompt-section">
            <h3>AI 提示词模板</h3>
            <p class="token-help" v-pre>可用变量：{{context}}、{{chapter_count}}、{{chapter_title}}、{{chapter_objective}}</p>
            <div class="prompt-editor-grid">
              <label>
                <span>课程大纲</span>
                <PromptTextarea v-model="settings.prompts.outline" :placeholder="defaultPrompts.outline" />
              </label>
              <label>
                <span>章节内容</span>
                <PromptTextarea v-model="settings.prompts.chapter" :placeholder="defaultPrompts.chapter" />
              </label>
              <label>
                <span>测验出题</span>
                <PromptTextarea v-model="settings.prompts.quiz" :placeholder="defaultPrompts.quiz" />
              </label>
            </div>
          </article>
        </div>
      </div>

      <footer class="modal-actions">
        <button @click="$emit('reset')">恢复默认提示词</button>
        <button class="primary" @click="$emit('save')">保存设置</button>
      </footer>
    </section>
  </div>
</template>
