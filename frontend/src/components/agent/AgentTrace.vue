<script setup lang="ts">
import { computed } from 'vue'
import type { AgentTraceStep } from '@/types'

const props = defineProps<{ steps: AgentTraceStep[]; running: boolean }>()

const traceState = computed(() => {
  if (props.running) return 'RUNNING'
  return props.steps.every((step) => step.status === 'pending') ? 'IDLE' : 'COMPLETE'
})
</script>

<template>
  <section class="trace-panel" aria-live="polite">
    <header class="section-heading compact">
      <div><span class="section-index">01</span><h2>Agent Trace</h2></div>
      <span class="trace-state"><i :class="{ running }"></i>{{ traceState }}</span>
    </header>
    <ol class="trace-list">
      <li v-for="(step, index) in steps" :key="step.id" :class="step.status">
        <span class="trace-node"><i></i></span>
        <span class="trace-number mono">{{ String(index + 1).padStart(2, '0') }}</span>
        <span class="trace-copy"><strong>{{ step.label }}</strong><small>{{ step.detail }}</small></span>
        <span class="trace-label mono">{{ step.status === 'done' ? 'DONE' : step.status === 'active' ? 'ACTIVE' : 'WAIT' }}</span>
      </li>
    </ol>
  </section>
</template>
