<template>
  <div class="contest-page">
    <h2>谱面投稿</h2>
    <p>上传完整谱面及配套素材。可自由选曲。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-card class="section">
      <template #header>提交作品</template>
      <el-alert v-if="!currentUser" title="登录后即可投稿" type="info" :closable="false" />
      <el-alert v-else-if="!canUpload" title="投稿尚未开放或已截止" type="info" :closable="false" />
      <p v-if="currentUser && submissionStatus?.competition_id">
        本届{{ submissionStatus.scope === 'identity' ? '大号与绑定小号合计' : '每个账号' }}
        {{
          submissionStatus.limit ? `最多参与 ${submissionStatus.limit} 张谱面` : '不限投稿数量'
        }}， 已参与 {{ submissionStatus.used }} 张（含合作投稿）。
      </p>
      <el-alert
        v-if="currentUser && canUpload && submissionStatus && !submissionStatus.can_upload"
        title="本届投稿名额已用完（包含被绑定的合作谱面）"
        type="info"
        :closable="false"
      />
      <form
        v-if="currentUser && canUpload && submissionStatus?.can_upload"
        @submit.prevent="upload"
        class="upload-grid"
      >
        <label>标题（可从谱面读取）<el-input v-model="title" maxlength="200" /></label>
        <label>谱师名义（可从谱面读取）<el-input v-model="designer" maxlength="100" /></label>
        <label v-if="submissionStatus.allow_collaboration">
          合作谱师（可选）
          <el-select
            v-model="collaboratorIds"
            multiple
            filterable
            remote
            clearable
            :remote-method="(query) => searchAccounts('collaborator', query)"
            :loading="searching.collaborator"
            :placeholder="
              submissionStatus.require_collaborator_approval
                ? '选择已授权你的合作谱师'
                : '输入至少两个字符搜索用户名'
            "
            @visible-change="(visible) => visible && searchAccounts('collaborator', '')"
          >
            <el-option
              v-for="account in accountOptions.collaborator"
              :key="account.id"
              :value="account.id"
              :label="account.username + (account.available ? '' : '（名额已用完）')"
              :disabled="!account.available"
            />
          </el-select>
          <small v-if="submissionStatus.require_collaborator_approval"
            >合作谱师需先在本页授权你的账号，才会出现在列表中。</small
          >
          <small>提交成功后，本人和合作谱师都计入投稿名额。</small>
        </label>
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
    <el-card
      v-if="
        currentUser &&
        submissionStatus?.allow_collaboration &&
        submissionStatus.require_collaborator_approval
      "
      class="section"
    >
      <template #header>授权合作投稿</template>
      <p>由对方上传合作谱面时，先选择对方的账号并授权。只有成功投稿才会占用你的名额。</p>
      <div v-if="canUpload && submissionStatus.can_upload" class="consent-form">
        <el-select
          v-model="uploaderId"
          filterable
          remote
          clearable
          placeholder="输入至少两个字符搜索上传者"
          :remote-method="(query) => searchAccounts('uploader', query)"
          :loading="searching.uploader"
        >
          <el-option
            v-for="account in accountOptions.uploader"
            :key="account.id"
            :value="account.id"
            :label="account.username + (account.available ? '' : '（名额已用完）')"
            :disabled="!account.available"
          />
        </el-select>
        <el-button :disabled="!uploaderId" :loading="granting" @click="grant"
          >授权对方上传一张合作谱面</el-button
        >
      </div>
      <p v-for="consent in consents" :key="consent.id" class="consent-row">
        <span
          >{{ consent.uploader.username }}：{{ consent.used ? '已用于投稿' : '待对方投稿' }}</span
        >
        <el-button
          v-if="!consent.used"
          link
          type="danger"
          :loading="revoking === consent.id"
          @click="revoke(consent)"
          >撤销授权</el-button
        >
      </p>
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
        <el-tag v-if="chart.is_collaboration" type="info">合作谱面</el-tag>
        <p v-if="chart.is_collaboration && chart.contributors?.length">
          合作谱师：{{ chart.contributors.map((account) => account.username).join('、') }}
        </p>
        <audio v-if="chart.audio_url" controls preload="none" :src="chart.audio_url" />
        <p v-if="syncLabels[chart.net_sync_status]">
          <el-tag>{{ syncLabels[chart.net_sync_status] }}</el-tag>
        </p>
        <el-button @click="download(chart.id)" :loading="downloading === chart.id"
          >下载谱面包</el-button
        >
        <el-button
          v-if="
            tab === 'mine' &&
            chart.can_retry_sync &&
            ['failed', 'disabled', 'pending'].includes(chart.net_sync_status)
          "
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
  getSubmissionStatus,
  searchCollaborationAccounts,
  getCollaborationConsents,
  grantCollaboration,
  revokeCollaboration,
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
const submissionStatus = ref(null),
  collaboratorIds = ref([]),
  uploaderId = ref(null),
  consents = ref([]),
  granting = ref(false),
  revoking = ref(null)
const accountOptions = reactive({ collaborator: [], uploader: [] })
const searching = reactive({ collaborator: false, uploader: false })
const searchVersions = { collaborator: 0, uploader: 0 }
const searchAccounts = async (purpose, query) => {
  const version = ++searchVersions[purpose]
  searching[purpose] = true
  try {
    const rows = await searchCollaborationAccounts(query, purpose)
    if (version === searchVersions[purpose]) accountOptions[purpose] = rows
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    if (version === searchVersions[purpose]) searching[purpose] = false
  }
}
const refreshSubmission = async () => {
  canUpload.value = (await getCompetitionStatus()).capabilities.chart_upload
  if (!currentUser.value) return
  submissionStatus.value = await getSubmissionStatus()
  if (!submissionStatus.value.allow_collaboration) collaboratorIds.value = []
  consents.value = submissionStatus.value.require_collaborator_approval
    ? await getCollaborationConsents()
    : []
}
const grant = async () => {
  granting.value = true
  try {
    await grantCollaboration(uploaderId.value)
    uploaderId.value = null
    ElMessage.success('已授权')
    await refreshSubmission()
  } catch (err) {
    ElMessage.error(err.message)
    await refreshSubmission().catch(() => {})
  } finally {
    granting.value = false
  }
}
const revoke = async (consent) => {
  revoking.value = consent.id
  try {
    await revokeCollaboration(consent.id)
    ElMessage.success('已撤销授权')
    await refreshSubmission()
  } catch (err) {
    ElMessage.error(err.message)
    await refreshSubmission().catch(() => {})
  } finally {
    revoking.value = null
  }
}
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
    for (const id of collaboratorIds.value) data.append('collaborator_ids', id)
    await submitChart(data)
    ElMessage.success('投稿已保存')
    event.target.reset()
    Object.keys(files).forEach((key) => delete files[key])
    title.value = ''
    designer.value = ''
    collaboratorIds.value = []
    submissionKey = crypto.randomUUID()
    tab.value = 'mine'
    page.value = 1
    await load()
    await refreshSubmission()
  } catch (err) {
    ElMessage.error(err.message)
    await Promise.all([refreshSubmission(), load()]).catch(() => {})
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
    await refreshSubmission()
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
.consent-form,
.consent-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.consent-form .el-select {
  min-width: 260px;
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
