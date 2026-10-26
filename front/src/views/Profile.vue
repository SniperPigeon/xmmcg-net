<template>
  <el-card class="profile-card" v-if="currentUser">
    <template #header><h2>个人中心</h2></template>
    <el-descriptions :column="1" border>
      <el-descriptions-item label="用户名">{{ currentUser.username }}</el-descriptions-item>
      <el-descriptions-item label="绑定大号">{{
        currentUser.main_account?.username || '独立账号'
      }}</el-descriptions-item>
      <el-descriptions-item label="邮箱">{{ currentUser.email }}</el-descriptions-item>
      <el-descriptions-item label="QQ">{{ currentUser.qqid }}</el-descriptions-item>
      <el-descriptions-item label="谱面数量">{{ currentUser.chartsCount }}</el-descriptions-item>
    </el-descriptions>
    <form @submit.prevent="save">
      <label>谱师名义<el-input v-model="name" maxlength="50" /></label
      ><el-button native-type="submit" :loading="busy">保存</el-button>
    </form>
    <el-button type="primary" @click="$router.push('/charts')">前往投稿</el-button>
    <el-button @click="$router.push('/eval')">查看评分任务</el-button>
    <p v-if="currentUser.is_staff">
      <a :href="adminUrl" target="_blank" rel="noopener">管理后台：阶段、公告、抽选和评分分配</a>
    </p>
  </el-card>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { currentUser, loadSession } from '../state/session'
import { updateUserProfile } from '../api'
const adminUrl =
  new URL(import.meta.env.VITE_API_BASE_URL || '/api', window.location.origin).origin + '/admin/'
const name = ref(''),
  busy = ref(false)
onMounted(async () => {
  await loadSession(true)
  name.value = currentUser.value?.preferred_name || ''
})
const save = async () => {
  busy.value = true
  try {
    currentUser.value = await updateUserProfile({ preferred_name: name.value })
    ElMessage.success('已保存')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    busy.value = false
  }
}
</script>
<style scoped>
.profile-card {
  max-width: 800px;
  margin: auto;
}
form {
  margin: 24px 0;
  display: flex;
  align-items: end;
  gap: 16px;
}
label {
  display: grid;
  gap: 8px;
}
</style>
