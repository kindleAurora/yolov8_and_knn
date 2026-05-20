import type { ServiceDependency } from '@/types/health';

export function summarizeDependencies(dependencies: ServiceDependency[]): string {
  const downDependencies = dependencies.filter((item) => item.status === 'down');

  if (downDependencies.length === 0) {
    return '所有基础服务均已联通。';
  }

  return `待恢复服务：${downDependencies.map((item) => item.name).join('、')}`;
}
