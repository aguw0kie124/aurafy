<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { Bell, Search, Settings } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';

	let { children } = $props();

	const navItems = [
		{ label: 'Dashboard', href: '/' },
		{ label: 'Artists', href: '/artists' },
		{ label: 'Songs', href: '/songs' },
		{ label: 'Albums', href: '/albums' },
		{ label: 'Genres', href: '/genres' }
	] as const;

	const currentPath = $derived(page.url.pathname);
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Statify</title>
</svelte:head>

<div class="app-frame">
	<header class="topbar">
		<div class="page-shell topbar-inner">
			<a class="brand" href={resolve('/')}>Statify</a>

			<label class="search">
				<Search size={18} strokeWidth={2} />
				<input type="search" placeholder="Search..." />
			</label>

			<nav aria-label="Primary">
				{#each navItems as item (item.href)}
					<a
						href={resolve(item.href)}
						class:active={currentPath === item.href}
						aria-current={currentPath === item.href ? 'page' : undefined}
					>
						{item.label}
					</a>
				{/each}
			</nav>

			<div class="tools">
				<button type="button" aria-label="Notifications">
					<Bell size={20} strokeWidth={2} />
				</button>
				<button type="button" aria-label="Settings">
					<Settings size={21} strokeWidth={2} />
				</button>
				<span class="profile">
					<MediaThumb kind="artist" alt="Profile image" size="small" round label="You" />
				</span>
			</div>
		</div>
	</header>

	<main class="page-shell">
		{@render children()}
	</main>
</div>

<style>
	.app-frame {
		display: flex;
		min-height: 100vh;
		flex-direction: column;
	}

	.topbar {
		border-bottom: 1px solid rgba(255, 255, 255, 0.08);
		background: #373737;
	}

	.topbar-inner {
		display: grid;
		grid-template-columns: auto minmax(220px, 320px) 1fr auto;
		align-items: center;
		gap: 28px;
		min-height: 78px;
	}

	.brand {
		color: #71ef9d;
		font-size: 1.7rem;
		font-weight: 700;
	}

	.search {
		display: flex;
		align-items: center;
		gap: 12px;
		min-height: 48px;
		padding: 0 18px;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.03);
		color: #d0d5d2;
	}

	.search input {
		width: 100%;
		border: 0;
		background: transparent;
		color: #f7f8f7;
		outline: 0;
	}

	.search input::placeholder {
		color: #d0d5d2;
	}

	nav {
		display: flex;
		align-items: center;
		justify-content: center;
		gap: clamp(18px, 2.6vw, 42px);
	}

	nav a {
		position: relative;
		color: #e3e7e4;
		font-weight: 600;
		padding: 29px 0 25px;
	}

	nav a::after {
		position: absolute;
		right: 0;
		bottom: 18px;
		left: 0;
		height: 2px;
		border-radius: 999px;
		background: transparent;
		content: '';
	}

	nav a.active::after {
		background: #71ef9d;
	}

	.tools {
		display: flex;
		align-items: center;
		gap: 18px;
	}

	.tools button {
		display: grid;
		width: 34px;
		height: 34px;
		place-items: center;
		border: 0;
		background: transparent;
		color: #dce2de;
		cursor: pointer;
	}

	.profile {
		display: grid;
		padding-left: 4px;
	}

	main {
		flex: 1;
		padding-block: 42px 48px;
	}

	@media (max-width: 1100px) {
		.topbar-inner {
			grid-template-columns: auto 1fr auto;
		}

		.search {
			order: 3;
			grid-column: 1 / -1;
			margin-bottom: 16px;
		}

		nav {
			justify-content: end;
		}
	}

	@media (max-width: 760px) {
		.topbar-inner {
			grid-template-columns: 1fr auto;
			gap: 14px;
			padding-block: 14px;
		}

		nav {
			order: 3;
			grid-column: 1 / -1;
			justify-content: space-between;
			gap: 12px;
			overflow-x: auto;
		}

		nav a {
			padding: 12px 0 16px;
			white-space: nowrap;
		}

		nav a::after {
			bottom: 8px;
		}

		.search {
			order: 4;
			margin-bottom: 0;
		}
	}
</style>
