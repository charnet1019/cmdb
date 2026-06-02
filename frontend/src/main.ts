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
    loading.style.transition = 'opacity 0.2s';
    setTimeout(() => {
      loading.classList.add('hidden')
    }, 200)
  }

  // Show the app element now that Vue is mounted
  const appEl = document.getElementById('app');
  if (appEl) {
    appEl.style.display = 'block';
  }
}

// Show the app element once fonts are loaded or timeout occurs
function waitForFontsOrTimeout() {
  // Use document.fonts.ready for reliable font loading detection
  const fontReady = document.fonts ? document.fonts.ready : Promise.resolve();
  const timeout = new Promise(resolve => setTimeout(resolve, 1000));

  Promise.race([fontReady, timeout])
    .then(mountAndHideLoading)
    .catch(mountAndHideLoading); // fallback if fonts API rejects
}

function mountAndHideLoading() {
  app.mount('#app')
  hideLoadingIndicator();
}

// Initialize the app with font loading considerations
function initApp() {
  // Ensure the app element is visible initially
  const appEl = document.getElementById('app');
  if (appEl) {
    appEl.style.display = 'block';
    appEl.style.visibility = 'visible';
  }

  // Wait for fonts or mount immediately
  waitForFontsOrTimeout();
}

if (document.readyState === 'loading') {
  // DOM not yet ready, wait for it
  document.addEventListener('DOMContentLoaded', initApp);
} else {
  // DOM already ready (e.g., on page refresh), mount immediately
  initApp();
}