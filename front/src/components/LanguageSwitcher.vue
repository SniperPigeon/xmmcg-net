<template>
  <select v-model="locale" class="language-switcher" :aria-label="t('language')">
    <option v-for="item in supportedLocales" :key="item.value" :value="item.value">
      {{ item.label }}
    </option>
  </select>
</template>

<script setup>
import { useI18n } from 'vue-i18n'
import { supportedLocales } from '../i18n'
const { locale, t } = useI18n()
</script>

<style scoped>
.language-switcher {
  align-self: center;
  max-width: 110px;
  margin: 0 8px;
  padding: 6px;
  color: var(--text-primary);
  background: var(--surface-color);
  border: 1px solid var(--border-color);
  border-radius: 6px;
}
</style>
