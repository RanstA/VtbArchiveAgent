import { createRouter, createWebHistory } from 'vue-router'
import ArchiveView from '@/views/ArchiveView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', redirect: '/archive' },
    { path: '/archive', name: 'archive', component: ArchiveView },
    { path: '/streams/:streamId', name: 'timeline', component: () => import('@/views/TimelineView.vue') },
    { path: '/search', name: 'search', component: () => import('@/views/SearchView.vue') },
    { path: '/highlights', name: 'highlights', component: () => import('@/views/HighlightsView.vue') },
    { path: '/investigate', name: 'investigate', component: () => import('@/views/InvestigateView.vue') },
    { path: '/:pathMatch(.*)*', redirect: '/archive' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

export default router
