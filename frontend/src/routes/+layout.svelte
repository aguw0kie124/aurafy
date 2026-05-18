<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { onMount } from 'svelte';
	import { Bell, LogIn, LogOut, Search, Settings } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import { API_BASE_URL } from '$lib/config';
	import favicon from '$lib/assets/favicon.svg';
	import '../app.css';

	let { children } = $props();

	type AuthUser = {
		spotifyUserId: string;
		displayName: string;
		imageUrl: string | null;
	};

	type AuthStatusResponse = {
		authenticated: boolean;
		user: AuthUser | null;
	};

	const navItems = [
		{ label: 'Dashboard', href: '/' },
		{ label: 'Artists', href: '/artists' },
		{ label: 'Songs', href: '/songs' },
		{ label: 'Albums', href: '/albums' },
		{ label: 'Genres', href: '/genres' }
	] as const;

	const currentPath = $derived(page.url.pathname);
	const authError = $derived(page.url.searchParams.get('auth_error'));

	let authStatus = $state<'loading' | 'anonymous' | 'authenticated'>('loading');
	let user = $state<AuthUser | null>(null);
	let authCheckFailed = $state(false);

	const isAuthenticated = $derived(authStatus === 'authenticated' && user !== null);

	onMount(() => {
		void loadSession();
	});

	async function loadSession() {
		authCheckFailed = false;

		try {
			const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
				credentials: 'include'
			});

			if (!response.ok) {
				throw new Error(`Auth check failed with status ${response.status}`);
			}

			const data = (await response.json()) as AuthStatusResponse;

			if (data.authenticated && data.user) {
				user = data.user;
				authStatus = 'authenticated';
				return;
			}

			user = null;
			authStatus = 'anonymous';
		} catch {
			user = null;
			authStatus = 'anonymous';
			authCheckFailed = true;
		}
	}

	function startSpotifyLogin() {
		window.location.assign(`${API_BASE_URL}/api/auth/spotify/login`);
	}

	async function logout() {
		await fetch(`${API_BASE_URL}/api/auth/logout`, {
			method: 'POST',
			credentials: 'include'
		});

		user = null;
		authStatus = 'anonymous';
		window.location.assign(resolve('/'));
	}
</script>

<svelte:head>
	<link rel="icon" href={favicon} />
	<title>Aurafy</title>
</svelte:head>

<div class="app-frame">
	{#if authStatus === 'loading'}
		<main class="login-shell">
			<section class="login-panel">
				<strong class="login-brand">Aurafy</strong>
				<p>Checking your session...</p>
			</section>
		</main>
	{:else if !isAuthenticated}
		<main class="login-shell">
			<section class="login-panel">
				<strong class="login-brand">Aurafy</strong>
				<h1>Sign in with Spotify</h1>
				<p>Connect your Spotify account to view your listening insights.</p>

				{#if authError}
					<p class="login-error">Spotify sign in did not complete. Try again.</p>
				{:else if authCheckFailed}
					<p class="login-error">The backend is not reachable right now.</p>
				{/if}

				<button type="button" onclick={startSpotifyLogin}>
					<LogIn size={19} strokeWidth={2.2} />
					Continue with Spotify
				</button>
			</section>
		</main>
	{:else}
		<header class="topbar">
			<div class="page-shell topbar-inner">
				<a class="brand" href={resolve('/')}>Aurafy</a>

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
					<button type="button" aria-label="Log out" onclick={logout}>
						<LogOut size={20} strokeWidth={2} />
					</button>
					<span class="profile">
						<MediaThumb
							kind="artist"
							src={user?.imageUrl ?? undefined}
							alt="Profile image"
							size="small"
							round
							label={user?.displayName ?? 'You'}
						/>
					</span>
				</div>
			</div>
		</header>

		<main class="page-shell app-main">
			{@render children()}
		</main>
	{/if}
</div>

<style>
	.app-frame {
		display: flex;
		min-height: 100vh;
		flex-direction: column;
	}

	.login-shell {
		display: grid;
		min-height: 100vh;
		place-items: center;
		padding: 32px;
	}

	.login-panel {
		display: grid;
		width: min(460px, 100%);
		gap: 18px;
		justify-items: start;
		padding: 36px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 10px;
		background: #232323;
	}

	.login-brand {
		color: #71ef9d;
		font-size: 1.6rem;
	}

	.login-panel h1,
	.login-panel p {
		margin: 0;
	}

	.login-panel h1 {
		font-size: clamp(2.1rem, 7vw, 3.4rem);
		line-height: 0.96;
	}

	.login-panel p {
		color: #d0d5d2;
		line-height: 1.5;
	}

	.login-error {
		width: 100%;
		padding: 12px 14px;
		border: 1px solid rgba(255, 120, 120, 0.32);
		border-radius: 8px;
		background: rgba(255, 120, 120, 0.08);
		color: #ffd2d2;
	}

	.login-panel button {
		display: inline-flex;
		align-items: center;
		gap: 10px;
		min-height: 46px;
		margin-top: 4px;
		padding: 0 22px;
		border: 0;
		border-radius: 999px;
		background: #19ce72;
		color: #061109;
		font-weight: 800;
		cursor: pointer;
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

	.app-main {
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
