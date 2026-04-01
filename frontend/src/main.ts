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

// Helper to hide loading indicator
function hideLoadingIndicator() {
  const loading = document.getElementById('app-loading')
  if (loading) {
    loading.style.opacity = '0'
    loading.style.transition = 'opacity 0.2s'
    setTimeout(() => {
      loading.classList.add('hidden')
    }, 200)
  }
}

// Wait for fonts to load before mounting app to prevent icon text flash
if (document.fonts && document.fonts.ready) {
  document.fonts.ready.then(() => {
    app.mount('#app')
    // Hide loading indicator after Vue app is mounted
    hideLoadingIndicator()
  })
} else {
  // Fallback for browsers without fonts API
  app.mount('#app')
  hideLoadingIndicator()
}