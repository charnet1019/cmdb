import { createApp } from 'vue'
import { createPinia } from 'pinia'
import Antd from 'ant-design-vue'
import App from './App.vue'
import router from './router'

// Import styles - Ant Design reset first, then Tailwind to ensure Tailwind takes precedence
import 'ant-design-vue/dist/reset.css'
import './assets/main.css'

const app = createApp(App)

app.use(createPinia())
app.use(router)
app.use(Antd)

app.mount('#app')