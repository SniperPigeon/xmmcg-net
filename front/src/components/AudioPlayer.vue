<template>
  <!-- Vidstack 按扩展名把 .ogg 识别为视频，固定为音频视图以始终显示音频控件 -->
  <media-player
    class="audio-player"
    :title="title"
    :src="src"
    view-type="audio"
    load="play"
    preload="none"
  >
    <media-provider></media-provider>
    <media-audio-layout color-scheme="dark"></media-audio-layout>
  </media-player>
</template>

<script setup>
// Vidstack 默认音频布局所需的样式与元素；仅在使用播放器的页面加载。
import 'vidstack/player/styles/default/theme.css'
import 'vidstack/player/styles/default/layouts/audio.css'
import 'vidstack/player'
import 'vidstack/player/layouts/default'
import 'vidstack/player/ui'

defineProps({
  src: { type: String, required: true },
  title: { type: String, default: '' },
})
</script>

<style scoped>
.audio-player {
  width: 100%;
  --audio-bg: rgba(15, 23, 42, 0.6);
  --audio-border: 1px solid var(--border-color);
  --audio-border-radius: 8px;
  /* 沿用原有的深色播放按钮 */
  --audio-play-button-bg: #33363c;
}
</style>
