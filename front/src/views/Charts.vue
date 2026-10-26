<template>
  <div class="contest-page">
    <h2>谱面投稿</h2>
    <p>上传完整谱面及配套素材。可自由选曲，无需先上传歌曲或参与抽选。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-card class="section">
      <template #header>提交作品</template>
      <el-alert v-if="!currentUser" title="登录后即可投稿" type="info" :closable="false" />
      <el-alert v-else-if="!canUpload" title="投稿尚未开放或已截止" type="info" :closable="false" />
      <form v-else @submit.prevent="upload" class="upload-grid">
        <label>标题（可从谱面读取）<el-input v-model="title" maxlength="200" /></label>
        <label>谱师名义（可从谱面读取）<el-input v-model="designer" maxlength="100" /></label>
        <label
          >谱面文件<input
            ref="chartInput"
            type="file"
            accept=".txt"
            required
            @change="setFile('chart_file', $event)"
        /></label>
        <label
          >音频<input type="file" accept="audio/*" required @change="setFile('audio_file', $event)"
        /></label>
        <label
          >封面<input
            type="file"
            accept=".jpg,.jpeg,.png,.webp"
            required
            @change="setFile('cover_image', $event)"
        /></label>
        <label
          >背景视频（可选）<input
            type="file"
            accept=".mp4"
            @change="setFile('background_video', $event)"
        /></label>
        <el-button native-type="submit" type="primary" :loading="uploading">提交完整谱面</el-button>
      </form>
    </el-card>
    <el-tabs v-model="tab" @tab-change="switchTab">
      <el-tab-pane label="全部作品" name="all" />
      <el-tab-pane v-if="currentUser" label="我的投稿" name="mine" />
    </el-tabs>
    <el-skeleton v-if="loading" :rows="4" animated />
    <el-empty v-else-if="!charts.length" description="暂无谱面" />
    <div v-else class="chart-grid">
      <el-card v-for="chart in charts" :key="chart.id">
        <img v-if="chart.cover_url" :src="chart.cover_url" :alt="chart.title" class="cover" />
        <h3>{{ chart.title }}</h3>
        <p>{{ chart.designer }}</p>
        <audio v-if="chart.audio_url" controls preload="none" :src="chart.audio_url" />
        <p v-if="syncLabels[chart.net_sync_status]">
          <el-tag>{{ syncLabels[chart.net_sync_status] }}</el-tag>
        </p>
        <el-button @click="download(chart.id)" :loading="downloading === chart.id"
          >下载谱面包</el-button
        >
        <el-button
          v-if="tab === 'mine' && ['failed', 'disabled', 'pending'].includes(chart.net_sync_status)"
          @click="retry(chart)"
          :loading="retrying === chart.id"
          >重试 Net 同步</el-button
        >
        <a v-if="chart.net_url" :href="chart.net_url" target="_blank" rel="noopener noreferrer"
          >在 Net 查看</a
        >
      </el-card>
    </div>
    <el-pagination
      v-if="total > 20"
      v-model:current-page="page"
      :page-size="20"
      :total="total"
      layout="prev, pager, next"
      @current-change="load"
    />
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  getCharts,
  getMyCharts,
  submitChart,
  getCompetitionStatus,
  downloadBundle,
  retryChartSync,
} from '../api'
import { currentUser, loadSession } from '../state/session'
const charts = ref([]),
  total = ref(0),
  page = ref(1),
  tab = ref('all'),
  loading = ref(true),
  uploading = ref(false)
const downloading = ref(null),
  retrying = ref(null),
  error = ref(''),
  canUpload = ref(false),
  title = ref(''),
  designer = ref('')
const files = reactive({})
let submissionKey = crypto.randomUUID()
const syncLabels = {
  pending: '待同步',
  syncing: '正在同步 Net',
  synced: '已同步 Net',
  failed: 'Net 同步失败',
  disabled: 'Net 同步未启用',
}
const setFile = (name, event) => {
  files[name] = event.target.files[0]
  submissionKey = crypto.randomUUID()
}
const load = async () => {
  loading.value = true
  try {
    const result = await (tab.value === 'mine' ? getMyCharts : getCharts)({ page: page.value })
    charts.value = result.results
    total.value = result.count
    error.value = ''
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
const switchTab = () => {
  page.value = 1
  load()
}
const upload = async (event) => {
  uploading.value = true
  try {
    const data = new FormData()
    for (const [name, file] of Object.entries(files)) if (file) data.append(name, file)
    data.append('title', title.value)
    data.append('designer', designer.value)
    data.append('submission_key', submissionKey)
    await submitChart(data)
    ElMessage.success('投稿已保存')
    event.target.reset()
    Object.keys(files).forEach((key) => delete files[key])
    title.value = ''
    designer.value = ''
    submissionKey = crypto.randomUUID()
    tab.value = 'mine'
    page.value = 1
    await load()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    uploading.value = false
  }
}
const download = async (id) => {
  downloading.value = id
  try {
    await downloadBundle(id)
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    downloading.value = null
  }
}
const retry = async (chart) => {
  retrying.value = chart.id
  try {
    Object.assign(chart, await retryChartSync(chart.id))
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    retrying.value = null
  }
}
onMounted(async () => {
  await loadSession().catch(() => {})
  try {
    canUpload.value = (await getCompetitionStatus()).capabilities.chart_upload
  } catch (err) {
    error.value = err.message
  }
  await load()
})
</script>
<style scoped>
.contest-page {
  max-width: 1200px;
  margin: auto;
}
.section {
  margin: 24px 0;
}
.upload-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 20px;
}
label {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
input[type='file'] {
  max-width: 100%;
}
.chart-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin: 20px 0;
}
.cover {
  width: 100%;
  aspect-ratio: 16/9;
  object-fit: cover;
  border-radius: 6px;
}
audio {
  width: 100%;
}
</style>
