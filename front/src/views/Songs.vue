<template>
  <div class="songs-page page-container">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="mb-20" />
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Upload /></el-icon>
          <span>{{ t('songUploadsAndDraws') }}</span>
          <el-tag v-if="enabled && !canUpload" type="info" size="small">{{
            t('submissionsAreCurrentlyClosed')
          }}</el-tag>
        </div>
      </template>
      <p class="page-hint">{{ t('uploadingASongAutomaticallyEntersYouInThe') }}</p>
      <el-alert
        v-if="!enabled"
        :title="t('theSongPhaseIsDisabledForThisCompetition')"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="!canUpload"
        :title="t('songSubmissionsAndNewDrawEntriesAreCurrently')"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form v-else label-width="100px" :disabled="busy" @submit.prevent="upload">
        <el-form-item :label="t('songTitle')" required>
          <el-input v-model="title" maxlength="100" :placeholder="t('enterTheSongTitle')" />
        </el-form-item>
        <el-form-item :label="t('audioFile')" required>
          <el-upload
            v-model:file-list="audioList"
            :auto-upload="false"
            :limit="1"
            accept="audio/*"
            :on-change="(file) => (audio = file.raw)"
            :on-remove="() => (audio = null)"
            :on-exceed="replaceAudio"
          >
            <el-button type="primary" :icon="Headset">{{ t('chooseAudioFile') }}</el-button>
            <template #tip
              ><div class="form-tip">
                {{ t('automaticallyEnterTheDrawAfterUploading') }}
              </div></template
            >
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button native-type="submit" type="primary" :icon="Upload" :loading="busy">{{
            t('uploadAndEnterDraw')
          }}</el-button>
          <el-button :icon="Pointer" :loading="busy" @click="join">{{
            t('enterDrawOnly')
          }}</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="enabled">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Trophy /></el-icon>
            <span>{{ t('myDraws') }}</span>
          </div>
        </template>
        <el-empty v-if="!draws.length" :description="t('notEnteredYet')" :image-size="80" />
        <el-descriptions v-else :column="1" border>
          <el-descriptions-item v-for="draw in draws" :key="draw.phase" :label="draw.phase">
            <el-tag v-if="draw.song" type="success">{{ draw.song.title }}</el-tag>
            <span v-else class="pending-text">{{ t('enteredAwaitingDraw') }}</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Headset /></el-icon>
            <span>{{ t('songResources') }}</span>
          </div>
        </template>
        <el-empty v-if="!songs.length" :description="t('noSongsYet')" />
        <div v-else class="songs-grid">
          <div v-for="song in songs" :key="song.id" class="song-item">
            <h3 class="song-title" :title="song.title">{{ song.title }}</h3>
            <audio controls preload="none" :src="song.audio_url" />
          </div>
        </div>
      </el-card>
    </template>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Headset, Trophy, Pointer } from '@element-plus/icons-vue'
import { getCompetitionStatus, getSongs, uploadSong, joinDraw, getMyDraws } from '../api'
const enabled = ref(false),
  canUpload = ref(false),
  error = ref(''),
  busy = ref(false),
  title = ref(''),
  audio = ref(null),
  audioList = ref([]),
  songs = ref([]),
  draws = ref([])
const load = async () => {
  try {
    const state = await getCompetitionStatus()
    enabled.value = state.capabilities.songs_enabled
    canUpload.value = state.capabilities.song_upload
    if (enabled.value) {
      ;[songs.value, draws.value] = await Promise.all([getSongs(), getMyDraws()])
    }
  } catch (err) {
    error.value = err.message
  }
}
const replaceAudio = (list) => {
  const raw = list[0]
  if (!raw) return
  audioList.value = [{ name: raw.name, raw, status: 'ready', uid: Date.now() }]
  audio.value = raw
}
const upload = async () => {
  if (!title.value.trim() || !audio.value) {
    ElMessage.warning(t('pleaseEnterASongTitleAndChooseAn'))
    return
  }
  busy.value = true
  try {
    const form = new FormData()
    form.append('title', title.value)
    form.append('audio_file', audio.value)
    await uploadSong(form)
    ElMessage.success(t('uploadedAndEntered'))
    title.value = ''
    audio.value = null
    audioList.value = []
    await load()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    busy.value = false
  }
}
const join = async () => {
  busy.value = true
  try {
    await joinDraw()
    ElMessage.success(t('entered'))
    await load()
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    busy.value = false
  }
}
onMounted(load)
</script>
<style scoped>
.songs-page {
  max-width: 1000px;
}

.mb-20 {
  margin-bottom: 20px;
}

.pending-text {
  color: var(--text-secondary);
}

.songs-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 16px;
}

.song-item {
  padding: 15px;
  border: 1px solid var(--border-color);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.2);
}

.song-title {
  font-size: 16px;
  font-weight: bold;
  margin-bottom: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

audio {
  display: block;
  width: 100%;
  height: 36px;
}
</style>
