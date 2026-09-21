import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { getVtubers, type Vtuber } from '@/api/vtubers'

export type { Vtuber } from '@/api/vtubers'

/**
 * Phase 2B-1 过渡用。
 *
 * 当前 router/index.ts 和 vite.config.ts
 * 仍然依赖这个静态 catalog 做配置校验。
 *
 * 真正展示给用户的 VTuber 列表已经不再使用它，
 * 而是由 GET /vtubers 加载。
 *
 * Phase 2B-2 改造 Router 后会彻底删除。
 */
export const TEMPORARY_MOCK_VTUBERS: readonly Vtuber[] = [
  {
    id: 'mikoto',
    displayName: '蜜言',
  },
  {
    id: 'aza',
    displayName: '阿萨Aza',
  },
]

export const useVtuberStore = defineStore(
  'vtuber',
  () => {
    /**
     * 真正的运行时 catalog。
     *
     * 不再用 TEMPORARY_MOCK_VTUBERS 初始化，
     * 页面必须通过 GET /vtubers 获取。
     */
    const vtubers = ref<Vtuber[]>([])

    const loaded = ref(false)
    const loading = ref(false)
    const error = ref('')

    const currentVtuberId = ref<string>()

    const currentVtuber = computed(() =>
      vtubers.value.find(
        (vtuber) =>
          vtuber.id === currentVtuberId.value,
      ),
    )

    async function loadVtubers() {
      if (loaded.value) {
        return
      }

      loading.value = true
      error.value = ''

      try {
        vtubers.value = await getVtubers()
        loaded.value = true
      } catch (reason) {
        vtubers.value = []
        loaded.value = false

        error.value =
          reason instanceof Error
            ? reason.message
            : '无法加载 VTuber 列表'
      } finally {
        loading.value = false
      }
    }

    function hasVtuber(
      vtuberId: string,
    ) {
      return vtubers.value.some(
        (vtuber) =>
          vtuber.id === vtuberId,
      )
    }

    function setCurrentVtuber(
      vtuberId: string,
    ) {
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

      loaded,
      loading,
      error,

      currentVtuber,
      currentVtuberId,

      loadVtubers,
      hasVtuber,
      setCurrentVtuber,
      clearCurrentVtuber,
    }
  },
)