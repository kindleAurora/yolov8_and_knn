import { createRouter, createWebHistory } from 'vue-router';

import { pinia } from '@/app/pinia';
import { buildDocumentTitle } from '@/config/branding';
import AppLayout from '@/layouts/AppLayout.vue';
import LoginView from '@/modules/auth/views/LoginView.vue';
import AlertCenterView from '@/modules/alerts/views/AlertCenterView.vue';
import AlertDetailView from '@/modules/alerts/views/AlertDetailView.vue';
import DashboardView from '@/modules/dashboard/views/DashboardView.vue';
import DeviceManagementView from '@/modules/devices/views/DeviceManagementView.vue';
import BehaviorEventWorkbenchView from '@/modules/events/views/BehaviorEventWorkbenchView.vue';
import HistoryAnalysisView from '@/modules/history/views/HistoryAnalysisView.vue';
import DeviceMonitorDetailView from '@/modules/monitor/views/DeviceMonitorDetailView.vue';
import MonitorWallView from '@/modules/monitor/views/MonitorWallView.vue';
import RuleManagementView from '@/modules/rules/views/RuleManagementView.vue';
import ZoneManagementView from '@/modules/zones/views/ZoneManagementView.vue';
import { useAuthStore } from '@/stores/auth';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: {
        guestOnly: true,
        title: '登录',
      },
    },
    {
      path: '/',
      component: AppLayout,
      meta: {
        requiresAuth: true,
      },
      children: [
        {
          path: '',
          name: 'dashboard',
          component: DashboardView,
          meta: {
            title: '系统总览',
          },
        },
        {
          path: 'devices',
          name: 'devices',
          component: DeviceManagementView,
          meta: {
            title: '设备管理',
          },
        },
        {
          path: 'zones',
          name: 'zones',
          component: ZoneManagementView,
          meta: {
            title: '区域配置',
          },
        },
        {
          path: 'events',
          name: 'events',
          component: BehaviorEventWorkbenchView,
          meta: {
            title: '事件中心',
          },
        },
        {
          path: 'alerts',
          name: 'alerts',
          component: AlertCenterView,
          meta: {
            title: '告警中心',
          },
        },
        {
          path: 'alerts/:alertId',
          name: 'alert-detail',
          component: AlertDetailView,
          meta: {
            title: '告警详情',
          },
        },
        {
          path: 'rules',
          name: 'rules',
          component: RuleManagementView,
          meta: {
            title: '规则配置',
          },
        },
        {
          path: 'history',
          name: 'history',
          component: HistoryAnalysisView,
          meta: {
            title: '历史分析',
          },
        },
        {
          path: 'monitor',
          name: 'monitor',
          component: MonitorWallView,
          meta: {
            title: '监控中心',
          },
        },
        {
          path: 'monitor/:deviceId',
          name: 'monitor-detail',
          component: DeviceMonitorDetailView,
          meta: {
            title: '监控详情',
          },
        },
      ],
    },
  ],
});

router.beforeEach(async (to) => {
  const authStore = useAuthStore(pinia);
  await authStore.initialize();

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return {
      name: 'login',
      query: {
        redirect: to.fullPath,
      },
    };
  }

  if (to.meta.guestOnly && authStore.isAuthenticated) {
    return { name: 'dashboard' };
  }

  return true;
});

router.afterEach((to) => {
  document.title = buildDocumentTitle(typeof to.meta.title === 'string' ? to.meta.title : undefined);
});
