export const APP_NAME = import.meta.env.VITE_APP_TITLE || '牧巡智控平台';
export const APP_SUBTITLE = '牛只行为监测与运营管理系统';
export const APP_ACCESS_LABEL = '系统访问入口';
export const APP_OPERATION_LABEL = '智慧牧场运营中枢';
export const APP_DESCRIPTION = '统一管理设备接入、区域配置、实时监控与行为事件处置。';

export function buildDocumentTitle(pageTitle?: string) {
  return pageTitle ? `${pageTitle} - ${APP_NAME}` : APP_NAME;
}
