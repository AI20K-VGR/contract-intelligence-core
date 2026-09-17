import { defineConfig } from 'vite';

// Port 8000 is used by the independent ai-service OCR lab.
export default defineConfig({server: {proxy: {'/api': 'http://127.0.0.1:8001'}}});
