<template>
  <nav class="navigation" aria-label="主导航">
    <router-link to="/" class="brand"
      ><img src="/res/xmmcglogo.png" alt="XMMCG" height="32"
    /></router-link>
    <router-link to="/">首页</router-link>
    <router-link to="/charts">谱面投稿</router-link>
    <router-link v-if="songsEnabled" to="/songs">歌曲抽选</router-link>
    <router-link to="/eval">评分</router-link>
    <span class="spacer" />
    <template v-if="currentUser">
      <router-link to="/profile">{{ currentUser.username }}</router-link>
      <el-button link @click="signOut">退出</el-button>
    </template>
    <template v-else
      ><router-link to="/login">登录</router-link
      ><router-link to="/register">注册</router-link></template
    >
  </nav>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getCompetitionStatus } from '../api'
import { currentUser, loadSession, endSession } from '../state/session'
const router = useRouter()
const songsEnabled = ref(false)
let timer
const refresh = async () => {
  try {
    songsEnabled.value = (await getCompetitionStatus()).capabilities.songs_enabled
  } catch {
    songsEnabled.value = false
  }
}
onMounted(async () => {
  await loadSession().catch(() => {})
  await refresh()
  timer = setInterval(refresh, 30000)
})
onUnmounted(() => clearInterval(timer))
const signOut = async () => {
  try {
    await endSession()
    router.push('/')
  } catch (error) {
    ElMessage.error(error.message)
  }
}
</script>
<style scoped>
.navigation {
  display: flex;
  align-items: center;
  gap: 22px;
  flex-wrap: wrap;
  padding: 16px 28px;
  border-bottom: 1px solid var(--border-color);
  background: var(--surface-color);
}
a {
  color: var(--text-secondary);
  text-decoration: none;
}
a.router-link-exact-active {
  color: var(--primary-color);
}
.spacer {
  flex: 1;
}
@media (max-width: 600px) {
  .navigation {
    gap: 14px;
    padding: 14px;
  }
  .brand {
    width: 100%;
  }
}
</style>
