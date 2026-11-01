<template>
  <div class="register-page">
    <el-card class="register-card">
      <template #header>
        <div class="title-header"><h2>用户注册</h2></div>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="96px"
        :disabled="busy"
        @submit.prevent="submit"
      >
        <el-form-item label="用户名" prop="username">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            :prefix-icon="User"
            autocomplete="username"
            maxlength="20"
          />
        </el-form-item>
        <el-form-item label-width="0" class="bind-switch">
          <el-checkbox v-model="bindMain">这是我的小号，绑定已有大号</el-checkbox>
        </el-form-item>
        <template v-if="bindMain">
          <el-form-item label="选择大号" prop="main_account_id">
            <el-select
              v-model="form.main_account_id"
              filterable
              remote
              :remote-method="search"
              :loading="searching"
              placeholder="输入至少两个字符搜索用户名"
              style="width: 100%"
              ><el-option
                v-for="account in accounts"
                :key="account.id"
                :label="account.username"
                :value="account.id"
            /></el-select>
          </el-form-item>
          <el-form-item label="大号密码" prop="main_password">
            <el-input
              v-model="form.main_password"
              type="password"
              show-password
              placeholder="验证大号密码"
              :prefix-icon="Lock"
              autocomplete="off"
            />
          </el-form-item>
          <p class="bind-hint">联系方式使用大号的资料。一个大号可绑定多个小号。</p>
        </template>
        <template v-else>
          <el-form-item label="QQ号" prop="qqid">
            <el-input
              v-model="form.qqid"
              placeholder="请输入主要使用的QQ号"
              :prefix-icon="ChatDotRound"
              inputmode="numeric"
            />
          </el-form-item>
          <el-form-item label="邮箱" prop="email">
            <el-input
              v-model="form.email"
              type="email"
              placeholder="请输入邮箱"
              :prefix-icon="Message"
              autocomplete="email"
            />
          </el-form-item>
        </template>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="请输入新账号密码"
            :prefix-icon="Lock"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item label="确认密码" prop="password_confirm">
          <el-input
            v-model="form.password_confirm"
            type="password"
            show-password
            placeholder="请再次输入密码"
            :prefix-icon="Lock"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button native-type="submit" type="primary" :loading="busy" style="width: 100%"
            >注册</el-button
          >
        </el-form-item>
        <el-form-item>
          <div class="register-footer">
            <span>已有账号？</span>
            <el-link type="primary" @click="$router.push('/login')">立即登录</el-link>
          </div>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>
<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User, Lock, Message, ChatDotRound } from '@element-plus/icons-vue'
import { register, searchAccounts } from '../api'
const router = useRouter(),
  busy = ref(false),
  bindMain = ref(false),
  searching = ref(false),
  accounts = ref([]),
  formRef = ref(null)
const form = reactive({
  username: '',
  qqid: '',
  email: '',
  password: '',
  password_confirm: '',
  main_account_id: null,
  main_password: '',
})
const required = (message) => ({ required: true, message, trigger: 'blur' })
const rules = {
  username: [
    required('请输入用户名'),
    { min: 3, max: 20, message: '用户名长度为 3-20 个字符', trigger: 'blur' },
  ],
  main_account_id: [{ required: true, message: '请选择大号', trigger: 'change' }],
  main_password: [required('请输入大号密码')],
  qqid: [
    required('请输入QQ号'),
    { pattern: /^[1-9][0-9]{4,14}$/, message: 'QQ号格式不正确', trigger: 'blur' },
  ],
  email: [required('请输入邮箱'), { type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
  password: [required('请输入密码')],
  password_confirm: [required('请再次输入密码')],
}
let searchVersion = 0
const search = async (query) => {
  const version = ++searchVersion
  searching.value = true
  try {
    const result = await searchAccounts(query)
    if (version === searchVersion) accounts.value = result
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    if (version === searchVersion) searching.value = false
  }
}
const submit = async () => {
  if (!(await formRef.value?.validate().catch(() => false))) return
  if (form.password !== form.password_confirm) {
    ElMessage.error('两次密码不一致')
    return
  }
  if (bindMain.value && !form.main_account_id) {
    ElMessage.error('请选择大号')
    return
  }
  busy.value = true
  try {
    const data = {
      username: form.username,
      password: form.password,
      password_confirm: form.password_confirm,
    }
    Object.assign(
      data,
      bindMain.value
        ? { main_account_id: form.main_account_id, main_password: form.main_password }
        : { email: form.email, qqid: form.qqid },
    )
    await register(data)
    form.main_password = ''
    ElMessage.success('注册成功，请登录')
    router.push('/login')
  } catch (err) {
    ElMessage.error(err.message)
  } finally {
    busy.value = false
  }
}
</script>
<style scoped>
.register-page {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 260px);
  padding: 20px;
}

.register-card {
  width: 100%;
  max-width: 460px;
}

.title-header h2 {
  margin: 0;
  text-align: center;
}

.bind-switch {
  margin-bottom: 12px;
}

.bind-hint {
  margin: -8px 0 18px 96px;
  color: var(--text-secondary);
  font-size: 12px;
}

.register-footer {
  width: 100%;
  text-align: center;
  font-size: 14px;
  color: var(--text-secondary);
}

.register-footer span {
  margin-right: 5px;
}
</style>
