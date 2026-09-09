<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineChart, ScatterChart, type LineSeriesOption, type ScatterSeriesOption } from 'echarts/charts'
import { GridComponent, TooltipComponent, type GridComponentOption, type TooltipComponentOption } from 'echarts/components'
import { graphic, init, use, type ComposeOption, type ECharts } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import type { Event } from '@/types'
import { formatTimestamp } from '@/utils/time'

use([LineChart, ScatterChart, GridComponent, TooltipComponent, CanvasRenderer])

type TimelineChartOption = ComposeOption<
  LineSeriesOption | ScatterSeriesOption | GridComponentOption | TooltipComponentOption
>

const props = defineProps<{
  events: Event[]
  durationMs: number
  activeEventId?: string
}>()

const emit = defineEmits<{ select: [eventId: string] }>()

const chartElement = ref<HTMLDivElement>()
let chart: ECharts | undefined
let resizeObserver: ResizeObserver | undefined
let themeObserver: MutationObserver | undefined

function readChartColors() {
  const styles = getComputedStyle(document.documentElement)
  return {
    background: styles.getPropertyValue('--surface-raised').trim(),
    border: styles.getPropertyValue('--line-strong').trim(),
    grid: styles.getPropertyValue('--line').trim(),
    text: styles.getPropertyValue('--text').trim(),
    faint: styles.getPropertyValue('--faint').trim(),
    accent: styles.getPropertyValue('--accent').trim(),
    amber: styles.getPropertyValue('--amber').trim(),
    page: styles.getPropertyValue('--bg').trim(),
    areaStart: styles.getPropertyValue('--chart-area-start').trim(),
    areaEnd: styles.getPropertyValue('--chart-area-end').trim(),
  }
}

function createDensitySeries() {
  const steps = 72
  return Array.from({ length: steps + 1 }, (_, index) => {
    const timestamp = (props.durationMs / steps) * index
    const eventBoost = props.events.reduce((boost, event) => {
      const center = (event.startMs + event.endMs) / 2
      const distance = Math.abs(timestamp - center)
      return boost + Math.max(0, 52 - (distance / Math.max(props.durationMs, 1)) * 900)
    }, 0)
    const baseline = 15 + Math.sin(index * 0.75) * 5 + Math.cos(index * 0.23) * 4
    return [Math.round(timestamp), Math.min(100, Math.max(4, Math.round(baseline + eventBoost)))]
  })
}

function renderChart() {
  if (!chart) return
  const colors = readChartColors()
  const eventPoints = props.events.map((event) => ({
    value: [event.startMs, 86],
    eventId: event.id,
    itemStyle: {
      color: event.id === props.activeEventId ? colors.amber : colors.accent,
      borderColor: colors.page,
      borderWidth: 2,
    },
  }))

  const option: TimelineChartOption = {
    animation: false,
    grid: { top: 26, right: 18, bottom: 38, left: 42 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: colors.background,
      borderColor: colors.border,
      textStyle: { color: colors.text, fontSize: 12 },
      formatter: (params: unknown) => {
        const entries = params as Array<{ value: [number, number] }>
        const first = entries[0]
        return first ? `${formatTimestamp(first.value[0])}<br/>弹幕相对强度 ${first.value[1]}` : ''
      },
    },
    xAxis: {
      type: 'value',
      min: 0,
      max: props.durationMs,
      axisLabel: { color: colors.faint, formatter: (value: number) => formatTimestamp(value), fontSize: 11 },
      axisLine: { lineStyle: { color: colors.border } },
      axisTick: { show: false },
      splitLine: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { color: colors.faint, fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: colors.grid, opacity: .55 } },
    },
    series: [
      {
        name: '弹幕相对强度',
        type: 'line',
        data: createDensitySeries(),
        symbol: 'none',
        smooth: 0.28,
        lineStyle: { width: 1.5, color: colors.accent },
        areaStyle: {
          color: new graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colors.areaStart },
            { offset: 1, color: colors.areaEnd },
          ]),
        },
      },
      {
        name: 'Events',
        type: 'scatter',
        data: eventPoints,
        symbol: 'diamond',
        symbolSize: 13,
        z: 4,
      },
    ],
  }
  chart.setOption(option, true)
}

onMounted(() => {
  if (!chartElement.value) return
  chart = init(chartElement.value, undefined, { renderer: 'canvas' })
  chart.on('click', (params) => {
    const data = params.data as { eventId?: string } | undefined
    if (data?.eventId) emit('select', data.eventId)
  })
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartElement.value)
  themeObserver = new MutationObserver(renderChart)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  renderChart()
})

watch(() => [props.events, props.durationMs, props.activeEventId], renderChart, { deep: true })

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  themeObserver?.disconnect()
  chart?.dispose()
})
</script>

<template>
  <div ref="chartElement" class="timeline-chart" role="img" aria-label="直播弹幕相对强度与事件位置时间轴"></div>
</template>
