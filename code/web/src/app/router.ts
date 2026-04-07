import { createRouter, createWebHistory } from 'vue-router';

import { pinia } from '@/app/pinia';
import AppLayout from '@/layouts/AppLayout.vue';
import LoginView from '@/modules/auth/views/LoginView.vue';
import DashboardView from '@/modules/dashboard/views/DashboardView.vue';
import DeviceManagementView from '@/modules/devices/views/DeviceManagementView.vue';
import BehaviorEventWorkbenchView from '@/modules/events/views/BehaviorEventWorkbenchView.vue';
import MonitorWallView from '@/modules/monitor/views/MonitorWallView.vue';
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
        },
        {
          path: 'devices',
          name: 'devices',
          component: DeviceManagementView,
        },
        {
          path: 'zones',
          name: 'zones',
          component: ZoneManagementView,
        },
        {
          path: 'events',
          name: 'events',
          component: BehaviorEventWorkbenchView,
        },
        {
          path: 'monitor',
          name: 'monitor',
          component: MonitorWallView,
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
