function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function trimLeadingSlash(value: string) {
  return value.replace(/^\/+/, '');
}

function joinUrl(base: string, path: string) {
  const normalizedBase = trimTrailingSlash(base);
  const normalizedPath = trimLeadingSlash(path);
  return normalizedPath ? `${normalizedBase}/${normalizedPath}` : normalizedBase;
}

function readEnvValue(value: string | undefined) {
  if (!value) {
    return null;
  }

  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

const browserOrigin = typeof window === 'undefined' ? '' : window.location.origin;

const configuredApiBaseUrl = readEnvValue(import.meta.env.VITE_API_BASE_URL);
const configuredMediaHlsBaseUrl = readEnvValue(import.meta.env.VITE_MEDIA_MTX_HLS_BASE_URL);

export const apiBaseUrl = configuredApiBaseUrl ?? browserOrigin;
export const apiDocsUrl = configuredApiBaseUrl ? joinUrl(configuredApiBaseUrl, 'docs') : joinUrl(browserOrigin, 'docs');
export const mediaHlsBaseUrl = configuredMediaHlsBaseUrl ?? joinUrl(browserOrigin, 'hls');
