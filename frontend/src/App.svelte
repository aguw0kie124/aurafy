<script lang="ts">
	import { onMount } from 'svelte';
	import { LogIn, LogOut, RefreshCw } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import { API_BASE_URL } from '$lib/config';
	import { loadMusicData, syncListeningHistory } from '$lib/data/music';
	import favicon from '$lib/assets/favicon.svg';
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
		{ label: 'Recap', href: '/' },
		{ label: 'Artists', href: '/artists' },
		{ label: 'Songs', href: '/songs' },
		{ label: 'Albums', href: '/albums' }
	] as const;

	const pages = {
		'/': Recap,
		'/artists': Artists,
		'/songs': Songs,
		'/albums': Albums,
		'/recap': Recap
	} as const;

	let currentUrl = $state(new URL(window.location.href));

	const currentPath = $derived(currentUrl.pathname);
	const activePath = $derived(currentPath === '/recap' ? '/' : currentPath);
	const authError = $derived(currentUrl.searchParams.get('auth_error'));
	const CurrentPage = $derived(pages[currentPath as keyof typeof pages] ?? Recap);

	let authStatus = $state<'loading' | 'anonymous' | 'authenticated'>('loading');
	let user = $state<AuthUser | null>(null);
	let authCheckFailed = $state(false);
	let statsStatus = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
	let statsVersion = $state(0);
	let syncing = $state(false);
	let profileMenuOpen = $state(false);

	const isAuthenticated = $derived(authStatus === 'authenticated' && user !== null);

	onMount(() => {
		void loadSession();

		const handlePopState = () => {
			currentUrl = new URL(window.location.href);
			profileMenuOpen = false;
		};

		const handleWindowClick = () => {
			profileMenuOpen = false;
		};

		const handleKeydown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				profileMenuOpen = false;
			}
		};

		window.addEventListener('popstate', handlePopState);
		window.addEventListener('click', handleWindowClick);
		window.addEventListener('keydown', handleKeydown);

		return () => {
			window.removeEventListener('popstate', handlePopState);
			window.removeEventListener('click', handleWindowClick);
			window.removeEventListener('keydown', handleKeydown);
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
		profileMenuOpen = false;

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
		profileMenuOpen = false;
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
							class:active={activePath === item.href}
							aria-current={activePath === item.href ? 'page' : undefined}
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
					<div class="profile-menu-wrap">
						<button
							type="button"
							class="profile"
							aria-label="Profile menu"
							aria-haspopup="menu"
							aria-expanded={profileMenuOpen}
							onclick={(event) => {
								event.stopPropagation();
								profileMenuOpen = !profileMenuOpen;
							}}
						>
							<MediaThumb
								kind="artist"
								src={user?.imageUrl ?? undefined}
								alt="Profile image"
								size="small"
								round
								label={user?.displayName ?? 'You'}
							/>
						</button>

						{#if profileMenuOpen}
							<div class="profile-menu">
								<div class="profile-summary">
									<MediaThumb
										kind="artist"
										src={user?.imageUrl ?? undefined}
										alt="Profile image"
										size="small"
										round
										label={user?.displayName ?? 'You'}
									/>
									<span>
										<strong>{user?.displayName ?? 'Spotify user'}</strong>
										<small>{user?.spotifyUserId ?? 'Signed in'}</small>
									</span>
								</div>

								<button type="button" class="menu-action" onclick={logout}>
									<LogOut size={18} strokeWidth={2.1} />
									Log out
								</button>
							</div>
						{/if}
					</div>
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
		border: 1px solid var(--color-border);
		border-radius: 8px;
		background: var(--color-surface-elevated);
		box-shadow: 0 24px 70px rgba(0, 0, 0, 0.4);
	}

	.login-brand {
		color: var(--color-accent);
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
		color: var(--color-soft);
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
		background: var(--color-accent);
		color: #061109;
		font-weight: 800;
		cursor: pointer;
		transition:
			background 160ms ease,
			transform 160ms ease;
	}

	.login-panel button:hover {
		background: var(--color-accent-hover);
		transform: translateY(-1px);
	}

	.topbar {
		position: sticky;
		top: 0;
		z-index: 20;
		background: #000;
	}

	.topbar-inner {
		display: grid;
		grid-template-columns: auto 1fr auto;
		align-items: center;
		gap: 24px;
		min-height: 64px;
	}

	.brand {
		display: inline-flex;
		align-items: center;
		color: #fff;
		font-size: 1.2rem;
		font-weight: 900;
		letter-spacing: 0;
	}

	nav {
		display: flex;
		align-items: center;
		justify-content: center;
		justify-self: center;
		gap: clamp(18px, 3vw, 34px);
	}

	nav a {
		position: relative;
		color: var(--color-muted);
		font-size: 0.92rem;
		font-weight: 800;
		padding: 22px 0 20px;
		transition: color 160ms ease;
	}

	nav a:hover {
		color: #fff;
	}

	nav a::after {
		position: absolute;
		right: 0;
		bottom: 14px;
		left: 0;
		height: 2px;
		border-radius: 999px;
		background: transparent;
		content: '';
	}

	nav a.active {
		color: #fff;
	}

	nav a.active::after {
		background: var(--color-accent);
	}

	.tools {
		display: flex;
		align-items: center;
		gap: 8px;
	}

	.tools button {
		display: grid;
		width: 36px;
		height: 36px;
		place-items: center;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: var(--color-soft);
		cursor: pointer;
		transition:
			background 160ms ease,
			color 160ms ease,
			transform 160ms ease;
	}

	.tools button:hover:not(:disabled) {
		background: #1f1f1f;
		color: #fff;
	}

	.tools button:disabled {
		cursor: progress;
		opacity: 0.62;
	}

	.profile {
		display: grid;
		width: auto;
		height: auto;
		padding: 0;
		border-color: transparent;
		background: transparent;
	}

	.profile-menu-wrap {
		position: relative;
		display: grid;
	}

	.profile-menu {
		position: absolute;
		top: calc(100% + 10px);
		right: 0;
		z-index: 40;
		display: grid;
		width: min(260px, calc(100vw - 32px));
		gap: 6px;
		padding: 6px;
		border-radius: 8px;
		background: #282828;
		box-shadow: 0 18px 50px rgba(0, 0, 0, 0.48);
	}

	.profile-summary {
		display: grid;
		grid-template-columns: 48px minmax(0, 1fr);
		align-items: center;
		gap: 12px;
		padding: 10px;
	}

	.profile-summary span {
		display: grid;
		min-width: 0;
		gap: 3px;
	}

	.profile-summary strong,
	.profile-summary small {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.profile-summary small {
		color: var(--color-muted);
	}

	.tools .menu-action {
		display: flex;
		width: 100%;
		height: auto;
		min-height: 42px;
		align-items: center;
		justify-content: start;
		gap: 10px;
		padding: 0 12px;
		border-radius: 6px;
		background: transparent;
		color: #fff;
		font-weight: 800;
	}

	.tools .menu-action:hover {
		background: #3a3a3a;
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
		padding-block: 24px 48px;
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
			justify-self: stretch;
			gap: 12px;
			overflow-x: auto;
		}

		nav a {
			padding: 10px 0 14px;
			white-space: nowrap;
		}

		nav a::after {
			bottom: 6px;
		}
	}
</style>
