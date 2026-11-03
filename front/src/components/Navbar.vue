<template>
  <!-- 桌面端导航栏 -->
  <el-menu
    v-if="!isMobile"
    :default-active="activeIndex"
    mode="horizontal"
    :ellipsis="false"
    class="navbar"
    :aria-label="t('mainNavigation')"
    @select="handleSelect"
  >
    <div class="logo" @click="router.push('/')">
      <img src="/res/xmmcglogo.png" alt="XMMCG Logo" height="32" />
    </div>

    <div class="flex-grow" />

    <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
      {{ item.label }}
    </el-menu-item>

    <div class="flex-grow" />

    <LanguageSwitcher />
    <div v-if="!currentUser" class="auth-buttons">
      <el-button type="primary" size="small" @click="router.push('/login')">{{
        t('logIn')
      }}</el-button>
      <el-button type="success" size="small" @click="router.push('/register')">{{
        t('register')
      }}</el-button>
    </div>

    <el-sub-menu v-else index="user" class="user-menu">
      <template #title>
        <el-icon><UserFilled /></el-icon>
        <span>{{ currentUser.username }}</span>
      </template>
      <el-menu-item index="/profile">
        <el-icon><User /></el-icon>{{ t('profile') }}</el-menu-item
      >
      <el-menu-item index="logout">
        <el-icon><SwitchButton /></el-icon>{{ t('logOut') }}</el-menu-item
      >
    </el-sub-menu>
  </el-menu>

  <!-- 移动端导航栏 -->
  <div v-else class="mobile-navbar">
    <div class="mobile-header">
      <div class="logo" @click="router.push('/')">
        <img src="/res/xmmcglogo.png" alt="XMMCG Logo" height="24" />
      </div>

      <div class="mobile-actions">
        <LanguageSwitcher />
        <template v-if="!currentUser">
          <el-button type="primary" size="small" @click="router.push('/login')">{{
            t('logIn')
          }}</el-button>
          <el-button type="success" size="small" @click="router.push('/register')">{{
            t('register')
          }}</el-button>
        </template>
        <el-button
          v-else
          circle
          size="small"
          :aria-label="t('userMenu')"
          @click="showMobileMenu = true"
        >
          <el-icon><UserFilled /></el-icon>
        </el-button>
        <el-button
          circle
          size="small"
          :aria-label="t('openMenu')"
          @click="mobileDrawerVisible = true"
        >
          <el-icon><Menu /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 移动端抽屉菜单 -->
    <el-drawer
      v-model="mobileDrawerVisible"
      direction="rtl"
      size="70%"
      :show-close="false"
      append-to-body
      class="custom-mobile-drawer"
    >
      <template #header>
        <div class="drawer-header">
          <el-icon :size="24"><Trophy /></el-icon>
          <span>{{ t('menu') }}</span>
        </div>
      </template>

      <el-menu :default-active="activeIndex" class="mobile-menu" @select="handleMobileSelect">
        <el-menu-item v-for="item in navItems" :key="item.path" :index="item.path">
          <el-icon><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
        </el-menu-item>

        <el-divider />

        <template v-if="currentUser">
          <el-menu-item index="/profile">
            <el-icon><User /></el-icon>
            <span>{{ t('profile') }}</span>
          </el-menu-item>
          <el-menu-item index="logout">
            <el-icon><SwitchButton /></el-icon>
            <span>{{ t('logOut') }}</span>
          </el-menu-item>
        </template>
        <template v-else>
          <el-menu-item index="/login">
            <el-icon><User /></el-icon>
            <span>{{ t('logIn') }}</span>
          </el-menu-item>
          <el-menu-item index="/register">
            <el-icon><UserFilled /></el-icon>
            <span>{{ t('register') }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-drawer>

    <!-- 移动端用户菜单（快捷弹窗） -->
    <el-dialog
      v-model="showMobileMenu"
      width="80%"
      :show-close="false"
      append-to-body
      class="custom-mobile-dialog"
    >
      <template #header>
        <div class="mobile-user-header">
          <el-icon><UserFilled /></el-icon>
          <span>{{ currentUser?.username }}</span>
        </div>
      </template>
      <div class="mobile-user-actions">
        <el-button type="primary" @click="handleMobileSelect('/profile')">
          <el-icon><User /></el-icon>{{ t('profile') }}</el-button
        >
        <el-button type="danger" @click="handleMobileSelect('logout')">
          <el-icon><SwitchButton /></el-icon>{{ t('logOut') }}</el-button
        >
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import LanguageSwitcher from './LanguageSwitcher.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  Trophy,
  UserFilled,
  User,
  SwitchButton,
  Menu,
  HomeFilled,
  Headset,
  Document,
  Star,
} from '@element-plus/icons-vue'
import { getCompetitionStatus } from '../api'
import { currentUser, loadSession, endSession } from '../state/session'

const router = useRouter()
const route = useRoute()
const songsEnabled = ref(false)
const isMobile = ref(false)
const mobileDrawerVisible = ref(false)
const showMobileMenu = ref(false)
let timer

const navItems = computed(() =>
  [
    { path: '/', label: t('home'), icon: HomeFilled },
    { path: '/charts', label: t('submitCharts'), icon: Document },
    songsEnabled.value && { path: '/songs', label: t('songDraw'), icon: Headset },
    { path: '/eval', label: t('review'), icon: Star },
  ].filter(Boolean),
)
const activeIndex = computed(() => route.path)

const checkMobile = () => {
  isMobile.value = window.innerWidth <= 768
}

const refresh = async () => {
  try {
    songsEnabled.value = (await getCompetitionStatus()).capabilities.songs_enabled
  } catch {
    songsEnabled.value = false
  }
}

const signOut = async () => {
  try {
    await endSession()
    ElMessage.success(t('loggedOut'))
    router.push('/')
  } catch (error) {
    ElMessage.error(error.message)
  }
}

const handleSelect = (key) => {
  if (key === 'user') return
  if (key === 'logout') {
    signOut()
    return
  }
  router.push(key)
}

const handleMobileSelect = (key) => {
  mobileDrawerVisible.value = false
  showMobileMenu.value = false
  handleSelect(key)
}

onMounted(async () => {
  checkMobile()
  window.addEventListener('resize', checkMobile)
  await loadSession().catch(() => {})
  await refresh()
  timer = setInterval(refresh, 30000)
})

onUnmounted(() => {
  clearInterval(timer)
  window.removeEventListener('resize', checkMobile)
})
</script>

<style scoped>
/* 桌面端导航栏 */
.navbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: var(--surface-strong);
  backdrop-filter: blur(var(--glass-blur));
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--shadow-elevated);
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  cursor: pointer;
}

.logo img {
  height: 32px;
  width: auto;
}

.flex-grow {
  flex-grow: 1;
}

.auth-buttons {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 20px;
}

.user-menu {
  margin-left: auto;
}

/* 移动端导航栏 */
.mobile-navbar {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: var(--surface-strong);
  backdrop-filter: blur(var(--glass-blur));
  border-bottom: 1px solid var(--border-color);
  box-shadow: var(--shadow-elevated);
}

.mobile-navbar .logo {
  padding: 0;
}

.mobile-navbar .logo img {
  height: 24px;
}

.mobile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  min-height: 60px;
}

.mobile-actions {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}

.mobile-actions .el-button--small {
  padding: 6px 12px;
  font-size: 13px;
  min-width: 48px;
}
</style>

<style>
/* 抽屉与弹窗被 append-to-body 移出 #app，这里不能用 scoped，使用专用类名避免污染全局 */
.custom-mobile-drawer {
  background: var(--surface-color) !important;
  backdrop-filter: blur(var(--glass-blur));
  color: var(--text-primary);
}

.custom-mobile-drawer .el-drawer__header {
  margin-bottom: 16px;
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-primary);
}

.custom-mobile-drawer .el-drawer__body {
  padding: 0 !important;
}

.custom-mobile-drawer .drawer-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: bold;
  color: var(--primary-color);
}

.custom-mobile-drawer .mobile-menu {
  border: none !important;
  background: transparent !important;
}

.custom-mobile-drawer .el-menu-item {
  height: 56px;
  line-height: 56px;
  font-size: 16px;
  padding: 0 20px;
  background: transparent;
  color: var(--text-primary);
}

.custom-mobile-drawer .el-menu-item .el-icon {
  margin-right: 12px;
  font-size: 18px;
}

.custom-mobile-drawer .el-menu-item:hover {
  background-color: rgba(122, 200, 255, 0.15);
  color: var(--primary-color);
}

.custom-mobile-drawer .el-menu-item.is-active {
  background-color: rgba(122, 200, 255, 0.2);
  color: var(--primary-color);
}

.custom-mobile-dialog {
  border-radius: 12px;
  max-width: 320px;
  color: var(--text-primary);
}

.custom-mobile-dialog .el-dialog__header {
  padding: 20px;
  border-bottom: 1px solid var(--border-color);
  margin-right: 0;
}

.custom-mobile-dialog .el-dialog__body {
  padding: 20px;
}

.custom-mobile-dialog .mobile-user-header {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 18px;
  font-weight: bold;
}

.custom-mobile-dialog .mobile-user-actions {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.custom-mobile-dialog .mobile-user-actions .el-button {
  height: 48px;
  font-size: 16px;
  margin-left: 0;
}
</style>
