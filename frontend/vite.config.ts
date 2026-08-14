import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
	envPrefix: ['VITE_', 'PUBLIC_'],
	plugins: [react()],
	publicDir: 'static',
	// Stylesheets use hyphenated class names; expose them to JS in camelCase
	// (styles.topbarInner -> .topbar-inner).
	css: {
		modules: {
			localsConvention: 'camelCase'
		}
	},
	resolve: {
		alias: {
			'@': path.resolve('./src')
		}
	}
});
