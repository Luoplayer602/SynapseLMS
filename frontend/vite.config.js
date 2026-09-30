import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
    plugins: [react()],
    server: {
        proxy: {
            '/api': {
                target: 'https://synapselms-7e172b4c.fastapicloud.dev',
                changeOrigin: true,
                secure: true,
            },
        },
    },
});
