import { createRouter, createWebHistory } from 'vue-router'
import { loadSession } from '../state/session'
import { watch } from 'vue'
import { i18n, t } from '../i18n'
import Home from '../views/Home.vue'
import Charts from '../views/Charts.vue'
import Songs from '../views/Songs.vue'
import Eval from '../views/Eval.vue'
import Login from '../views/Login.vue'
import Register from '../views/Register.vue'
import Profile from '../views/Profile.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Home, meta: { title: 'home' } },
    { path: '/charts', component: Charts, meta: { title: 'submitCharts' } },
    { path: '/songs', component: Songs, meta: { title: 'songDraw', requiresAuth: true } },
    { path: '/eval', component: Eval, meta: { title: 'review', requiresAuth: true } },
    { path: '/login', component: Login, meta: { title: 'logIn' } },
    { path: '/register', component: Register, meta: { title: 'register' } },
    { path: '/profile', component: Profile, meta: { title: 'profile', requiresAuth: true } },
  ],
})
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !(await loadSession()))
    return { path: '/login', query: { redirect: to.fullPath } }
})
const updateTitle = () => {
  document.title = `${t(router.currentRoute.value.meta.title || 'home')} - 小妹妹唱歌net`
}
router.afterEach(updateTitle)
watch(i18n.global.locale, updateTitle)
export default router
