import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import {
  getVtubers,
  type Vtuber,
} from '@/api/vtubers'

export type { Vtuber } from '@/api/vtubers'

export const useVtuberStore = defineStore(
  'vtuber',
  () => {
    const vtubers = ref<Vtuber[]>([])

    const loaded = ref(false)
    const loading = ref(false)
    const error = ref('')

    const currentVtuberId = ref<string>()

    /**
     * 同一时间只允许一个 catalog 请求。
     *
     * Router guard 和页面可能同时请求 VTuber catalog，
     * 共用这个 Promise，避免重复 GET /vtubers。
     */
    let loadPromise: Promise<boolean> | null = null

    const currentVtuber = computed(() =>
      vtubers.value.find(
        (vtuber) =>
          vtuber.id === currentVtuberId.value,
      ),
    )

    function performLoad(): Promise<boolean> {
      loading.value = true
      error.value = ''

      const request = getVtubers()
        .then((result) => {
          vtubers.value = result

          /**
           * 空数组也是一次成功响应。
           *
           * loaded 表示：
           * “已经成功读取过 catalog”
           * 而不是：
           * “catalog 至少有一个 VTuber”。
           */
          loaded.value = true

          return true
        })
        .catch((reason) => {
          vtubers.value = []
          loaded.value = false

          error.value =
            reason instanceof Error
              ? reason.message
              : '无法加载 VTuber 列表'

          return false
        })
        .finally(() => {
          loading.value = false
          loadPromise = null
        })

      loadPromise = request

      return request
    }

    function loadVtubers(): Promise<boolean> {
      if (loaded.value) {
        return Promise.resolve(true)
      }

      if (loadPromise) {
        return loadPromise
      }

      return performLoad()
    }

    function reloadVtubers(): Promise<boolean> {
      if (loadPromise) {
        return loadPromise
      }

      loaded.value = false

      return performLoad()
    }

    function ensureLoaded(): Promise<boolean> {
      if (loaded.value) {
        return Promise.resolve(true)
      }

      return loadVtubers()
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
      reloadVtubers,
      ensureLoaded,

      hasVtuber,
      setCurrentVtuber,
      clearCurrentVtuber,
    }
  },
)