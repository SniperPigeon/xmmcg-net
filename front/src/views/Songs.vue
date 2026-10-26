<template>
  <div class="songs-page">
    <h2>歌曲上传与抽选</h2>
    <p>上传歌曲后自动参加抽选，也可直接报名。抽选结果仅供创作参考，不限制谱面选曲。</p>
    <el-alert v-if="error" :title="error" type="error" :closable="false" />
    <el-alert v-if="!enabled" title="本次比赛未启用歌曲阶段" type="info" :closable="false" />
    <template v-else>
      <el-card>
        <form v-if="canUpload" @submit.prevent="upload">
          <label>歌曲标题<el-input v-model="title" required maxlength="100" /></label>
          <label
            >音频文件<input
              type="file"
              accept="audio/*"
              required
              @change="audio = $event.target.files[0]"
          /></label>
          <el-button native-type="submit" type="primary" :loading="busy">上传并参加抽选</el-button>
        </form>
        <el-button v-if="canUpload" @click="join" :loading="busy">仅参加抽选</el-button>
        <p v-else>当前不接受歌曲投稿或新报名。</p>
      </el-card>
      <h3>我的抽选</h3>
      <el-empty v-if="!draws.length" description="尚未报名" />
      <p v-for="draw in draws" :key="draw.phase">
        {{ draw.phase }}：{{ draw.song?.title || '已报名，等待抽选' }}
      </p>
      <h3>歌曲素材</h3>
      <el-card v-for="song in songs" :key="song.id" class="song"
        ><strong>{{ song.title }}</strong
        ><audio controls preload="none" :src="song.audio_url"
      /></el-card>
    </template>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCompetitionStatus, getSongs, uploadSong, joinDraw, getMyDraws } from '../api'
const enabled = ref(false),
  canUpload = ref(false),
  error = ref(''),
  busy = ref(false),
  title = ref(''),
  audio = ref(null),
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
const upload = async (event) => {
  busy.value = true
  try {
    const form = new FormData()
    form.append('title', title.value)
    form.append('audio_file', audio.value)
    await uploadSong(form)
    ElMessage.success('已上传并报名')
    title.value = ''
    audio.value = null
    event.target.reset()
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
  max-width: 900px;
  margin: auto;
}
form {
  display: grid;
  gap: 18px;
  margin-bottom: 18px;
}
label {
  display: grid;
  gap: 8px;
}
.song {
  margin: 12px 0;
}
audio {
  display: block;
  width: 100%;
  margin-top: 12px;
}
</style>
