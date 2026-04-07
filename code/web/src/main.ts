import { createApp } from 'vue';

import { pinia } from '@/app/pinia';

import App from './App.vue';
import { router } from './app/router';
import './styles/main.css';

const app = createApp(App);

app.use(pinia);
app.use(router);
app.mount('#app');
