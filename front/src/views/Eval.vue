<template>
  <div class="eval-page page-container">
    <el-card shadow="hover" class="header-card">
      <template #header>
        <div class="card-header">
          <el-icon><EditPen /></el-icon>
          <span>评分任务</span>
          <div class="header-actions">
            <el-tag type="info" effect="plain">满分 {{ config.max_score }}</el-tag>
            <el-tag type="danger" effect="plain">
              真爱票 {{ favoriteTotal }} / {{ config.max_favorites }}
            </el-tag>
            <el-button
              v-if="canReview && isOpen && !loading"
              type="primary"
              :icon="Plus"
              @click="showExtra"
              >添加额外谱面</el-button
            >
          </div>
        </div>
      </template>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <el-skeleton v-if="loading" :rows="2" animated />
      <template v-else>
        <el-alert
          v-if="!canReview"
          title="提交谱面后可参与评分"
          type="info"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="!isOpen"
          title="评分尚未开放或已截止，已提交评分仍可查看"
          type="warning"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else
          :title="`待提交 ${pending.length} 份，提交后不能修改`"
          type="success"
          :closable="false"
          show-icon
        />
      </template>
    </el-card>
    <template v-if="!loading">
      <el-empty v-if="!tasks.length" description="暂无评分任务" />
      <el-card v-for="(task, index) in tasks" :key="task.chart_id" class="task" shadow="hover">
        <div class="heading">
          <div class="task-title">
            <el-icon><Document /></el-icon>
            <strong>{{ task.title }}</strong>
            <span class="designer">{{ task.designer }}</span>
          </div>
          <el-tag :type="task.completed ? 'success' : task.allocation_id ? 'primary' : 'warning'">{{
            task.completed ? '已提交' : task.allocation_id ? '分配任务' : '额外评分'
          }}</el-tag>
        </div>
        <div class="score-row">
          <el-input-number
            v-model="task.score"
            :min="0"
            :max="Number(config.max_score)"
            :precision="2"
            :step="0.25"
            :disabled="task.completed || !isOpen"
            aria-label="评分"
          />
          <el-checkbox
            v-model="task.favorite"
            :disabled="
              task.completed || !isOpen || (!task.favorite && favoriteTotal >= config.max_favorites)
            "
            >真爱票</el-checkbox
          >
          <el-button
            v-if="!task.completed && !task.allocation_id"
            type="danger"
            link
            @click="tasks.splice(index, 1)"
            >移除</el-button
          >
          <el-button link type="primary" :icon="Download" @click="download(task.chart_id)"
            >下载谱面</el-button
          >
        </div>
        <el-input
          v-model="task.comment"
          type="textarea"
          :rows="2"
          maxlength="20000"
          placeholder="评语（可选）"
          :disabled="task.completed || !isOpen"
        />
      </el-card>
      <div v-if="canReview && isOpen && pending.length" class="submit-bar">
        <el-button type="primary" size="large" :icon="Check" :loading="submitting" @click="submit"
          >提交评分（{{ pending.length }}）</el-button
        >
      </div>
    </template>
    <el-dialog v-model="extraVisible" title="添加额外谱面" width="min(90vw, 600px)">
      <el-select v-model="selected" filterable placeholder="选择谱面" style="width: 100%"
        ><el-option
          v-for="chart in available"
          :key="chart.id"
          :value="chart.id"
          :label="`${chart.title} · ${chart.designer}`"
      /></el-select>
      <template #footer
        ><el-button @click="extraVisible = false">取消</el-button
        ><el-button type="primary" @click="addExtra">添加</el-button></template
      >
    </el-dialog>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { EditPen, Plus, Document, Download, Check } from '@element-plus/icons-vue'
import { getMyReviewTasks, getReviewableCharts, submitReviews, downloadBundle } from '../api'
const tasks = ref([]),
  loading = ref(true),
  submitting = ref(false),
  error = ref(''),
  config = ref({ max_score: 50, max_favorites: 3 })
const canReview = ref(false),
  isOpen = ref(false),
  extraVisible = ref(false),
  selected = ref(null),
  available = ref([])
const pending = computed(() => tasks.value.filter((task) => !task.completed))
const favoriteTotal = computed(() => tasks.value.filter((task) => task.favorite).length)
const load = async () => {
  loading.value = true
  try {
    const result = await getMyReviewTasks()
    tasks.value = result.tasks.map((task) => ({
      ...task,
      score: task.score === null ? undefined : Number(task.score),
    }))
    config.value = result.config
    canReview.value = result.can_review
    isOpen.value = result.is_open
    error.value = ''
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
const showExtra = async () => {
  try {
    const selectedIds = new Set(tasks.value.map((task) => task.chart_id))
    available.value = (await getReviewableCharts()).filter((chart) => !selectedIds.has(chart.id))
    selected.value = null
    extraVisible.value = true
  } catch (err) {
    ElMessage.error(err.message)
  }
}
const addExtra = () => {
  const chart = available.value.find((chart) => chart.id === selected.value)
  if (!chart) return
  tasks.value.push({
    chart_id: chart.id,
    title: chart.title,
    designer: chart.designer,
    completed: false,
    allocation_id: null,
    score: undefined,
    comment: '',
    favorite: false,
  })
  extraVisible.value = false
}
const submit = async () => {
  if (pending.value.some((task) => task.score === undefined || task.score === null)) {
    ElMessage.warning('请填写全部待提交任务的分数')
    return
  }
  try {
    await ElMessageBox.confirm(`提交 ${pending.value.length} 份评分？提交后不能修改。`, '确认提交')
    submitting.value = true
    await submitReviews(
      pending.value.map(({ chart_id, score, comment, favorite }) => ({
        chart_id,
        score,
        comment,
        favorite,
      })),
    )
    ElMessage.success('评分已保存')
    await load()
  } catch (err) {
    if (err !== 'cancel' && err !== 'close') ElMessage.error(err.message)
  } finally {
    submitting.value = false
  }
}
const download = async (id) => {
  try {
    await downloadBundle(id)
  } catch (err) {
    ElMessage.error(err.message)
  }
}
onMounted(load)
</script>
<style scoped>
.eval-page {
  max-width: 1000px;
}
.task {
  margin: 16px 0;
}
.heading,
.score-row {
  display: flex;
  gap: 16px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.heading {
  justify-content: space-between;
}
.task-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  min-width: 0;
}
.task-title .designer {
  font-size: 14px;
  color: var(--text-secondary);
}
.submit-bar {
  display: flex;
  justify-content: center;
  margin: 20px 0;
}
</style>
