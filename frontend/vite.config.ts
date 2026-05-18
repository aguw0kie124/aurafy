import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';
import path from 'node:path';

export default defineConfig({
	envPrefix: ['VITE_', 'PUBLIC_'],
	plugins: [
		svelte({
			compilerOptions: {
				runes: true
			}
		})
	],
	publicDir: 'static',
	resolve: {
		alias: {
			$lib: path.resolve('./src/lib')
		}
	}
});
