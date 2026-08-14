import { useCallback, useEffect, useState } from 'react';
import { Sparkles, ExternalLink, RefreshCw } from 'lucide-react';
import MediaThumb from '@/lib/components/MediaThumb';
import SectionHeading from '@/lib/components/SectionHeading';
import PlaylistModal from '@/lib/components/PlaylistModal';
import {
	recommendations,
	previewPlaylist,
	createPlaylist,
	type Recommendations,
	type RecPlaylist,
	type ProposedPlaylist,
	type StatsRangeValue
} from '@/lib/data/music';
import styles from './ForYou.module.css';

const lengthOptions = [10, 15, 25, 40, 50];

const rowSkeletons = Array.from({ length: 3 }, (_, i) => i);
const cardSkeletons = Array.from({ length: 6 }, (_, i) => i);

// Per-shelf save state, keyed by playlist.key — each row saves independently.
type SaveState = { status: 'saving' | 'saved' | 'error'; url?: string | null; error?: string };

// Page contract props (unused here, but App passes them to every page).
type ForYouProps = {
	activeRange?: StatsRangeValue;
	onRangeChange?: (range: StatsRangeValue) => void;
	loading?: boolean;
};

export default function ForYou(_props: ForYouProps) {
	const [instruction, setInstruction] = useState('');
	const [length, setLength] = useState(25);
	const [describeError, setDescribeError] = useState('');

	const [feed, setFeed] = useState<Recommendations | null>(null);
	const [feedStatus, setFeedStatus] = useState<'loading' | 'ready' | 'error'>('loading');
	const [refreshing, setRefreshing] = useState(false);

	const [modalOpen, setModalOpen] = useState(false);
	const [modalLoading, setModalLoading] = useState(false);
	const [modalPlaylist, setModalPlaylist] = useState<ProposedPlaylist | RecPlaylist | null>(null);

	const [saveStates, setSaveStates] = useState<Record<string, SaveState>>({});

	const loadFeed = useCallback(async (refresh = false) => {
		// On refresh keep the current feed visible and just spin the button; only the
		// first (cold) load shows the full skeletons.
		if (refresh) setRefreshing(true);
		else setFeedStatus('loading');
		try {
			setFeed(await recommendations(refresh));
			// Keys are stable across rebuilds but their tracks are not, so a stale
			// "Open in Spotify" would point at the wrong playlist.
			setSaveStates({});
			setFeedStatus('ready');
		} catch {
			if (!refresh) setFeedStatus('error');
		} finally {
			setRefreshing(false);
		}
	}, []);

	useEffect(() => {
		void loadFeed();
	}, [loadFeed]);

	async function describe() {
		const text = instruction.trim();
		if (!text) return;
		setDescribeError('');
		setModalPlaylist(null);
		setModalLoading(true);
		setModalOpen(true);
		try {
			setModalPlaylist(await previewPlaylist({ instruction: text, length }));
		} catch (error) {
			setModalOpen(false);
			setDescribeError(error instanceof Error ? error.message : 'Could not build a playlist.');
		} finally {
			setModalLoading(false);
		}
	}

	async function saveRow(playlist: RecPlaylist) {
		if (saveStates[playlist.key]?.status === 'saving') return;
		setSaveStates((states) => ({ ...states, [playlist.key]: { status: 'saving' } }));
		try {
			const result = await createPlaylist({
				name: playlist.name,
				description: playlist.description,
				trackUris: playlist.trackUris,
				isPublic: false
			});
			setSaveStates((states) => ({
				...states,
				[playlist.key]: { status: 'saved', url: result.spotifyUrl }
			}));
		} catch (error) {
			setSaveStates((states) => ({
				...states,
				[playlist.key]: {
					status: 'error',
					error: error instanceof Error ? error.message : 'Could not save to Spotify.'
				}
			}));
		}
	}

	return (
		<>
			<section className={styles.pageHeader}>
				<SectionHeading title="For You" subtitle="New music, picked from what you love." />
				<button
					type="button"
					className={styles.refresh}
					onClick={() => loadFeed(true)}
					disabled={refreshing || feedStatus === 'loading'}
					title="Rebuild your feed with fresh picks"
				>
					<RefreshCw size={16} strokeWidth={2.2} className={refreshing ? 'spin' : undefined} />
					{refreshing ? 'Refreshing…' : 'Refresh'}
				</button>
			</section>

			{/* AI describe bar */}
			<form
				className={styles.describe}
				onSubmit={(event) => {
					event.preventDefault();
					void describe();
				}}
			>
				<div className={styles.describeField}>
					<Sparkles size={20} strokeWidth={2.2} className={styles.describeIcon} />
					<input
						type="text"
						value={instruction}
						onChange={(event) => setInstruction(event.target.value)}
						placeholder="Describe what you want to hear — “late-night drive, moody synths”"
						aria-label="Describe what you want to hear"
					/>
					<select
						value={length}
						onChange={(event) => setLength(Number(event.target.value))}
						aria-label="Playlist length"
						className={styles.length}
					>
						{lengthOptions.map((option) => (
							<option key={option} value={option}>
								{option} tracks
							</option>
						))}
					</select>
					<button type="submit" className={styles.go} disabled={!instruction.trim()}>
						Create
					</button>
				</div>
				{describeError && <p className={styles.error}>{describeError}</p>}
			</form>

			{/* Feed */}
			{feedStatus === 'loading' ? (
				<div className={styles.feed}>
					{rowSkeletons.map((row) => (
						<section key={row} className={styles.shelf}>
							<span className={`skeleton ${styles.skelHeading}`}></span>
							<div className={styles.rail}>
								{cardSkeletons.map((card) => (
									<article key={card} className={`${styles.song} ${styles.skeletonCard}`}>
										<span className={`skeleton ${styles.skelArt}`}></span>
										<span className={`skeleton ${styles.skelLine}`} style={{ width: '80%' }}></span>
										<span className={`skeleton ${styles.skelLine}`} style={{ width: '55%' }}></span>
									</article>
								))}
							</div>
						</section>
					))}
				</div>
			) : feedStatus === 'error' ? (
				<div className={styles.notice}>
					<p>Couldn’t load your recommendations.</p>
					<button type="button" className={styles.ghost} onClick={() => loadFeed()}>
						<RefreshCw size={16} strokeWidth={2.2} /> Try again
					</button>
				</div>
			) : feed ? (
				<div className={styles.feed}>
					{feed.playlists.map((playlist) => {
						const save = saveStates[playlist.key];
						return (
							<section key={playlist.key} className={styles.shelf}>
								<header className={styles.shelfHead}>
									<div className={styles.shelfTitle}>
										<h2>{playlist.name}</h2>
										<small>
											{playlist.description} · {playlist.tracks.length} tracks
										</small>
									</div>
									{save?.status === 'saved' && save.url ? (
										<a
											className={styles.save}
											href={save.url}
											target="_blank"
											rel="noreferrer noopener"
										>
											<ExternalLink size={15} strokeWidth={2.2} /> Open in Spotify
										</a>
									) : (
										<button
											type="button"
											className={styles.save}
											onClick={() => saveRow(playlist)}
											disabled={save?.status === 'saving'}
										>
											{save?.status === 'saving' ? 'Saving…' : 'Save as playlist'}
										</button>
									)}
								</header>
								{save?.status === 'error' && <p className={styles.error}>{save.error}</p>}
								<div className={styles.rail}>
									{playlist.tracks.map((track, index) => (
										<article key={track.spotifyTrackId ?? index} className={styles.song}>
											<MediaThumb
												kind="cover"
												src={track.coverUrl}
												alt={`${track.album} artwork`}
												size="large"
												label={track.title}
											/>
											<strong>{track.title}</strong>
											<small>{track.artist}</small>
											{track.externalUrl && (
												<a
													className={styles.open}
													href={track.externalUrl}
													target="_blank"
													rel="noreferrer noopener"
													aria-label={`Open ${track.title} in Spotify`}
												>
													<ExternalLink size={16} strokeWidth={2.2} />
												</a>
											)}
										</article>
									))}
								</div>
							</section>
						);
					})}

					{!feed.playlists.length && (
						<div className={styles.notice}>
							<p>Sync your Spotify library to get recommendations.</p>
						</div>
					)}
				</div>
			) : null}

			<PlaylistModal
				open={modalOpen}
				loading={modalLoading}
				playlist={modalPlaylist}
				onClose={() => setModalOpen(false)}
			/>
		</>
	);
}
