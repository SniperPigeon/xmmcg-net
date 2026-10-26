import { ref } from 'vue'
import { getUserProfile, logout as logoutRequest } from '../api'

export const currentUser = ref(null)
let request
export const loadSession = async (refresh = false) => {
  if (!request || refresh)
    request = getUserProfile()
      .then((user) => (currentUser.value = user))
      .catch((error) => {
        if (![401, 403].includes(error.response?.status)) {
          request = null
          throw error
        }
        currentUser.value = null
        return null
      })
  return request
}
export const endSession = async () => {
  await logoutRequest()
  currentUser.value = null
  request = null
  localStorage.removeItem('token')
  localStorage.removeItem('username')
}
