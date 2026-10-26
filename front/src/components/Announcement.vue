<template>
  <el-card class="announcement-card" shadow="hover">
    <template #header>
      <div class="card-header">
        <el-icon><BellFilled /></el-icon>
        <span>最新公告</span>
      </div>
    </template>

    <el-timeline>
      <el-timeline-item
        v-for="(announcement, index) in announcements"
        :key="index"
        :timestamp="formatTime(announcement.created_at)"
        :type="getCategoryType(announcement.category)"
        placement="top"
      >
        <el-card :body-style="{ padding: '15px' }">
          <div class="announcement-header">
            <h4>{{ announcement.title }}</h4>
            <el-tag v-if="announcement.is_pinned" type="danger" size="small">置顶</el-tag>
            <el-tag :type="getCategoryTagType(announcement.category)" size="small">
              {{ getCategoryLabel(announcement.category) }}
            </el-tag>
          </div>
          <div class="announcement-content" v-html="parseMarkdown(announcement.content)"></div>
        </el-card>
      </el-timeline-item>
    </el-timeline>

    <el-empty v-if="announcements.length === 0" description="暂无公告" />
  </el-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { BellFilled } from '@element-plus/icons-vue'
import { getAnnouncementsFromAPI } from '../api'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const announcements = ref([])

const getCategoryType = (category) => {
  const typeMap = {
    news: 'primary',
    event: 'success',
    notice: 'warning',
  }
  return typeMap[category] || 'primary'
}

const getCategoryTagType = (category) => {
  const typeMap = {
    news: 'info',
    event: 'success',
    notice: 'warning',
  }
  return typeMap[category] || 'info'
}

const getCategoryLabel = (category) => {
  const labelMap = {
    news: '新闻',
    event: '活动',
    notice: '通知',
  }
  return labelMap[category] || category
}

const formatTime = (dateString) => {
  if (!dateString) return ''
  try {
    const date = new Date(dateString)
    return date.toLocaleDateString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return dateString
  }
}

const parseMarkdown = (markdown) => {
  if (!markdown) return ''
  try {
    return DOMPurify.sanitize(marked(markdown))
  } catch {
    return markdown
  }
}

const fetchAnnouncements = async () => {
  try {
    const data = await getAnnouncementsFromAPI(10)
    if (data && data.length > 0) {
      announcements.value = data
    }
  } catch (error) {
    console.error('获取公告失败:', error)
  }
}

onMounted(() => {
  fetchAnnouncements()
})
</script>

<style scoped>
.announcement-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 18px;
  font-weight: bold;
}

.announcement-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.announcement-header h4 {
  margin: 0;
  flex: 1;
  color: #303133;
  font-size: 16px;
}

.announcement-content {
  color: #606266;
  line-height: 1.6;
  font-size: 14px;
}

.announcement-content :deep(p) {
  margin: 8px 0;
}

.announcement-content :deep(ul),
.announcement-content :deep(ol) {
  margin: 8px 0;
  padding-left: 20px;
}

.announcement-content :deep(li) {
  margin: 4px 0;
}

.announcement-content :deep(strong) {
  color: #303133;
  font-weight: bold;
}

.announcement-content :deep(em) {
  font-style: italic;
}

.announcement-content :deep(code) {
  background-color: #f5f7fa;
  padding: 2px 6px;
  border-radius: 3px;
  font-family: monospace;
  font-size: 13px;
}

.announcement-content :deep(blockquote) {
  border-left: 4px solid #409eff;
  padding-left: 12px;
  margin: 8px 0;
  color: #606266;
}

.announcement-content :deep(a) {
  color: #409eff;
  text-decoration: none;
}

.announcement-content :deep(a:hover) {
  text-decoration: underline;
}
</style>
