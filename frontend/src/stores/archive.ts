import {
  computed,
  ref,
} from 'vue'

import {
  defineStore,
} from 'pinia'

import {
  getStreams,
  type StreamListParams,
} from '@/api/streams'

export const useArchiveStore =
  defineStore(
    'archive',
    () => {
      const streams = ref<
        Awaited<
          ReturnType<
            typeof getStreams
          >
        >
      >([])

      const loading =
        ref(false)

      const error =
        ref('')

      const query =
        ref('')

      const status =
        ref<
          NonNullable<
            StreamListParams[
              'status'
            ]
          >
        >('all')

      /**
       * 防止切换 workspace 时：
       *
       * aza 请求较慢
       * → 切到 mikoto
       * → mikoto 请求先完成
       * → aza 旧请求最后回来
       * → 覆盖当前页面
       *
       * 每次 load 都获得一个递增 token。
       * 只有最新请求允许修改状态。
       */
      let loadSequence = 0

      const resultCount =
        computed(
          () =>
            streams.value.length,
        )

      async function load(
        vtuberId: string,
      ) {
        const normalizedVtuberId =
          vtuberId.trim()

        if (!normalizedVtuberId) {
          streams.value = []
          error.value =
            'VTuber ID 不能为空'

          return
        }

        const requestId =
          ++loadSequence

        loading.value = true
        error.value = ''

        /**
         * workspace 切换时立即清空旧主播数据，
         * 避免新请求期间短暂显示其他 VTuber
         * 的 Stream。
         */
        streams.value = []

        try {
          const result =
            await getStreams({
              vtuberId:
                normalizedVtuberId,

              query:
                query.value,

              status:
                status.value,
            })

          if (
            requestId
            !== loadSequence
          ) {
            return
          }

          /**
           * backend 已经负责 vtuber_id scope，
           * 前端再做一次 contract 检查。
           *
           * 如果后端未来意外返回跨 workspace
           * 数据，宁可明确报错，
           * 不要静默展示错误主播的数据。
           */
          const invalidStream =
            result.find(
              (stream) =>
                stream.vtuberId
                !== normalizedVtuberId,
            )

          if (invalidStream) {
            throw new Error(
              'Archive scope mismatch: '
              + `requested "${normalizedVtuberId}", `
              + `received stream "${invalidStream.id}" `
              + `owned by "${invalidStream.vtuberId}".`,
            )
          }

          streams.value = result
        } catch (reason) {
          if (
            requestId
            !== loadSequence
          ) {
            return
          }

          streams.value = []

          error.value =
            reason instanceof Error
              ? reason.message
              : '无法读取直播档案'
        } finally {
          if (
            requestId
            === loadSequence
          ) {
            loading.value = false
          }
        }
      }

      return {
        streams,
        loading,
        error,

        query,
        status,

        resultCount,

        load,
      }
    },
  )