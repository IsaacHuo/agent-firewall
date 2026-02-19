import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 9091,
    strictPort: true,
    host: true,
  },
});
