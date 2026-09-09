<script setup lang="ts">
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useMockApi } from '@/api/client'
import ArchiveFilters from '@/components/archive/ArchiveFilters.vue'
import StreamTable from '@/components/archive/StreamTable.vue'
import { useArchiveStore } from '@/stores/archive'

const archive = useArchiveStore()
const { streams, loading, error, query, status, resultCount } = storeToRefs(archive)

onMounted(() => archive.load())
</script>

<template>
  <main class="page archive-page">
    <header class="page-header">
      <div>
        <span class="eyebrow">ARCHIVE INDEX</span>
        <h1>直播档案</h1>
      </div>
      <div class="header-metric">
        <span>DATA SOURCE</span>
        <strong>{{ useMockApi ? 'LOCAL / MOCK' : 'FASTAPI' }}</strong>
      </div>
    </header>

    <section class="content-panel">
      <ArchiveFilters
        v-model:query="query"
        v-model:status="status"
        :count="resultCount"
        :loading="loading"
        @search="archive.load"
      />
      <p v-if="error" class="error-banner">{{ error }}</p>
      <StreamTable :streams="streams" :loading="loading" />
    </section>
  </main>
</template>
