import type { ApiEnvelope } from '@/types/api';
import { getStoredToken } from '@/utils/session';

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL;

type ApiRequestOptions = NonNullable<Parameters<typeof fetch>[1]> & {
  auth?: boolean;
};

function delay(ms: number) {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function formatValidationLocation(location: unknown) {
  if (!Array.isArray(location)) {
    return '';
  }

  const parts = location
    .filter((item): item is string | number => typeof item === 'string' || typeof item === 'number')
    .map(String)
    .filter((item) => item !== 'body');

  return parts.join('.');
}

function extractErrorMessage(responseBody: unknown, statusCode: number) {
  let message = `请求失败，状态码 ${statusCode}`;

  if (!isRecord(responseBody)) {
    return message;
  }

  if (typeof responseBody.detail === 'string') {
    return responseBody.detail;
  }

  if (Array.isArray(responseBody.detail)) {
    const issues = responseBody.detail
      .map((issue) => {
        if (!isRecord(issue) || typeof issue.msg !== 'string') {
          return null;
        }

        const location = formatValidationLocation(issue.loc);
        return location ? `${location}：${issue.msg}` : issue.msg;
      })
      .filter((issue): issue is string => Boolean(issue));

    if (issues.length > 0) {
      return `数据校验失败：${issues.join('；')}`;
    }
  }

  if (typeof responseBody.message === 'string') {
    return responseBody.message;
  }

  return message;
}

async function performApiFetch(path: string, options: ApiRequestOptions = {}): Promise<Response> {
  const { auth = true, headers, body, ...rest } = options;
  const requestHeaders = new Headers(headers);

  if (!(body instanceof FormData) && body !== undefined && !requestHeaders.has('Content-Type')) {
    requestHeaders.set('Content-Type', 'application/json');
  }

  if (auth) {
    const token = getStoredToken();
    if (token) {
      requestHeaders.set('Authorization', `Bearer ${token}`);
    }
  }

  const request = () =>
    fetch(`${apiBaseUrl}${path}`, {
      ...rest,
      headers: requestHeaders,
      body,
    });

  const method = (rest.method ?? 'GET').toUpperCase();
  const allowRetry = method === 'GET';

  let response: Response;
  try {
    response = await request();
  } catch {
    if (allowRetry) {
      await delay(800);
      try {
        response = await request();
      } catch {
        throw new Error('无法连接到平台服务，服务可能正在重启，请稍后刷新重试。');
      }
    } else {
      throw new Error('无法连接到平台服务，请检查网络或确认后端服务已经启动。');
    }
  }

  return response;
}

export async function apiRequest<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
  const response = await performApiFetch(path, options);

  const contentType = response.headers.get('content-type') ?? '';
  const responseBody = contentType.includes('application/json') ? ((await response.json()) as unknown) : null;

  if (!response.ok) {
    throw new Error(extractErrorMessage(responseBody, response.status));
  }

  if (!isRecord(responseBody)) {
    return undefined as T;
  }

  return (responseBody as unknown as ApiEnvelope<T>).data;
}

export async function apiBlob(path: string, options: ApiRequestOptions = {}): Promise<Blob> {
  const response = await performApiFetch(path, options);

  if (!response.ok) {
    const contentType = response.headers.get('content-type') ?? '';
    let responseBody: unknown = null;

    if (contentType.includes('application/json')) {
      responseBody = (await response.json()) as unknown;
    }

    throw new Error(extractErrorMessage(responseBody, response.status));
  }

  return response.blob();
}
