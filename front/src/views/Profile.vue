<template>
  <div v-if="currentUser" class="profile-page page-container">
    <el-card shadow="hover">
      <template #header>
        <div class="card-header">
          <el-icon><User /></el-icon>
          <span>{{ t('profile') }}</span>
        </div>
      </template>
      <el-descriptions :column="isMobile ? 1 : 2" border>
        <el-descriptions-item :label="t('username')">{{
          currentUser.username
        }}</el-descriptions-item>
        <el-descriptions-item :label="t('linkedMainAccount')">{{
          currentUser.main_account?.username || t('independentAccount')
        }}</el-descriptions-item>
        <el-descriptions-item :label="t('email')">{{ currentUser.email }}</el-descriptions-item>
        <el-descriptions-item :label="t('qqNumber')">{{ currentUser.qqid }}</el-descriptions-item>
        <el-descriptions-item :label="t('registrationDate')">{{
          new Date(currentUser.date_joined).toLocaleString(locale)
        }}</el-descriptions-item>
        <el-descriptions-item :label="t('chartsSubmitted')">{{
          currentUser.chartsCount
        }}</el-descriptions-item>
      </el-descriptions>
      <el-divider />
      <el-form label-width="80px" class="name-form" @submit.prevent="save">
        <el-form-item :label="t('chartDesigner')">
          <el-input
            v-model="name"
            maxlength="50"
            show-word-limit
            :placeholder="t('leaveBlankToHide')"
            class="name-input"
          />
          <el-button native-type="submit" type="primary" :loading="busy">{{ t('save') }}</el-button>
        </el-form-item>
      </el-form>
      <el-divider />
      <div class="action-buttons">
        <el-button type="primary" :icon="Document" @click="$router.push('/charts')">{{
          t('goToSubmissions')
        }}</el-button>
        <el-button type="success" :icon="Star" @click="$router.push('/eval')">{{
          t('viewReviewTasks')
        }}</el-button>
      </div>
    </el-card>
  </div>
</template>
<script setup>
import { useI18n } from 'vue-i18n'
const { t, locale } = useI18n()

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
    ElMessage.success(t('saved'))
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
