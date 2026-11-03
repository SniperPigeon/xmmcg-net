<template>
  <div class="charts-page page-container">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="mb-20" />
    <el-card class="upload-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Upload /></el-icon>
          <span>{{ t('submitCharts') }}</span>
        </div>
      </template>
      <p class="page-hint">{{ t('uploadACompleteChartWithItsAssetsYou') }}</p>
      <el-alert
        v-if="!currentUser"
        :title="t('logInToSubmitAChart')"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="!canUpload"
        :title="t('submissionsHaveNotOpenedOrHaveClosed')"
        type="warning"
        :closable="false"
        show-icon
      />
      <template v-else>
        <p v-if="submissionStatus?.competition_id" class="quota-text">
          <el-icon><InfoFilled /></el-icon
          >{{
            t('thisRoundValueValueAlreadyParticipatingInValue', {
              value0:
                submissionStatus.scope === 'identity'
                  ? t('theMainAccountAndAllLinkedAccountsCombined')
                  : t('eachAccount'),
              value1: submissionStatus.limit
                ? t('upToValueCharts', { value0: submissionStatus.limit })
                : t('unlimitedSubmissions'),
              value2: submissionStatus.used,
            })
          }}
        </p>
        <el-alert
          v-if="submissionStatus && !submissionStatus.can_upload"
          :title="t('yourSubmissionQuotaForThisRoundIsExhausted')"
          type="warning"
          :closable="false"
          show-icon
        />
      </template>
      <el-form
        v-if="currentUser && canUpload && submissionStatus?.can_upload"
        ref="formRef"
        :model="form"
        label-width="110px"
        class="upload-form"
        :disabled="uploading"
        @submit.prevent="upload"
      >
        <el-form-item :label="t('title')">
          <el-input
            v-model="form.title"
            maxlength="200"
            :placeholder="t('leaveBlankToReadFromTheChart')"
          />
        </el-form-item>
        <el-form-item :label="t('chartDesigner')">
          <el-input
            v-model="form.designer"
            maxlength="100"
            :placeholder="t('leaveBlankToReadFromTheChart')"
          />
        </el-form-item>
        <el-form-item v-if="submissionStatus.allow_collaboration" :label="t('collaborators')">
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
                ? t('optionalSelectCollaboratorsWhoHaveAuthorizedYou')
                : t('optionalEnterAtLeastTwoCharactersToSearch')
            "
            @visible-change="(visible) => visible && searchAccounts('collaborator', '')"
          >
            <el-option
              v-for="account in accountOptions.collaborator"
              :key="account.id"
              :value="account.id"
              :label="account.username + (account.available ? '' : t('quotaExhausted'))"
              :disabled="!account.available"
            />
          </el-select>
          <div class="form-tip">
            <template v-if="submissionStatus.require_collaborator_approval">{{
              t('collaboratorsMustAuthorizeYourAccountOnThisPage')
            }}</template
            >{{ t('aSuccessfulSubmissionCountsTowardBothYourQuota') }}
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
          <el-button native-type="submit" type="primary" :icon="Upload" :loading="uploading">{{
            t('submitCompleteChart')
          }}</el-button>
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
          <span>{{ t('authorizeCollaboration') }}</span>
        </div>
      </template>
      <p class="page-hint">{{ t('ifSomeoneElseWillUploadYourCollaborationSelect') }}</p>
      <div v-if="canUpload && submissionStatus.can_upload" class="consent-form">
        <el-select
          v-model="uploaderId"
          filterable
          remote
          clearable
          :placeholder="t('enterAtLeastTwoCharactersToSearchUploaders')"
          :remote-method="(query) => searchAccounts('uploader', query)"
          :loading="searching.uploader"
        >
          <el-option
            v-for="account in accountOptions.uploader"
            :key="account.id"
            :value="account.id"
            :label="account.username + (account.available ? '' : t('quotaExhausted'))"
            :disabled="!account.available"
          />
        </el-select>
        <el-button type="primary" :disabled="!uploaderId" :loading="granting" @click="grant">{{
          t('authorizeOneCollaborationUpload')
        }}</el-button>
      </div>
      <el-empty v-if="!consents.length" :description="t('noAuthorizationsYet')" :image-size="60" />
      <div v-for="consent in consents" :key="consent.id" class="consent-row">
        <el-icon><User /></el-icon>
        <span class="consent-name">{{ consent.uploader.username }}</span>
        <el-tag :type="consent.used ? 'success' : 'info'" size="small">{{
          consent.used ? t('usedForASubmission') : t('awaitingSubmission')
        }}</el-tag>
        <el-button
          v-if="!consent.used"
          link
          type="danger"
          :loading="revoking === consent.id"
          @click="revoke(consent)"
          >{{ t('revokeAuthorization') }}</el-button
        >
      </div>
    </el-card>

    <el-card class="charts-list-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Tickets /></el-icon>
          <span>{{ t('chartList') }}</span>
          <div class="header-actions">
            <el-button circle :icon="Refresh" :loading="loading" @click="load" />
          </div>
        </div>
      </template>
      <el-tabs v-model="tab" @tab-change="switchTab">
        <el-tab-pane :label="t('allCharts')" name="all" />
        <el-tab-pane v-if="currentUser" :label="t('mySubmissions')" name="mine" />
      </el-tabs>
      <el-skeleton v-if="loading" :rows="4" animated />
      <el-empty v-else-if="!charts.length" :description="t('noChartsYet')" />
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
              <el-tag v-if="chart.is_collaboration" size="small" type="info">{{
                t('collaboration')
              }}</el-tag>
            </div>
            <p v-if="chart.is_collaboration && chart.contributors?.length" class="contributors">
              {{
                t('collaboratorsValue', {
                  value0: chart.contributors.map((account) => account.username).join('、'),
                })
              }}
            </p>
            <audio v-if="chart.audio_url" controls preload="none" :src="chart.audio_url" />
          </div>
          <div class="chart-actions">
            <el-button
              type="primary"
              :icon="Download"
              :loading="downloading === chart.id"
              @click="download(chart.id)"
              >{{ t('downloadChartBundle') }}</el-button
            >
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
              >{{ t('retryNetSync') }}</el-button
            >
            <el-button
              v-if="chart.net_url"
              tag="a"
              :href="chart.net_url"
              target="_blank"
              rel="noopener noreferrer"
              :icon="Link"
              >{{ t('viewOnNet') }}</el-button
            >
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
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

import { computed, ref, reactive, onMounted } from 'vue'
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
    ElMessage.success(t('authorizationGranted'))
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
    ElMessage.success(t('authorizationRevoked'))
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
const fileFields = computed(() => [
  {
    name: 'chart_file',
    label: t('chartFile'),
    accept: '.txt',
    required: true,
    icon: Document,
    button: t('chooseChart'),
    tip: t('maidataTxtChartFileTitleAndDesignerAre'),
  },
  {
    name: 'audio_file',
    label: t('audio'),
    accept: 'audio/*',
    required: true,
    icon: Headset,
    button: t('chooseAudio'),
    tip: t('audioFileForThisChart'),
  },
  {
    name: 'cover_image',
    label: t('coverImage'),
    accept: '.jpg,.jpeg,.png,.webp',
    required: true,
    icon: Picture,
    button: t('chooseCoverImage'),
    tip: t('supportsJpgPngAndWebp'),
  },
  {
    name: 'background_video',
    label: t('backgroundVideo'),
    accept: '.mp4',
    required: false,
    icon: VideoCamera,
    button: t('chooseVideoOptional'),
    tip: t('optionalSupportsMp'),
  },
])
let submissionKey = crypto.randomUUID()
const syncLabels = computed(() => ({
  pending: t('pendingSync'),
  syncing: t('syncingToNet'),
  synced: t('syncedToNet'),
  failed: t('netSyncFailed'),
  disabled: t('netSyncDisabled'),
}))
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
  const missing = fileFields.value.find((field) => field.required && !files[field.name])
  if (missing) {
    ElMessage.warning(t('pleaseSelectValue', { value0: missing.label }))
    return
  }
  uploading.value = true
  try {
    const data = new FormData()
    for (const [name, file] of Object.entries(files)) if (file) data.append(name, file)
    data.append('title', form.title)
    data.append('designer', form.designer)
    data.append('submission_key', submissionKey)
    for (const id of collaboratorIds.value) data.append('collaborator_ids', id)
    await submitChart(data)
    ElMessage.success(t('submissionSaved'))
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
