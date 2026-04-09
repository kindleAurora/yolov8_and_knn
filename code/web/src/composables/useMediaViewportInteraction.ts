import { computed, onBeforeUnmount, watch, type CSSProperties, type Ref } from 'vue';

export type MediaFitMode = 'contain' | 'cover';

interface MediaSize {
  width: number;
  height: number;
}

interface UseMediaViewportInteractionOptions {
  fitMode: Ref<MediaFitMode>;
  zoom: Ref<number>;
  stageRef: Ref<HTMLElement | null>;
  intrinsicSize: Ref<MediaSize>;
  offsetX: Ref<number>;
  offsetY: Ref<number>;
  isDragging: Ref<boolean>;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

export function useMediaViewportInteraction({
  fitMode,
  zoom,
  stageRef,
  intrinsicSize,
  offsetX,
  offsetY,
  isDragging,
}: UseMediaViewportInteractionOptions) {
  let activePointerId: number | null = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragOriginX = 0;
  let dragOriginY = 0;
  let resizeObserver: ResizeObserver | null = null;

  const maxOffsets = computed(() => {
    const stage = stageRef.value;
    const { width: mediaWidth, height: mediaHeight } = intrinsicSize.value;

    if (!stage || mediaWidth <= 0 || mediaHeight <= 0) {
      return { x: 0, y: 0 };
    }

    const stageWidth = stage.clientWidth;
    const stageHeight = stage.clientHeight;
    if (stageWidth <= 0 || stageHeight <= 0) {
      return { x: 0, y: 0 };
    }

    const baseScale =
      fitMode.value === 'cover'
        ? Math.max(stageWidth / mediaWidth, stageHeight / mediaHeight)
        : Math.min(stageWidth / mediaWidth, stageHeight / mediaHeight);

    const renderedWidth = mediaWidth * baseScale * zoom.value;
    const renderedHeight = mediaHeight * baseScale * zoom.value;

    return {
      x: Math.max((renderedWidth - stageWidth) / 2, 0),
      y: Math.max((renderedHeight - stageHeight) / 2, 0),
    };
  });

  const canPan = computed(() => maxOffsets.value.x > 0.5 || maxOffsets.value.y > 0.5);
  const stageInteractionStyle = computed<CSSProperties>(() => ({
    cursor: canPan.value ? (isDragging.value ? 'grabbing' : 'grab') : 'default',
    touchAction: canPan.value ? 'none' : 'auto',
  }));
  const panStyle = computed<CSSProperties>(() => ({
    transform: `translate3d(${offsetX.value}px, ${offsetY.value}px, 0)`,
  }));
  const mediaStyle = computed<CSSProperties>(() => ({
    objectFit: fitMode.value,
    transform: `scale(${zoom.value})`,
  }));

  function resetViewport() {
    offsetX.value = 0;
    offsetY.value = 0;
  }

  function clampOffsets() {
    const { x, y } = maxOffsets.value;
    offsetX.value = clamp(offsetX.value, -x, x);
    offsetY.value = clamp(offsetY.value, -y, y);
  }

  function stopDragging() {
    isDragging.value = false;
    activePointerId = null;
  }

  function startDrag(event: PointerEvent) {
    if (!canPan.value) {
      return;
    }

    const stage = event.currentTarget as HTMLElement | null;
    activePointerId = event.pointerId;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
    dragOriginX = offsetX.value;
    dragOriginY = offsetY.value;
    isDragging.value = true;

    stage?.setPointerCapture?.(event.pointerId);
  }

  function updateDrag(event: PointerEvent) {
    if (!isDragging.value || activePointerId !== event.pointerId) {
      return;
    }

    const { x, y } = maxOffsets.value;
    offsetX.value = clamp(dragOriginX + event.clientX - dragStartX, -x, x);
    offsetY.value = clamp(dragOriginY + event.clientY - dragStartY, -y, y);
  }

  function endDrag(event?: PointerEvent) {
    if (event && activePointerId !== null && event.pointerId !== activePointerId) {
      return;
    }

    const stage = event?.currentTarget as HTMLElement | null;
    if (event && stage?.hasPointerCapture?.(event.pointerId)) {
      stage.releasePointerCapture(event.pointerId);
    }

    stopDragging();
  }

  watch([fitMode, zoom, intrinsicSize], () => {
    if (!canPan.value) {
      resetViewport();
      return;
    }

    clampOffsets();
  });

  watch(
    stageRef,
    (stage) => {
      resizeObserver?.disconnect();
      resizeObserver = null;

      if (!stage) {
        return;
      }

      resizeObserver = new ResizeObserver(() => {
        if (!canPan.value) {
          resetViewport();
          return;
        }

        clampOffsets();
      });
      resizeObserver.observe(stage);
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
    resizeObserver?.disconnect();
    stopDragging();
  });

  return {
    canPan,
    endDrag,
    mediaStyle,
    panStyle,
    resetViewport,
    stageInteractionStyle,
    startDrag,
    updateDrag,
  };
}
