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
  // Check if fonts are already loaded
  const isFontLoaded = document.fonts ? document.fonts.check('16px Inter') || document.fonts.check('16px Manrope') : true;

  if (isFontLoaded) {
    // Fonts already loaded
    mountAndHideLoading();
  } else if (document.fonts) {
    // Wait for fonts to load with timeout
    const timeout = setTimeout(() => {
      if (document.fonts) {
        document.fonts.removeEventListener('loadingdone', fontLoadHandler);
      }
      mountAndHideLoading();
    }, 1000); // 1 second timeout

    const fontLoadHandler = () => {
      clearTimeout(timeout);
      if (document.fonts) {
        document.fonts.removeEventListener('loadingdone', fontLoadHandler);
      }
      mountAndHideLoading();
    };

    document.fonts.addEventListener('loadingdone', fontLoadHandler);
  } else {
    // No font loading API, just mount
    mountAndHideLoading();
  }
}

function mountAndHideLoading() {
  app.mount('#app')
  hideLoadingIndicator();
}

// Initialize the app with font loading considerations
document.addEventListener('DOMContentLoaded', () => {
  // Ensure the app element is visible initially
  const appEl = document.getElementById('app');
  if (appEl) {
    appEl.style.display = 'block';
    appEl.style.visibility = 'visible';
  }

  // Wait for fonts or mount immediately
  waitForFontsOrTimeout();
});