const headers = { 'Content-Type': 'application/json' }

async function request(path, options = {}) {
  const response = await fetch(`/api${path}`, options)
  const data = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(data.detail || '请求失败，请检查后端服务。')
  }
  return data
}

export function health() {
  return request('/health')
}

export function listDocuments() {
  return request('/documents')
}

export function uploadDocuments(files) {
  const form = new FormData()
  files.forEach((file) => form.append('files', file))
  return request('/documents/upload-batch', { method: 'POST', body: form })
}

export function deleteDocument(id) {
  return request(`/documents/${id}`, { method: 'DELETE' })
}

export function clearDocuments() {
  return request('/documents', { method: 'DELETE' })
}

export function createOutline(config) {
  return request('/outline', {
    method: 'POST',
    headers,
    body: JSON.stringify(config)
  })
}

export function listChapters() {
  return request('/chapters')
}

export function createChapterContent(id, config) {
  return request(`/chapters/${id}/content`, {
    method: 'POST',
    headers,
    body: JSON.stringify(config)
  })
}

export function createQuiz(id, config) {
  return request(`/chapters/${id}/quiz`, {
    method: 'POST',
    headers,
    body: JSON.stringify(config)
  })
}

export function submitQuiz(id, answers) {
  return request(`/chapters/${id}/submit`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ answers })
  })
}

export function listWrongAnswers() {
  return request('/wrong-answers')
}

export function testProvider(config) {
  return request('/provider/test', {
    method: 'POST',
    headers,
    body: JSON.stringify(config)
  })
}

export function listCloudOllamaModels(config) {
  return request('/provider/cloud-ollama/models', {
    method: 'POST',
    headers,
    body: JSON.stringify(config)
  })
}

export function faceProfile(username = '杨翰飞') {
  return request(`/face/profile?username=${encodeURIComponent(username)}`)
}

export function faceEnroll(payload) {
  return request('/face/enroll', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  })
}

export function faceLogin(payload) {
  return request('/face-login', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  })
}
