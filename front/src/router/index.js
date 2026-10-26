import { createRouter, createWebHistory } from 'vue-router'
import { loadSession } from '../state/session'
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
    { path: '/', component: Home, meta: { title: '首页' } },
    { path: '/charts', component: Charts, meta: { title: '谱面投稿' } },
    { path: '/songs', component: Songs, meta: { title: '歌曲抽选', requiresAuth: true } },
    { path: '/eval', component: Eval, meta: { title: '评分', requiresAuth: true } },
    { path: '/login', component: Login, meta: { title: '登录' } },
    { path: '/register', component: Register, meta: { title: '注册' } },
    { path: '/profile', component: Profile, meta: { title: '个人中心', requiresAuth: true } },
  ],
})
router.beforeEach(async (to) => {
  document.title = `${to.meta.title} -  小妹妹唱歌net`
  if (to.meta.requiresAuth && !(await loadSession()))
    return { path: '/login', query: { redirect: to.fullPath } }
})
export default router
