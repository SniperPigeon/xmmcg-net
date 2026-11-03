import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'
import App from './App.vue'
import { i18n } from './i18n'
import router from './router'
import './styles/main.css'

const app = createApp(App)
document.documentElement.classList.add('dark')

app.use(i18n)
app.use(ElementPlus)
app.use(router)
app.mount('#app')
