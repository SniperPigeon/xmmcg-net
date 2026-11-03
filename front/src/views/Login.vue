<template>
  <div class="login-page">
    <el-card class="login-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('userLogin') }}</h2>
        </div>
      </template>
      <el-form
        ref="loginFormRef"
        :model="loginForm"
        :rules="rules"
        label-width="80px"
        @submit.prevent="handleLogin"
      >
        <el-form-item :label="t('username')" prop="username">
          <el-input
            v-model="loginForm.username"
            :placeholder="t('enterYourUsername')"
            :prefix-icon="User"
          />
        </el-form-item>
        <el-form-item :label="t('password')" prop="password">
          <el-input
            v-model="loginForm.password"
            type="password"
            :placeholder="t('enterYourPassword')"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin" style="width: 100%">{{
            t('logIn')
          }}</el-button>
        </el-form-item>
        <el-form-item>
          <div class="login-footer">
            <span>{{ t('donTHaveAnAccount') }}</span>
            <el-link type="primary" @click="$router.push('/register')">{{
              t('registerNow')
            }}</el-link>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

import { computed, ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { login } from '../api'
import { loadSession } from '../state/session'

const router = useRouter()
const route = useRoute()
const loginFormRef = ref(null)
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
})

const rules = computed(() => ({
  username: [
    { required: true, message: t('enterYourUsername'), trigger: 'blur' },
    { min: 3, max: 20, message: t('usernameMustBeCharacters'), trigger: 'blur' },
  ],
  password: [
    { required: true, message: t('enterYourPassword'), trigger: 'blur' },
    { min: 6, message: t('passwordMustBeAtLeastCharacters'), trigger: 'blur' },
  ],
}))

const handleLogin = async () => {
  if (!loginFormRef.value) return

  await loginFormRef.value.validate(async (valid) => {
    if (valid) {
      loading.value = true
      try {
        await login(loginForm.username, loginForm.password)
        await loadSession(true)
        ElMessage.success(t('loggedIn'))
        const next =
          typeof route.query.redirect === 'string' &&
          route.query.redirect.startsWith('/') &&
          !route.query.redirect.startsWith('//')
            ? route.query.redirect
            : '/profile'
        router.push(next)
      } catch (error) {
        ElMessage.error(error.message || t('loginFailedCheckYourUsernameAndPassword'))
      } finally {
        loading.value = false
      }
    }
  })
}
</script>

<style scoped>
.login-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 200px);
  padding: 20px;
}

.login-card {
  width: 100%;
  max-width: 400px;
}

.card-header {
  justify-content: center;
}

.card-header h2 {
  margin: 0;
  text-align: center;
  color: #303133;
}

.login-footer {
  width: 100%;
  text-align: center;
  font-size: 14px;
  color: #909399;
}

.login-footer span {
  margin-right: 5px;
}
</style>
