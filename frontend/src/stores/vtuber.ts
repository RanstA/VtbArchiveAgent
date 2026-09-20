import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export interface Vtuber {
  id: string
  displayName: string
}

// Temporary frontend mock for Phase 1. Replace with GET /vtubers once the
// frontend starts consuming the backend VTuber catalog.
export const TEMPORARY_MOCK_VTUBERS: readonly Vtuber[] = [
  { id: 'mikoto', displayName: '蜜言' },
  { id: 'aza', displayName: '阿萨Aza' },
]

export const useVtuberStore = defineStore('vtuber', () => {
  const vtubers = ref<Vtuber[]>([...TEMPORARY_MOCK_VTUBERS])
  const currentVtuberId = ref<string>()
  const currentVtuber = computed(() =>
    vtubers.value.find((vtuber) => vtuber.id === currentVtuberId.value),
  )

  function hasVtuber(vtuberId: string) {
    return vtubers.value.some((vtuber) => vtuber.id === vtuberId)
  }

  function setCurrentVtuber(vtuberId: string) {
    if (!hasVtuber(vtuberId)) {
      currentVtuberId.value = undefined
      return false
    }

    currentVtuberId.value = vtuberId
    return true
  }

  function clearCurrentVtuber() {
    currentVtuberId.value = undefined
  }

  return {
    vtubers,
    currentVtuber,
    currentVtuberId,
    hasVtuber,
    setCurrentVtuber,
    clearCurrentVtuber,
  }
})
