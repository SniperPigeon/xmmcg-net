<template>
  <div class="register-page">
    <el-card class="register-card">
      <template #header>
        <div class="title-header">
          <h2>{{ t('userRegistration') }}</h2>
        </div>
      </template>
      <el-form
        ref="formRef"
        :model="form"
        :rules="rules"
        label-width="96px"
        :disabled="busy"
        @submit.prevent="submit"
      >
        <el-form-item :label="t('username')" prop="username">
          <el-input
            v-model="form.username"
            :placeholder="t('enterYourUsername')"
            :prefix-icon="User"
            autocomplete="username"
            maxlength="20"
          />
        </el-form-item>
        <el-form-item label-width="0" class="bind-switch">
          <el-checkbox v-model="bindMain">{{ t('thisIsMyAlternateAccountLinkItTo') }}</el-checkbox>
        </el-form-item>
        <template v-if="bindMain">
          <el-form-item :label="t('chooseMainAccount')" prop="main_account_id">
            <el-select
              v-model="form.main_account_id"
              filterable
              remote
              :remote-method="search"
              :loading="searching"
              :placeholder="t('enterAtLeastTwoCharactersToSearchUsernames')"
              style="width: 100%"
              ><el-option
                v-for="account in accounts"
                :key="account.id"
                :label="account.username"
                :value="account.id"
            /></el-select>
          </el-form-item>
          <el-form-item :label="t('mainAccountPassword')" prop="main_password">
            <el-input
              v-model="form.main_password"
              type="password"
              show-password
              :placeholder="t('verifyMainAccountPassword')"
              :prefix-icon="Lock"
              autocomplete="off"
            />
          </el-form-item>
          <p class="bind-hint">{{ t('contactDetailsAreInheritedFromTheMainAccount') }}</p>
        </template>
        <template v-else>
          <el-form-item :label="t('qqNumber')" prop="qqid">
            <el-input
              v-model="form.qqid"
              :placeholder="t('enterYourPrimaryQqNumber')"
              :prefix-icon="ChatDotRound"
              inputmode="numeric"
            />
          </el-form-item>
          <el-form-item :label="t('email')" prop="email">
            <el-input
              v-model="form.email"
              type="email"
              :placeholder="t('enterYourEmail')"
              :prefix-icon="Message"
              autocomplete="email"
            />
          </el-form-item>
        </template>
        <el-form-item :label="t('password')" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="t('enterAPasswordForTheNewAccount')"
            :prefix-icon="Lock"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item :label="t('confirmPassword')" prop="password_confirm">
          <el-input
            v-model="form.password_confirm"
            type="password"
            show-password
            :placeholder="t('enterYourPasswordAgain')"
            :prefix-icon="Lock"
            autocomplete="new-password"
          />
        </el-form-item>
        <el-form-item>
          <el-button native-type="submit" type="primary" :loading="busy" style="width: 100%">{{
            t('register')
          }}</el-button>
        </el-form-item>
        <el-form-item>
          <div class="register-footer">
            <span>{{ t('alreadyHaveAnAccount') }}</span>
            <el-link type="primary" @click="$router.push('/login')">{{ t('logInNow') }}</el-link>
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
const rules = computed(() => ({
  username: [
    required(t('enterYourUsername')),
    { min: 3, max: 20, message: t('usernameMustBeCharacters'), trigger: 'blur' },
  ],
  main_account_id: [{ required: true, message: t('pleaseChooseAMainAccount'), trigger: 'change' }],
  main_password: [required(t('enterYourMainAccountPassword'))],
  qqid: [
    required(t('enterYourQqNumber')),
    { pattern: /^[1-9][0-9]{4,14}$/, message: t('invalidQqNumber'), trigger: 'blur' },
  ],
  email: [
    required(t('enterYourEmail')),
    { type: 'email', message: t('invalidEmailAddress'), trigger: 'blur' },
  ],
  password: [required(t('enterYourPassword'))],
  password_confirm: [required(t('enterYourPasswordAgain'))],
}))
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
    ElMessage.error(t('passwordsDoNotMatch'))
    return
  }
  if (bindMain.value && !form.main_account_id) {
    ElMessage.error(t('pleaseChooseAMainAccount'))
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
    ElMessage.success(t('registrationSuccessfulPleaseLogIn'))
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
