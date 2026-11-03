<template>
  <div class="home">
    <el-container>
      <el-main>
        <!-- 轮换Banner -->
        <Banner />

        <!-- 比赛状态 -->
        <el-card class="status-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <el-icon>
                <TrophyBase />
              </el-icon>
              <span>{{ t('currentCompetitionStatus') }}</span>
            </div>
          </template>
          <el-row :gutter="20">
            <el-col :xs="24" :sm="12" :md="6">
              <div class="status-item">
                <div class="status-label">{{ t('competitionStatus') }}</div>
                <div class="status-value">
                  {{
                    competitionStatus.competition ? competitionStatus.currentRound : t('notStarted')
                  }}
                </div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="status-item">
                <div class="status-label">{{ t('status') }}</div>
                <el-tag :type="getStatusType(competitionStatus.status)">
                  {{
                    { active: t('inProgress'), upcoming: t('upcoming'), ended: t('ended') }[
                      competitionStatus.status
                    ] || t('toBeDetermined')
                  }}
                </el-tag>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="status-item">
                <div class="status-label">{{ t('participants') }}</div>
                <div class="status-value">{{ competitionStatus.participants || 0 }}</div>
              </div>
            </el-col>
            <el-col :xs="24" :sm="12" :md="6">
              <div class="status-item">
                <div class="status-label">
                  {{ t('submittedCharts') }}
                </div>
                <div class="status-value">{{ competitionStatus.submissions || 0 }}</div>
              </div>
            </el-col>
          </el-row>
        </el-card>

        <!-- 竞赛阶段日程 -->
        <PhaseTimeline />

        <!-- 公告栏 -->
        <Announcement />

        <!-- 快速入口 -->
        <el-row :gutter="20" class="quick-actions">
          <el-col v-if="competitionStatus.capabilities?.songs_enabled" :xs="24" :sm="12" :md="8">
            <el-card shadow="hover" class="action-card">
              <div class="action-content">
                <el-icon size="48" color="#409EFF">
                  <Headset />
                </el-icon>
                <h3>{{ t('songDraw') }}</h3>
                <p>{{ t('optionalSongUploadsAndRandomDraws') }}</p>
                <el-button type="primary" @click="$router.push('/songs')">{{
                  t('goToSongs')
                }}</el-button>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-card shadow="hover" class="action-card">
              <div class="action-content">
                <el-icon size="48" color="#67C23A">
                  <Document />
                </el-icon>
                <h3>{{ t('browseCharts') }}</h3>
                <p>{{ t('browseAllSubmittedCharts') }}</p>
                <el-button type="success" @click="$router.push('/charts')">{{
                  t('goToCharts')
                }}</el-button>
              </div>
            </el-card>
          </el-col>
          <el-col :xs="24" :sm="12" :md="8">
            <el-card shadow="hover" class="action-card">
              <div class="action-content">
                <el-icon size="48" color="#E6A23C">
                  <User />
                </el-icon>
                <h3>{{ t('profile') }}</h3>
                <p>{{ t('manageYourAccountAndCharts') }}</p>
                <el-button type="warning" @click="goToProfile">{{ t('goToProfile') }}</el-button>
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-main>
    </el-container>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { TrophyBase, Headset, Document, User } from '@element-plus/icons-vue'
import Banner from '../components/Banner.vue'
import Announcement from '../components/Announcement.vue'
import PhaseTimeline from '../components/PhaseTimeline.vue'
import { getCompetitionStatus } from '../api'
import { currentUser } from '../state/session'

const router = useRouter()

const competitionStatus = ref({
  currentRound: '',
  status: '',
  statusText: '',
  participants: 0,
  submissions: 0,
})

const getStatusType = (status) => {
  const typeMap = {
    upcoming: 'info',
    active: 'success',
    ended: 'warning',
  }
  return typeMap[status] || 'info'
}

const goToProfile = () => router.push(currentUser.value ? '/profile' : '/login')

const fetchCompetitionStatus = async () => {
  try {
    const data = await getCompetitionStatus()
    competitionStatus.value = data
  } catch (error) {
    console.error('获取比赛状态失败:', error)
  }
}

onMounted(() => {
  fetchCompetitionStatus()
})
</script>

<style scoped>
.home {
  max-width: 1200px;
  margin: 0 auto;
}

.status-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: bold;
}

.status-item {
  text-align: center;
  padding: 10px;
}

.status-label {
  font-size: 14px;
  color: #909399;
  margin-bottom: 8px;
}

.status-value {
  font-size: 24px;
  font-weight: bold;
  color: #303133;
}

.quick-actions {
  margin-top: 20px;
}

.action-card {
  margin-bottom: 20px;
  transition: transform 0.3s;
}

.action-card:hover {
  transform: translateY(-5px);
}

.action-content {
  text-align: center;
  padding: 20px;
}

.action-content h3 {
  margin: 15px 0 10px;
  color: #303133;
}

.action-content p {
  color: #909399;
  margin-bottom: 20px;
  font-size: 14px;
}
</style>
