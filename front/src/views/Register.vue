<template>
  <el-card class="register-card">
    <template #header><h2>用户注册</h2></template>
    <form @submit.prevent="submit">
      <label
        >用户名<el-input
          v-model="form.username"
          required
          autocomplete="username"
          minlength="3"
          maxlength="20"
      /></label>
      <el-checkbox v-model="bindMain">这是我的小号，绑定已有大号</el-checkbox>
      <template v-if="bindMain">
        <label
          >选择大号<el-select
            v-model="form.main_account_id"
            filterable
            remote
            :remote-method="search"
            :loading="searching"
            placeholder="输入至少两个字符搜索用户名"
            ><el-option
              v-for="account in accounts"
              :key="account.id"
              :label="account.username"
              :value="account.id" /></el-select
        ></label>
        <label
          >验证大号密码<el-input
            v-model="form.main_password"
            required
            type="password"
            show-password
            autocomplete="off"
        /></label>
        <p>联系方式使用大号的资料。一个大号可绑定多个小号。</p>
      </template>
      <template v-else>
        <label
          >QQ 号<el-input
            v-model="form.qqid"
            required
            inputmode="numeric"
            pattern="[1-9][0-9]{4,14}"
        /></label>
        <label
          >邮箱<el-input v-model="form.email" required type="email" autocomplete="email"
        /></label>
      </template>
      <label
        >新账号密码<el-input
          v-model="form.password"
          required
          type="password"
          show-password
          autocomplete="new-password"
      /></label>
      <label
        >确认新密码<el-input
          v-model="form.password_confirm"
          required
          type="password"
          show-password
          autocomplete="new-password"
      /></label>
      <el-button native-type="submit" type="primary" :loading="busy">注册</el-button>
      <router-link to="/login">已有账号，前往登录</router-link>
    </form>
  </el-card>
</template>
<script setup>
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { register, searchAccounts } from '../api'
const router = useRouter(),
  busy = ref(false),
  bindMain = ref(false),
  searching = ref(false),
  accounts = ref([])
const form = reactive({
  username: '',
  qqid: '',
  email: '',
  password: '',
  password_confirm: '',
  main_account_id: null,
  main_password: '',
})
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
.register-card {
  max-width: 520px;
  margin: auto;
}
form {
  display: grid;
  gap: 18px;
}
label {
  display: grid;
  gap: 8px;
}
p {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}
</style>
