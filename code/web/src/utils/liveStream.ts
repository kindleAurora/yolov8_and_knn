import type { DeviceSummary } from '@/types/device';
import { mediaHlsBaseUrl } from '@/config/runtime';

type LiveStreamDevice = Pick<DeviceSummary, 'stream_url' | 'config'>;

interface ResolveDeviceBrowserStreamOptions {
  hlsBaseUrl?: string;
}

const LIVE_URL_CONFIG_KEYS = ['browser_stream_url', 'hls_url', 'live_url'] as const;

function readConfigString(config: Record<string, unknown>, key: string): string | null {
  const value = config[key];
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function normalizeBaseUrl(url: string): string {
  return url.replace(/\/+$/, '');
}

export function resolveDeviceBrowserStreamUrl(
  device: LiveStreamDevice,
  options: ResolveDeviceBrowserStreamOptions = {},
): string | null {
  const config = device.config ?? {};

  for (const key of LIVE_URL_CONFIG_KEYS) {
    const configuredUrl = readConfigString(config, key);
    if (configuredUrl) {
      return configuredUrl;
    }
  }

  const streamUrl = device.stream_url.trim();
  if (!streamUrl) {
    return null;
  }

  if (/^https?:\/\/.+\.m3u8(?:$|[?#])/i.test(streamUrl)) {
    return streamUrl;
  }

  const hlsBaseUrl = normalizeBaseUrl(
    options.hlsBaseUrl ?? mediaHlsBaseUrl,
  );
  if (!hlsBaseUrl) {
    return null;
  }

  let parsedUrl: URL;
  try {
    parsedUrl = new URL(streamUrl);
  } catch {
    return null;
  }

  if (!['rtsp:', 'rtsps:', 'rtmp:', 'rtmps:'].includes(parsedUrl.protocol)) {
    return null;
  }

  const streamPath = parsedUrl.pathname.replace(/^\/+/, '').replace(/\/+$/, '');
  if (!streamPath) {
    return null;
  }

  return `${hlsBaseUrl}/${streamPath}/index.m3u8`;
}
