<template>
  <DeviceLivePlayer
    :device="device"
    :compact="compact"
    :show-controls="showControls"
  />
</template>

<script setup lang="ts">
import DeviceLivePlayer from '@/components/monitor/DeviceLivePlayer.vue';
import type { DeviceSummary } from '@/types/device';

withDefaults(
  defineProps<{
    device: DeviceSummary;
    refreshMs?: number;
    compact?: boolean;
    showControls?: boolean;
  }>(),
  {
    refreshMs: 6000,
    compact: false,
    showControls: false,
  },
);
</script>
