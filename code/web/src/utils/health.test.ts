import { describe, expect, it } from 'vitest';

import { summarizeDependencies } from './health';

describe('summarizeDependencies', () => {
  it('returns ready message when every dependency is up', () => {
    expect(
      summarizeDependencies([
        { name: 'postgres', status: 'up', detail: 'ok' },
        { name: 'redis', status: 'up', detail: 'ok' },
      ]),
    ).toBe('所有基础服务均已联通。');
  });

  it('lists down dependencies', () => {
    expect(
      summarizeDependencies([
        { name: 'postgres', status: 'up', detail: 'ok' },
        { name: 'redis', status: 'down', detail: 'timeout' },
      ]),
    ).toContain('redis');
  });
});
