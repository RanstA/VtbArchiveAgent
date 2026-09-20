import { createRouter, createWebHistory, type RouteLocationRaw, type RouteRecordRaw } from 'vue-router'
import ArchiveView from '@/views/ArchiveView.vue'
import { appConfig, isMultiVtuberMode } from '@/config/app'
import { TEMPORARY_MOCK_VTUBERS, useVtuberStore } from '@/stores/vtuber'

function resolveSingleVtuberId() {
  if (isMultiVtuberMode) return undefined

  const defaultVtuberId = appConfig.defaultVtuberId!
  if (!TEMPORARY_MOCK_VTUBERS.some((vtuber) => vtuber.id === defaultVtuberId)) {
    throw new Error(
      `[VTuber config] Unknown VITE_DEFAULT_VTUBER_ID "${defaultVtuberId}" in the temporary frontend VTuber catalog.`,
    )
  }

  return defaultVtuberId
}

const singleVtuberId = resolveSingleVtuberId()

function rootDestination(): RouteLocationRaw {
  return isMultiVtuberMode
    ? { name: 'vtuber-select' }
    : { name: 'archive', params: { vtuberId: singleVtuberId! } }
}

function legacyWorkspaceDestination(name: string, params: Record<string, string> = {}): RouteLocationRaw {
  const vtuberStore = useVtuberStore()
  const vtuberId = vtuberStore.currentVtuberId ?? (isMultiVtuberMode ? undefined : singleVtuberId)

  return vtuberId ? { name, params: { vtuberId, ...params } } : rootDestination()
}

const routes: RouteRecordRaw[] = [
  { path: '/', redirect: rootDestination },
  ...(isMultiVtuberMode
    ? [{ path: '/vtubers', name: 'vtuber-select', component: () => import('@/views/VtuberSelectView.vue') }]
    : []),
  {
    path: '/v/:vtuberId',
    redirect: (to) => ({ name: 'archive', params: { vtuberId: to.params.vtuberId } }),
  },
  { path: '/v/:vtuberId/archive', name: 'archive', component: ArchiveView, meta: { workspace: true } },
  {
    path: '/v/:vtuberId/streams/:streamId',
    name: 'timeline',
    component: () => import('@/views/TimelineView.vue'),
    meta: { workspace: true },
  },
  {
    path: '/v/:vtuberId/search',
    name: 'search',
    component: () => import('@/views/SearchView.vue'),
    meta: { workspace: true },
  },
  {
    path: '/v/:vtuberId/highlights',
    name: 'highlights',
    component: () => import('@/views/HighlightsView.vue'),
    meta: { workspace: true },
  },
  {
    path: '/v/:vtuberId/investigate',
    name: 'investigate',
    component: () => import('@/views/InvestigateView.vue'),
    meta: { workspace: true },
  },

  // Temporary compatibility redirects for links/bookmarks created before the
  // workspace routes were introduced. They always resolve into /v/:vtuberId/… .
  { path: '/archive', redirect: () => legacyWorkspaceDestination('archive') },
  { path: '/search', redirect: () => legacyWorkspaceDestination('search') },
  { path: '/highlights', redirect: () => legacyWorkspaceDestination('highlights') },
  { path: '/investigate', redirect: () => legacyWorkspaceDestination('investigate') },
  {
    path: '/streams/:streamId',
    redirect: (to) => legacyWorkspaceDestination('timeline', { streamId: String(to.params.streamId) }),
  },
  { path: '/:pathMatch(.*)*', redirect: rootDestination },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const vtuberStore = useVtuberStore()

  if (!to.meta.workspace) {
    if (to.name === 'vtuber-select') vtuberStore.clearCurrentVtuber()
    return true
  }

  const routeVtuberId = String(to.params.vtuberId ?? '')

  if (!isMultiVtuberMode && routeVtuberId !== singleVtuberId) {
    return { name: 'archive', params: { vtuberId: singleVtuberId! } }
  }

  if (!vtuberStore.setCurrentVtuber(routeVtuberId)) {
    return rootDestination()
  }

  return true
})

export default router
