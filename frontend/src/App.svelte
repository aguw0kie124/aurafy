<script lang="ts">
	import { onMount } from 'svelte';
	import { LogIn, LogOut, RefreshCw } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import { API_BASE_URL } from '$lib/config';
	import { loadMusicData, syncListeningHistory } from '$lib/data/music';
	import favicon from '$lib/assets/favicon.svg';
	import Dashboard from './pages/Dashboard.svelte';
	import Artists from './pages/Artists.svelte';
	import Songs from './pages/Songs.svelte';
	import Albums from './pages/Albums.svelte';
	import Recap from './pages/Recap.svelte';
	import './app.css';

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
		{ label: 'Albums', href: '/albums' }
	] as const;

	const pages = {
		'/': Dashboard,
		'/artists': Artists,
		'/songs': Songs,
		'/albums': Albums,
		'/recap': Recap
	} as const;

	let currentUrl = $state(new URL(window.location.href));

	const currentPath = $derived(currentUrl.pathname);
	const authError = $derived(currentUrl.searchParams.get('auth_error'));
	const CurrentPage = $derived(pages[currentPath as keyof typeof pages] ?? Dashboard);

	let authStatus = $state<'loading' | 'anonymous' | 'authenticated'>('loading');
	let user = $state<AuthUser | null>(null);
	let authCheckFailed = $state(false);
	let statsStatus = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
	let statsVersion = $state(0);
	let syncing = $state(false);

	const isAuthenticated = $derived(authStatus === 'authenticated' && user !== null);

	onMount(() => {
		void loadSession();

		const handlePopState = () => {
			currentUrl = new URL(window.location.href);
		};

		window.addEventListener('popstate', handlePopState);

		return () => {
			window.removeEventListener('popstate', handlePopState);
		};
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
				void loadStats();
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

	async function loadStats() {
		statsStatus = 'loading';

		try {
			await loadMusicData();
			statsStatus = 'ready';
			statsVersion += 1;
		} catch {
			statsStatus = 'error';
		}
	}

	function startSpotifyLogin() {
		window.location.assign(`${API_BASE_URL}/api/auth/spotify/login`);
	}

	async function refreshStats() {
		syncing = true;
		statsStatus = 'loading';

		try {
			await syncListeningHistory(true);
			await loadMusicData();
			statsStatus = 'ready';
			statsVersion += 1;
		} catch {
			statsStatus = 'error';
		} finally {
			syncing = false;
		}
	}

	async function logout() {
		await fetch(`${API_BASE_URL}/api/auth/logout`, {
			method: 'POST',
			credentials: 'include'
		});

		user = null;
		authStatus = 'anonymous';
		statsStatus = 'idle';
		navigate('/');
	}

	function navigate(path: string) {
		window.history.pushState({}, '', path);
		currentUrl = new URL(window.location.href);
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
				<a
					class="brand"
					href="/"
					onclick={(event) => {
						event.preventDefault();
						navigate('/');
					}}>Aurafy</a
				>

				<nav aria-label="Primary">
					{#each navItems as item (item.href)}
						<a
							href={item.href}
							class:active={currentPath === item.href}
							aria-current={currentPath === item.href ? 'page' : undefined}
							onclick={(event) => {
								event.preventDefault();
								navigate(item.href);
							}}
						>
							{item.label}
						</a>
					{/each}
				</nav>

				<div class="tools">
					<button
						type="button"
						aria-label={syncing ? 'Refreshing stats' : 'Refresh stats'}
						title="Refresh stats"
						disabled={syncing}
						onclick={refreshStats}
					>
						<RefreshCw class={syncing ? 'spin' : undefined} size={20} strokeWidth={2} />
					</button>
					<button type="button" aria-label="Log out" onclick={logout}>
						<LogOut size={20} strokeWidth={2} />
					</button>
					<button type="button" class="profile" aria-label="Profile settings">
						<MediaThumb
							kind="artist"
							src={user?.imageUrl ?? undefined}
							alt="Profile image"
							size="small"
							round
							label={user?.displayName ?? 'You'}
						/>
					</button>
				</div>
			</div>
		</header>

		<main class="page-shell app-main">
			{#if statsStatus === 'error'}
				<p class="stats-error">Stats could not load. Try refreshing.</p>
			{/if}

			{#key `${currentPath}-${statsVersion}`}
				<CurrentPage />
			{/key}
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
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 28px;
		min-height: 78px;
	}

	.brand {
		color: #71ef9d;
		font-size: 1.7rem;
		font-weight: 700;
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

	.tools button:disabled {
		cursor: progress;
		opacity: 0.62;
	}

	.profile {
		display: grid;
		width: auto;
		height: auto;
		padding-left: 4px;
	}

	.stats-error {
		margin: 0 0 18px;
		padding: 12px 14px;
		border: 1px solid rgba(255, 120, 120, 0.32);
		border-radius: 8px;
		background: rgba(255, 120, 120, 0.08);
		color: #ffd2d2;
	}

	:global(.spin) {
		animation: spin 0.9s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.app-main {
		flex: 1;
		padding-block: 42px 48px;
	}

	@media (max-width: 1100px) {
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
	}
</style>
