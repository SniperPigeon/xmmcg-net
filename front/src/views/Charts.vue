<template>
  <div class="charts-page page-container">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="mb-20" />
    <el-card class="upload-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Upload /></el-icon>
          <span>谱面投稿</span>
        </div>
      </template>
      <p class="page-hint">上传完整谱面及配套素材。可自由选曲。</p>
      <el-alert
        v-if="!currentUser"
        title="登录后即可投稿"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="!canUpload"
        title="投稿尚未开放或已截止"
        type="warning"
        :closable="false"
        show-icon
      />
      <template v-else>
        <p v-if="submissionStatus?.competition_id" class="quota-text">
          <el-icon><InfoFilled /></el-icon>
          本届{{ submissionStatus.scope === 'identity' ? '大号与绑定小号合计' : '每个账号' }}
          {{
            submissionStatus.limit ? `最多参与 ${submissionStatus.limit} 张谱面` : '不限投稿数量'
          }}，已参与 {{ submissionStatus.used }} 张（含合作投稿）。
        </p>
        <el-alert
          v-if="submissionStatus && !submissionStatus.can_upload"
          title="本届投稿名额已用完（包含被绑定的合作谱面）"
          type="warning"
          :closable="false"
          show-icon
        />
      </template>
      <el-form
        v-if="currentUser && canUpload && submissionStatus?.can_upload"
        ref="formRef"
        :model="form"
        :rules="formRules"
        label-width="110px"
        class="upload-form"
        :disabled="uploading"
        @submit.prevent="upload"
      >
        <el-form-item label="曲名" prop="title" required>
          <el-input v-model="form.title" maxlength="200" placeholder="请输入曲名" />
        </el-form-item>
        <el-form-item label="谱师名义" prop="designer" required>
          <el-input v-model="form.designer" maxlength="100" placeholder="请输入谱师名义" />
        </el-form-item>
        <el-form-item v-if="submissionStatus.allow_collaboration" label="合作谱师">
          <el-select
            v-model="collaboratorIds"
            multiple
            filterable
            remote
            clearable
            style="width: 100%"
            :remote-method="(query) => searchAccounts('collaborator', query)"
            :loading="searching.collaborator"
            :placeholder="
              submissionStatus.require_collaborator_approval
                ? '可选，选择已授权你的合作谱师'
                : '可选，输入至少两个字符搜索用户名'
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
          <div class="form-tip">
            <template v-if="submissionStatus.require_collaborator_approval"
              >合作谱师需先在本页授权你的账号，才会出现在列表中。</template
            >提交成功后，本人和合作谱师都计入投稿名额。
          </div>
        </el-form-item>
        <el-form-item v-for="field in fileFields" :key="field.name" :required="field.required">
          <template #label>{{ field.label }}</template>
          <el-upload
            v-model:file-list="fileLists[field.name]"
            :auto-upload="false"
            :limit="1"
            :accept="field.accept"
            :list-type="field.name === 'cover_image' ? 'picture' : 'text'"
            :on-change="(file) => setFile(field.name, file)"
            :on-remove="() => setFile(field.name, null)"
            :on-exceed="(list) => replaceFile(field.name, list)"
          >
            <el-button :type="field.required ? 'primary' : 'default'" :icon="field.icon">
              {{ field.button }}
            </el-button>
            <template #tip>
              <div class="form-tip">{{ field.tip }}</div>
            </template>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button native-type="submit" type="primary" :icon="Upload" :loading="uploading">
            提交完整谱面
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card
      v-if="
        currentUser &&
        submissionStatus?.allow_collaboration &&
        submissionStatus.require_collaborator_approval
      "
      class="consent-card"
      shadow="hover"
    >
      <template #header>
        <div class="card-header">
          <el-icon><Connection /></el-icon>
          <span>授权合作投稿</span>
        </div>
      </template>
      <p class="page-hint">
        由对方上传合作谱面时，先选择对方的账号并授权。只有成功投稿才会占用你的名额。
      </p>
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
        <el-button type="primary" :disabled="!uploaderId" :loading="granting" @click="grant"
          >授权对方上传一张合作谱面</el-button
        >
      </div>
      <el-empty v-if="!consents.length" description="暂无授权" :image-size="60" />
      <div v-for="consent in consents" :key="consent.id" class="consent-row">
        <el-icon><User /></el-icon>
        <span class="consent-name">{{ consent.uploader.username }}</span>
        <el-tag :type="consent.used ? 'success' : 'info'" size="small">{{
          consent.used ? '已用于投稿' : '待对方投稿'
        }}</el-tag>
        <el-button
          v-if="!consent.used"
          link
          type="danger"
          :loading="revoking === consent.id"
          @click="revoke(consent)"
          >撤销授权</el-button
        >
      </div>
    </el-card>

    <el-card class="charts-list-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Tickets /></el-icon>
          <span>谱面列表</span>
          <div class="header-actions">
            <el-button circle :icon="Refresh" :loading="loading" @click="load" />
          </div>
        </div>
      </template>
      <el-tabs v-model="tab" @tab-change="switchTab">
        <el-tab-pane label="全部作品" name="all" />
        <el-tab-pane v-if="currentUser" label="我的投稿" name="mine" />
      </el-tabs>
      <el-skeleton v-if="loading" :rows="4" animated />
      <el-empty v-else-if="!charts.length" description="暂无谱面" />
      <div v-else class="charts-grid">
        <el-card
          v-for="chart in charts"
          :key="chart.id"
          class="chart-card"
          shadow="hover"
          :body-style="{ padding: '0' }"
        >
          <div class="chart-cover">
            <img v-if="chart.cover_url" :src="chart.cover_url" :alt="chart.title" />
            <div v-else class="cover-placeholder">
              <el-icon :size="48"><Picture /></el-icon>
            </div>
          </div>
          <div class="chart-info">
            <h3 class="chart-title" :title="chart.title">{{ chart.title }}</h3>
            <div class="chart-meta">
              <span class="designer">
                <el-icon><User /></el-icon>
                {{ chart.designer }}
              </span>
              <el-tag
                v-if="syncLabels[chart.net_sync_status]"
                size="small"
                :type="syncTypes[chart.net_sync_status]"
              >
                {{ syncLabels[chart.net_sync_status] }}
              </el-tag>
              <el-tag v-if="chart.is_collaboration" size="small" type="info">合作谱面</el-tag>
            </div>
            <p v-if="chart.is_collaboration && chart.contributors?.length" class="contributors">
              合作谱师：{{ chart.contributors.map((account) => account.username).join('、') }}
            </p>
            <audio v-if="chart.audio_url" controls preload="none" :src="chart.audio_url" />
          </div>
          <div class="chart-actions">
            <el-button
              type="primary"
              :icon="Download"
              :loading="downloading === chart.id"
              @click="download(chart.id)"
            >
              下载谱面包
            </el-button>
            <el-button
              v-if="
                tab === 'mine' &&
                chart.can_retry_sync &&
                ['failed', 'disabled', 'pending'].includes(chart.net_sync_status)
              "
              type="warning"
              :icon="Refresh"
              :loading="retrying === chart.id"
              @click="retry(chart)"
            >
              重试 Net 同步
            </el-button>
            <el-button
              v-if="chart.net_url"
              tag="a"
              :href="chart.net_url"
              target="_blank"
              rel="noopener noreferrer"
              :icon="Link"
            >
              在 Net 查看
            </el-button>
          </div>
        </el-card>
      </div>
      <el-pagination
        v-if="total > 20"
        v-model:current-page="page"
        class="pagination"
        :page-size="20"
        :total="total"
        layout="prev, pager, next"
        @current-change="load"
      />
    </el-card>
  </div>
</template>
<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  Upload,
  Tickets,
  Refresh,
  Picture,
  User,
  Download,
  Link,
  Document,
  Headset,
  VideoCamera,
  Connection,
  InfoFilled,
} from '@element-plus/icons-vue'
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
  formRef = ref(null)
const form = reactive({ title: '', designer: '' })
const formRules = {
  title: [{ required: true, whitespace: true, message: '请输入曲名', trigger: 'blur' }],
  designer: [{ required: true, whitespace: true, message: '请输入谱师名义', trigger: 'blur' }],
}
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
const fileLists = reactive({
  chart_file: [],
  audio_file: [],
  cover_image: [],
  background_video: [],
})
const fileFields = [
  {
    name: 'chart_file',
    label: '谱面文件',
    accept: '.txt',
    required: true,
    icon: Document,
    button: '选择谱面',
    tip: 'maidata.txt 谱面文件，曲名与谱师名义请在上方填写',
  },
  {
    name: 'audio_file',
    label: '音频',
    accept: 'audio/*',
    required: true,
    icon: Headset,
    button: '选择音频',
    tip: '谱面对应的音频文件',
  },
  {
    name: 'cover_image',
    label: '封面',
    accept: '.jpg,.jpeg,.png,.webp',
    required: true,
    icon: Picture,
    button: '选择封面',
    tip: '支持 JPG、PNG、WEBP 格式',
  },
  {
    name: 'background_video',
    label: '背景视频',
    accept: '.mp4',
    required: false,
    icon: VideoCamera,
    button: '选择视频（可选）',
    tip: '可选，支持 MP4 格式',
  },
]
let submissionKey = crypto.randomUUID()
const syncLabels = {
  pending: '待同步',
  syncing: '正在同步 Net',
  synced: '已同步 Net',
  failed: 'Net 同步失败',
  disabled: 'Net 同步未启用',
}
const syncTypes = {
  pending: 'info',
  syncing: 'warning',
  synced: 'success',
  failed: 'danger',
  disabled: 'info',
}
const setFile = (name, uploadFile) => {
  files[name] = uploadFile?.raw || null
  submissionKey = crypto.randomUUID()
}
// limit=1 时再次选择文件会触发 exceed，直接替换为新文件
const replaceFile = (name, list) => {
  const raw = list[0]
  if (!raw) return
  fileLists[name] = [{ name: raw.name, raw, status: 'ready', uid: Date.now() }]
  setFile(name, { raw })
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
const upload = async () => {
  if (!(await formRef.value.validate().catch(() => false))) return
  const missing = fileFields.find((field) => field.required && !files[field.name])
  if (missing) {
    ElMessage.warning(`请选择${missing.label}`)
    return
  }
  uploading.value = true
  try {
    const data = new FormData()
    for (const [name, file] of Object.entries(files)) if (file) data.append(name, file)
    data.append('title', form.title.trim())
    data.append('designer', form.designer.trim())
    data.append('submission_key', submissionKey)
    for (const id of collaboratorIds.value) data.append('collaborator_ids', id)
    await submitChart(data)
    ElMessage.success('投稿已保存')
    Object.keys(files).forEach((key) => delete files[key])
    Object.keys(fileLists).forEach((key) => (fileLists[key] = []))
    form.title = ''
    form.designer = ''
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
.charts-page {
  max-width: 1400px;
}

.mb-20 {
  margin-bottom: 20px;
}

.quota-text {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 16px;
  color: var(--text-secondary);
}

.consent-form {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.consent-form .el-select {
  min-width: 260px;
  flex: 1;
  max-width: 400px;
}

.consent-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-color);
}

.contributors {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 10px;
}

.upload-form {
  max-width: 760px;
}

.pagination {
  margin-top: 20px;
  justify-content: center;
}

.charts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-top: 20px;
}

.chart-card {
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.chart-cover {
  width: 100%;
  height: 200px;
  overflow: hidden;
  background: rgba(255, 255, 255, 0.04);
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s;
}

.chart-cover:hover img {
  transform: scale(1.05);
}

.cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--text-secondary);
}

.chart-info {
  padding: 15px;
  flex: 1;
}

.chart-title {
  font-size: 16px;
  font-weight: bold;
  margin: 0 0 10px 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.chart-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.designer {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  color: var(--text-secondary);
}

audio {
  width: 100%;
  height: 36px;
}

.chart-actions {
  padding: 0 15px 15px;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chart-actions .el-button {
  flex: 1;
  min-width: 100px;
  margin-left: 0;
}

@media (max-width: 768px) {
  .charts-grid {
    grid-template-columns: 1fr;
  }

  .upload-form :deep(.el-form-item) {
    flex-direction: column;
    align-items: stretch;
  }

  .upload-form :deep(.el-form-item__label) {
    justify-content: flex-start;
    width: auto !important;
  }
}
</style>
