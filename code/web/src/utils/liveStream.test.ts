import { describe, expect, it } from 'vitest';

import { resolveDeviceBrowserStreamUrl } from './liveStream';

describe('resolveDeviceBrowserStreamUrl', () => {
  it('returns explicit browser playback URL from device config first', () => {
    expect(
      resolveDeviceBrowserStreamUrl(
        {
          stream_url: 'rtsp://localhost:8554/cow-monitor/demo',
          config: {
            browser_stream_url: 'http://localhost:8888/custom/index.m3u8',
          },
        },
        {
          hlsBaseUrl: 'http://localhost:8888',
        },
      ),
    ).toBe('http://localhost:8888/custom/index.m3u8');
  });

  it('derives an HLS URL from the RTSP path published by MediaMTX', () => {
    expect(
      resolveDeviceBrowserStreamUrl(
        {
          stream_url: 'rtsp://localhost:8554/cow-monitor/demo',
          config: {},
        },
        {
          hlsBaseUrl: 'http://localhost:8888/',
        },
      ),
    ).toBe('http://localhost:8888/cow-monitor/demo/index.m3u8');
  });

  it('returns the original URL when the device already stores an HLS manifest', () => {
    expect(
      resolveDeviceBrowserStreamUrl(
        {
          stream_url: 'http://localhost:8888/cow-monitor/demo/index.m3u8',
          config: {},
        },
        {
          hlsBaseUrl: 'http://localhost:9999',
        },
      ),
    ).toBe('http://localhost:8888/cow-monitor/demo/index.m3u8');
  });

  it('returns null when it cannot derive a browser-playable stream URL', () => {
    expect(
      resolveDeviceBrowserStreamUrl(
        {
          stream_url: 'http://localhost:8000/static/demo.mp4',
          config: {},
        },
        {
          hlsBaseUrl: 'http://localhost:8888',
        },
      ),
    ).toBeNull();
  });
});
