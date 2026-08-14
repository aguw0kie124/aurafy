import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, Route, Routes, useNavigate, useSearchParams } from 'react-router-dom';
import { LogIn, LogOut, RefreshCw } from 'lucide-react';
import MediaThumb from '@/lib/components/MediaThumb';
import { API_BASE_URL } from '@/lib/config';
import {
	emptyMusicData,
	loadMusicData,
	rangeOptions,
	syncLibrary,
	type MusicData,
	type StatsRangeValue
} from '@/lib/data/music';
import { MusicDataContext } from '@/lib/data/MusicDataContext';
import Recap from './pages/Recap';
import ForYou from './pages/ForYou';
import styles from './App.module.css';

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
	{ label: 'For You', href: '/' },
	{ label: 'Recap', href: '/recap' }
] as const;

function isRange(value: string | null): value is StatsRangeValue {
	return rangeOptions.some((option) => option.value === value);
}

export default function App() {
	const navigate = useNavigate();
	const [searchParams, setSearchParams] = useSearchParams();

	const rangeParam = searchParams.get('range');
	const selectedRange: StatsRangeValue = isRange(rangeParam) ? rangeParam : 'short_term';
	const authError = searchParams.get('auth_error');

	const [authStatus, setAuthStatus] = useState<'loading' | 'anonymous' | 'authenticated'>(
		'loading'
	);
	const [user, setUser] = useState<AuthUser | null>(null);
	const [authCheckFailed, setAuthCheckFailed] = useState(false);
	const [statsStatus, setStatsStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle');
	const [statsVersion, setStatsVersion] = useState(0);
	const [musicData, setMusicData] = useState<MusicData>(emptyMusicData);
	const [syncing, setSyncing] = useState(false);
	const [profileMenuOpen, setProfileMenuOpen] = useState(false);
	const statsRequestId = useRef(0);

	const isAuthenticated = authStatus === 'authenticated' && user !== null;
	const statsLoading = statsStatus === 'loading';
	const selectedRangeLabel =
		rangeOptions.find((option) => option.value === selectedRange)?.label ?? '4 Weeks';

	const loadStats = useCallback(async (range: StatsRangeValue) => {
		const requestId = ++statsRequestId.current;
		setStatsStatus('loading');

		try {
			const data = await loadMusicData(range);
			if (requestId !== statsRequestId.current) {
				return;
			}
			setMusicData(data);
			setStatsStatus('ready');
			setStatsVersion((version) => version + 1);
		} catch {
			if (requestId !== statsRequestId.current) {
				return;
			}
			setStatsStatus('error');
		}
	}, []);

	useEffect(() => {
		async function loadSession() {
			setAuthCheckFailed(false);

			try {
				const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
					credentials: 'include'
				});

				if (!response.ok) {
					throw new Error(`Auth check failed with status ${response.status}`);
				}

				const data = (await response.json()) as AuthStatusResponse;

				if (data.authenticated && data.user) {
					setUser(data.user);
					setAuthStatus('authenticated');
					return;
				}

				setUser(null);
				setAuthStatus('anonymous');
			} catch {
				setUser(null);
				setAuthStatus('anonymous');
				setAuthCheckFailed(true);
			}
		}

		void loadSession();
	}, []);

	// Loads once the session resolves, then again whenever the range changes —
	// including via browser back/forward, since the range lives in the URL.
	useEffect(() => {
		if (authStatus !== 'authenticated') {
			return;
		}
		void loadStats(selectedRange);
	}, [authStatus, selectedRange, loadStats]);

	useEffect(() => {
		const closeProfileMenu = () => setProfileMenuOpen(false);

		const handleKeydown = (event: KeyboardEvent) => {
			if (event.key === 'Escape') {
				setProfileMenuOpen(false);
			}
		};

		window.addEventListener('click', closeProfileMenu);
		window.addEventListener('popstate', closeProfileMenu);
		window.addEventListener('keydown', handleKeydown);

		return () => {
			window.removeEventListener('click', closeProfileMenu);
			window.removeEventListener('popstate', closeProfileMenu);
			window.removeEventListener('keydown', handleKeydown);
		};
	}, []);

	function changeRange(range: StatsRangeValue) {
		// Re-picking the current range is a no-op unless the last load failed, in
		// which case it retries — the URL doesn't change, so the effect won't fire.
		if (range === selectedRange) {
			if (statsStatus !== 'ready') {
				void loadStats(range);
			}
			return;
		}

		setSearchParams({ range }, { replace: true });
	}

	function startSpotifyLogin() {
		window.location.assign(`${API_BASE_URL}/api/auth/spotify/login`);
	}

	async function refreshStats() {
		setSyncing(true);
		setStatsStatus('loading');

		try {
			await syncLibrary();
			setMusicData(await loadMusicData(selectedRange));
			setStatsStatus('ready');
			setStatsVersion((version) => version + 1);
		} catch {
			setStatsStatus('error');
		} finally {
			setSyncing(false);
		}
	}

	async function logout() {
		setProfileMenuOpen(false);

		await fetch(`${API_BASE_URL}/api/auth/logout`, {
			method: 'POST',
			credentials: 'include'
		});

		setUser(null);
		setAuthStatus('anonymous');
		setStatsStatus('idle');
		navigate({ pathname: '/', search: `?range=${selectedRange}` });
	}

	const pageProps = {
		activeRange: selectedRange,
		onRangeChange: changeRange,
		loading: statsLoading
	};

	return (
		<div className={styles.appFrame}>
			{authStatus === 'loading' ? (
				<main className={styles.loginShell}>
					<section className={styles.loginPanel}>
						<strong className={styles.loginBrand}>Aurafy</strong>
						<p>Checking your session...</p>
					</section>
				</main>
			) : !isAuthenticated ? (
				<main className={styles.loginShell}>
					<section className={styles.loginPanel}>
						<strong className={styles.loginBrand}>Aurafy</strong>
						<h1>Sign in with Spotify</h1>
						<p>Connect your Spotify account to view your listening insights.</p>

						{authError ? (
							<p className={styles.loginError}>Spotify sign in did not complete. Try again.</p>
						) : authCheckFailed ? (
							<p className={styles.loginError}>The backend is not reachable right now.</p>
						) : null}

						<button type="button" onClick={startSpotifyLogin}>
							<LogIn size={19} strokeWidth={2.2} />
							Continue with Spotify
						</button>
					</section>
				</main>
			) : (
				<>
					<header className={styles.topbar}>
						<div className={`page-shell ${styles.topbarInner}`}>
							<NavLink
								className={styles.brand}
								to={{ pathname: '/', search: `?range=${selectedRange}` }}
							>
								Aurafy
							</NavLink>

							<nav aria-label="Primary">
								{navItems.map((item) => (
									<NavLink
										key={item.href}
										to={{ pathname: item.href, search: `?range=${selectedRange}` }}
										end={item.href === '/'}
										className={({ isActive }) => (isActive ? styles.active : '')}
									>
										{item.label}
									</NavLink>
								))}
							</nav>

							<div className={styles.tools}>
								<button
									type="button"
									aria-label={syncing ? 'Syncing your library' : 'Sync your library'}
									title="Sync your Spotify library"
									disabled={syncing}
									onClick={refreshStats}
								>
									<RefreshCw className={syncing ? 'spin' : undefined} size={20} strokeWidth={2} />
								</button>
								<div className={styles.profileMenuWrap}>
									<button
										type="button"
										className={styles.profile}
										aria-label="Profile menu"
										aria-haspopup="menu"
										aria-expanded={profileMenuOpen}
										onClick={(event) => {
											event.stopPropagation();
											setProfileMenuOpen((open) => !open);
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

									{profileMenuOpen && (
										<div className={styles.profileMenu}>
											<div className={styles.profileSummary}>
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

											<button type="button" className={styles.menuAction} onClick={logout}>
												<LogOut size={18} strokeWidth={2.1} />
												Log out
											</button>
										</div>
									)}
								</div>
							</div>
						</div>
					</header>

					<main className={`page-shell ${styles.appMain}`} aria-busy={statsLoading}>
						{statsStatus === 'error' ? (
							<p className={styles.statsError}>Stats could not load. Try refreshing.</p>
						) : statsLoading ? (
							<p className="sr-only" aria-live="polite">
								Loading {selectedRangeLabel} stats.
							</p>
						) : null}

						<MusicDataContext value={musicData}>
							<Routes key={`${selectedRange}-${statsVersion}`}>
								<Route path="/recap" element={<Recap {...pageProps} />} />
								<Route path="*" element={<ForYou {...pageProps} />} />
							</Routes>
						</MusicDataContext>
					</main>
				</>
			)}
		</div>
	);
}
