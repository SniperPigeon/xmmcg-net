import axios from 'axios'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 240000,
  withCredentials: true,
})
let csrfToken = ''
export async function ensureCsrfToken() {
  const response = await api.get('/users/csrf/')
  csrfToken = response.csrfToken
}
api.interceptors.request.use(async (config) => {
  if (!['get', 'head', 'options'].includes(config.method)) {
    // Login rotates the CSRF token; always fetch a current token before writes.
    await ensureCsrfToken()
    config.headers['X-CSRFToken'] = csrfToken
  }
  return config
})
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const data = error.response?.data
    error.message =
      typeof data === 'string'
        ? data
        : data?.detail ||
          data?.message ||
          (data &&
            Object.entries(data)
              .map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join('；') : value}`)
              .join('；')) ||
          '请求失败，请稍后重试'
    return Promise.reject(error)
  },
)
// The response interceptor unwraps CSRF responses too.
export const login = (username, password) => api.post('/users/login/', { username, password })
export const logout = () => api.post('/users/logout/')
export const register = (data) => api.post('/users/register/', data)
export const searchAccounts = (q) => api.get('/users/accounts/', { params: { q } })
export const getUserProfile = () => api.get('/users/me/')
export const updateUserProfile = async (data) => (await api.patch('/users/profile/', data)).user
export const getCompetitionStatus = () => api.get('/contest/status/')
export const getCompetitionPhases = () => api.get('/contest/phases/')
export const getBanners = () => api.get('/contest/banners/')
export const getAnnouncementsFromAPI = () => api.get('/contest/announcements/')
export const getCharts = (params) => api.get('/charts/', { params })
export const getMyCharts = (params) => api.get('/charts/me/', { params })
export const submitChart = (data) => api.post('/charts/', data)
export const retryChartSync = (id) => api.post(`/charts/${id}/sync/`)
export const getSongs = () => api.get('/songs/')
export const uploadSong = (data) => api.post('/songs/', data)
export const joinDraw = () => api.post('/songs/draw/join/')
export const getMyDraws = () => api.get('/songs/draw/me/')
export const getMyReviewTasks = () => api.get('/reviews/tasks/')
export const getReviewableCharts = () => api.get('/reviews/available/')
export const submitReviews = (reviews) => api.post('/reviews/submit/', { reviews })
export const downloadBundle = async (id) => {
  const blob = await api.get(`/charts/${id}/bundle/`, { responseType: 'blob' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `chart-${id}.zip`
  anchor.click()
  URL.revokeObjectURL(url)
}
