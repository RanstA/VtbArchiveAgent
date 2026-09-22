import {
  createRouter,
  createWebHistory,
  type RouteLocationRaw,
  type RouteRecordRaw,
} from 'vue-router'

import ArchiveView from '@/views/ArchiveView.vue'
import {
  appConfig,
  isMultiVtuberMode,
} from '@/config/app'
import {
  useVtuberStore,
} from '@/stores/vtuber'

const singleVtuberId = (
  isMultiVtuberMode
    ? undefined
    : appConfig.defaultVtuberId!
)

function rootDestination(): RouteLocationRaw {
  return isMultiVtuberMode
    ? {
        name: 'vtuber-select',
      }
    : {
        name: 'archive',
        params: {
          vtuberId: singleVtuberId!,
        },
      }
}

function legacyWorkspaceDestination(
  name: string,
  params: Record<string, string> = {},
): RouteLocationRaw {
  const vtuberStore = useVtuberStore()

  const vtuberId =
    vtuberStore.currentVtuberId
    ?? (
      isMultiVtuberMode
        ? undefined
        : singleVtuberId
    )

  return vtuberId
    ? {
        name,
        params: {
          vtuberId,
          ...params,
        },
      }
    : rootDestination()
}

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: rootDestination,
  },

  ...(
    isMultiVtuberMode
      ? [
          {
            path: '/vtubers',
            name: 'vtuber-select',
            component: () =>
              import(
                '@/views/VtuberSelectView.vue'
              ),
          },
        ]
      : []
  ),

  {
    path: '/v/:vtuberId',
    redirect: (to) => ({
      name: 'archive',
      params: {
        vtuberId:
          to.params.vtuberId,
      },
    }),
  },

  {
    path: '/v/:vtuberId/archive',
    name: 'archive',
    component: ArchiveView,
    meta: {
      workspace: true,
    },
  },

  {
    path: '/v/:vtuberId/streams/:streamId',
    name: 'timeline',
    component: () =>
      import(
        '@/views/TimelineView.vue'
      ),
    meta: {
      workspace: true,
    },
  },

  {
    path: '/v/:vtuberId/search',
    name: 'search',
    component: () =>
      import(
        '@/views/SearchView.vue'
      ),
    meta: {
      workspace: true,
    },
  },

  {
    path: '/v/:vtuberId/highlights',
    name: 'highlights',
    component: () =>
      import(
        '@/views/HighlightsView.vue'
      ),
    meta: {
      workspace: true,
    },
  },

  {
    path: '/v/:vtuberId/investigate',
    name: 'investigate',
    component: () =>
      import(
        '@/views/InvestigateView.vue'
      ),
    meta: {
      workspace: true,
    },
  },

  /**
   * Phase 1 之前的旧链接兼容。
   *
   * 最终都会进入：
   *
   * /v/:vtuberId/...
   */
  {
    path: '/archive',
    redirect: () =>
      legacyWorkspaceDestination(
        'archive',
      ),
  },

  {
    path: '/search',
    redirect: () =>
      legacyWorkspaceDestination(
        'search',
      ),
  },

  {
    path: '/highlights',
    redirect: () =>
      legacyWorkspaceDestination(
        'highlights',
      ),
  },

  {
    path: '/investigate',
    redirect: () =>
      legacyWorkspaceDestination(
        'investigate',
      ),
  },

  {
    path: '/streams/:streamId',
    redirect: (to) =>
      legacyWorkspaceDestination(
        'timeline',
        {
          streamId: String(
            to.params.streamId,
          ),
        },
      ),
  },

  {
    path: '/:pathMatch(.*)*',
    redirect: rootDestination,
  },
]

const router = createRouter({
  history: createWebHistory(
    import.meta.env.BASE_URL,
  ),

  routes,

  scrollBehavior: () => ({
    top: 0,
  }),
})

router.beforeEach(
  async (to) => {
    const vtuberStore =
      useVtuberStore()

    /**
     * Selector 不属于任何 VTuber workspace。
     */
    if (!to.meta.workspace) {
      if (
        to.name
        === 'vtuber-select'
      ) {
        vtuberStore
          .clearCurrentVtuber()
      }

      return true
    }

    const routeVtuberId = String(
      to.params.vtuberId ?? '',
    )

    /**
     * Single 模式只能进入配置指定的 VTuber。
     *
     * 不允许通过 URL 切换到其他 workspace。
     */
    if (
      !isMultiVtuberMode
      && routeVtuberId
        !== singleVtuberId
    ) {
      return {
        name: 'archive',
        params: {
          vtuberId:
            singleVtuberId!,
        },
      }
    }

    /**
     * 在判断 vtuberId 是否有效之前，
     * 必须先拿到真实 backend catalog。
     *
     * 这使 direct refresh：
     *
     * /v/aza/archive
     *
     * 也可以正确工作。
     */
    const catalogLoaded =
      await vtuberStore
        .ensureLoaded()

    if (!catalogLoaded) {
      vtuberStore
        .clearCurrentVtuber()

      /**
       * Multi 模式可以回到 selector，
       * selector 会显示 catalog error。
       */
      if (isMultiVtuberMode) {
        return {
          name: 'vtuber-select',
        }
      }

      /**
       * Single 模式没有 selector，
       * 不能偷偷 fallback 到别的 VTuber。
       *
       * 配置或 backend catalog 出问题时
       * 明确失败。
       */
      throw new Error(
        '[VTuber catalog] '
        + 'Unable to load runtime VTuber catalog. '
        + (
          vtuberStore.error
          || 'Unknown catalog error.'
        ),
      )
    }

    /**
     * Single 模式的 default VTuber
     * 必须真实存在于 backend catalog。
     */
    if (
      !isMultiVtuberMode
      && !vtuberStore.hasVtuber(
        singleVtuberId!,
      )
    ) {
      throw new Error(
        '[VTuber config] '
        + 'VITE_DEFAULT_VTUBER_ID '
        + `"${singleVtuberId}" `
        + 'does not exist in the runtime '
        + 'VTuber catalog.',
      )
    }

    /**
     * Multi 模式下不存在的 VTuber ID
     * 回到 VTuber Selector。
     */
    if (
      !vtuberStore.setCurrentVtuber(
        routeVtuberId,
      )
    ) {
      return isMultiVtuberMode
        ? {
            name:
              'vtuber-select',
          }
        : {
            name: 'archive',
            params: {
              vtuberId:
                singleVtuberId!,
            },
          }
    }

    return true
  },
)

export default router