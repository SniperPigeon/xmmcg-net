<template>
  <el-carousel :interval="5000" height="300px" class="banner-carousel">
    <el-carousel-item v-for="(item, index) in banners" :key="index">
      <div
        class="banner-item"
        :style="{
          backgroundColor: item.color,
          backgroundImage: item.image_url
            ? `linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5)), url(${item.image_url})`
            : 'none',
          backgroundSize: 'cover',
          backgroundPosition: 'center',
        }"
      >
        <div class="banner-content">
          <h2>{{ item.title }}</h2>
          <p>{{ item.content }}</p>
          <el-button v-if="item.link" type="primary" size="large" @click="handleClick(item.link)">
            {{ item.button_text || '了解更多' }}
          </el-button>
        </div>
      </div>
    </el-carousel-item>
  </el-carousel>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getBanners } from '../api'

const router = useRouter()

const banners = ref([])

const handleClick = (link) => {
  if (link) {
    // 检查是否是内部路由
    if (link.startsWith('/')) {
      router.push(link)
    } else {
      if (/^https?:\/\//i.test(link)) window.open(link, '_blank', 'noopener,noreferrer')
    }
  }
}

const fetchBanners = async () => {
  try {
    const data = await getBanners()
    if (data && data.length > 0) {
      banners.value = data
    }
  } catch (error) {
    console.error('获取 Banner 失败:', error)
  }
}

onMounted(() => {
  fetchBanners()
})
</script>

<style scoped>
.banner-carousel {
  margin-bottom: 20px;
  border-radius: 8px;
  overflow: hidden;
}

.banner-item {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
}

.banner-content {
  text-align: center;
  padding: 20px;
}

.banner-content h2 {
  font-size: 36px;
  margin: 0 0 15px 0;
  text-shadow: 2px 2px 4px rgba(0, 0, 0, 0.3);
}

.banner-content p {
  font-size: 18px;
  margin: 0 0 25px 0;
  text-shadow: 1px 1px 2px rgba(0, 0, 0, 0.3);
}

@media (max-width: 768px) {
  .banner-content h2 {
    font-size: 24px;
  }

  .banner-content p {
    font-size: 14px;
  }
}
</style>
