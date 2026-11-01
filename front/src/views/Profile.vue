<template>
  <div v-if="currentUser" class="profile-page page-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </div>
      </template>
      <el-descriptions :column="isMobile ? 1 : 2" border>
        <el-descriptions-item label="用户名">{{ currentUser.username }}</el-descriptions-item>
        <el-descriptions-item label="绑定大号">{{
          currentUser.main_account?.username || '独立账号'
        }}</el-descriptions-item>
        <el-descriptions-item label="邮箱">{{ currentUser.email }}</el-descriptions-item>
        <el-descriptions-item label="QQ号">{{ currentUser.qqid }}</el-descriptions-item>
        <el-descriptions-item label="注册时间">{{
          new Date(currentUser.date_joined).toLocaleString('zh-CN')
        }}</el-descriptions-item>
        <el-descriptions-item label="提交谱面">{{ currentUser.chartsCount }}</el-descriptions-item>
      </el-descriptions>
      <el-divider />
      <el-form label-width="80px" class="name-form" @submit.prevent="save">
        <el-form-item label="谱师名义">
          <el-input
            v-model="name"
            maxlength="50"
            show-word-limit
            placeholder="留空则不展示"
            class="name-input"
          />
          <el-button native-type="submit" type="primary" :loading="busy">保存</el-button>
        </el-form-item>
      </el-form>
      <el-divider />
      <div class="action-buttons">
        <el-button type="primary" :icon="Document" @click="$router.push('/charts')"
          >前往投稿</el-button
        >
        <el-button type="success" :icon="Star" @click="$router.push('/eval')"
          >查看评分任务</el-button
        >
      </div>
    </el-card>
  </div>
</template>
<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Document, Star } from '@element-plus/icons-vue'
import { currentUser, loadSession } from '../state/session'
import { updateUserProfile } from '../api'
const name = ref(''),
  busy = ref(false),
  isMobile = ref(false)
const checkMobile = () => (isMobile.value = window.innerWidth <= 768)
onUnmounted(() => window.removeEventListener('resize', checkMobile))
onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
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
.profile-page {
  max-width: 1000px;
}
.name-input {
  max-width: 320px;
  margin-right: 12px;
}
.action-buttons {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.action-buttons .el-button {
  margin-left: 0;
}
</style>
