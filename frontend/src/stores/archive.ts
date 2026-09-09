import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getStreams, type StreamListParams } from '@/api/streams'

export const useArchiveStore = defineStore('archive', () => {
  const streams = ref<Awaited<ReturnType<typeof getStreams>>>([])
  const loading = ref(false)
  const error = ref('')
  const query = ref('')
  const status = ref<NonNullable<StreamListParams['status']>>('all')

  const resultCount = computed(() => streams.value.length)

  async function load() {
    loading.value = true
    error.value = ''
    try {
      streams.value = await getStreams({ query: query.value, status: status.value })
    } catch (reason) {
      error.value = reason instanceof Error ? reason.message : '无法读取直播档案'
    } finally {
      loading.value = false
    }
  }

  return { streams, loading, error, query, status, resultCount, load }
})
