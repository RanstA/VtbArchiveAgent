import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export type Theme = 'light' | 'dark'

function resolveInitialTheme(): Theme {
  try {
    const saved = window.localStorage.getItem('vtuber-archive-theme')
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    // Storage can be unavailable in privacy-restricted browser contexts.
  }
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

export const useThemeStore = defineStore('theme', () => {
  const theme = ref<Theme>(resolveInitialTheme())
  const isDark = computed(() => theme.value === 'dark')

  function applyTheme(value: Theme) {
    theme.value = value
    document.documentElement.dataset.theme = value
    document.documentElement.style.colorScheme = value
    try {
      window.localStorage.setItem('vtuber-archive-theme', value)
    } catch {
      // The active theme still applies for the current session.
    }
  }

  function toggleTheme() {
    applyTheme(isDark.value ? 'light' : 'dark')
  }

  applyTheme(theme.value)

  return { theme, isDark, applyTheme, toggleTheme }
})
