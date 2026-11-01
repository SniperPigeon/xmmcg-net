<template>
  <div class="songs-page page-container">
    <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon class="mb-20" />
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><Upload /></el-icon>
          <span>歌曲上传与抽选</span>
          <el-tag v-if="enabled && !canUpload" type="info" size="small">当前不接受投稿</el-tag>
        </div>
      </template>
      <p class="page-hint">
        上传歌曲后自动参加抽选，也可直接报名。抽选结果仅供创作参考，不限制谱面选曲。
      </p>
      <el-alert
        v-if="!enabled"
        title="本次比赛未启用歌曲阶段"
        type="info"
        :closable="false"
        show-icon
      />
      <el-alert
        v-else-if="!canUpload"
        title="当前不接受歌曲投稿或新报名"
        type="warning"
        :closable="false"
        show-icon
      />
      <el-form v-else label-width="100px" :disabled="busy" @submit.prevent="upload">
        <el-form-item label="歌曲标题" required>
          <el-input v-model="title" maxlength="100" placeholder="请输入歌曲标题" />
        </el-form-item>
        <el-form-item label="音频文件" required>
          <el-upload
            v-model:file-list="audioList"
            :auto-upload="false"
            :limit="1"
            accept="audio/*"
            :on-change="(file) => (audio = file.raw)"
            :on-remove="() => (audio = null)"
            :on-exceed="replaceAudio"
          >
            <el-button type="primary" :icon="Headset">选择音频文件</el-button>
            <template #tip><div class="form-tip">上传后自动参加抽选</div></template>
          </el-upload>
        </el-form-item>
        <el-form-item>
          <el-button native-type="submit" type="primary" :icon="Upload" :loading="busy">
            上传并参加抽选
          </el-button>
          <el-button :icon="Pointer" :loading="busy" @click="join">仅参加抽选</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <template v-if="enabled">
      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Trophy /></el-icon>
            <span>我的抽选</span>
          </div>
        </template>
        <el-empty v-if="!draws.length" description="尚未报名" :image-size="80" />
        <el-descriptions v-else :column="1" border>
          <el-descriptions-item v-for="draw in draws" :key="draw.phase" :label="draw.phase">
            <el-tag v-if="draw.song" type="success">{{ draw.song.title }}</el-tag>
            <span v-else class="pending-text">已报名，等待抽选</span>
          </el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card shadow="hover">
        <template #header>
          <div class="card-header">
            <el-icon><Headset /></el-icon>
            <span>歌曲素材</span>
          </div>
        </template>
        <el-empty v-if="!songs.length" description="暂无歌曲" />
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
    ElMessage.warning('请填写歌曲标题并选择音频文件')
    return
  }
  busy.value = true
  try {
    const form = new FormData()
    form.append('title', title.value)
    form.append('audio_file', audio.value)
    await uploadSong(form)
    ElMessage.success('已上传并报名')
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
    ElMessage.success('已报名')
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
