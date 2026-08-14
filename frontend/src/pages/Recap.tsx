import { useMemo, useState } from 'react';
import {
	BarChart3,
	ExternalLink,
	Headphones,
	ListMusic,
	Music2,
	Play,
	Sparkles,
	Trophy
} from 'lucide-react';
import EmptyState from '@/lib/components/EmptyState';
import MediaThumb from '@/lib/components/MediaThumb';
import RangeTabs from '@/lib/components/RangeTabs';
import { rangeOptions, type MusicData, type StatsRangeValue } from '@/lib/data/music';
import { useMusicData } from '@/lib/data/MusicDataContext';
import styles from './Recap.module.css';

type RecapTab = 'tracks' | 'artists' | 'albums';

type RecapItem = {
	id: string;
	imageKind: 'artist' | 'cover';
	imageUrl: string | null;
	imageRound: boolean;
	title: string;
	subtitle: string;
	externalUrl: string | null;
	spotifyRank?: number;
	topTrackCount?: number;
	source: 'spotify' | 'spotify_derived';
};

const numberFormatter = new Intl.NumberFormat('en-US');

const tabOptions = [
	{ id: 'tracks', label: 'Tracks' },
	{ id: 'artists', label: 'Artists' },
	{ id: 'albums', label: 'Albums' }
] as const;

const summarySkeletonCards = Array.from({ length: 4 }, (_, index) => index);
const recapSkeletonRows = Array.from({ length: 6 }, (_, index) => index);
const dnaSkeletonCards = Array.from({ length: 4 }, (_, index) => index);

function getItems(tab: RecapTab, data: MusicData): RecapItem[] {
	if (tab === 'artists') {
		return data.artists.map((artist, index) => ({
			id: artist.spotifyArtistId ?? `artist-${artist.name}-${index}`,
			imageKind: 'artist',
			imageUrl: artist.imageUrl,
			imageRound: true,
			title: artist.name,
			subtitle: 'Artist',
			externalUrl: artist.externalUrl ?? null,
			spotifyRank: artist.spotifyRank,
			topTrackCount: artist.topTrackCount,
			source: artist.source === 'spotify_derived' ? 'spotify_derived' : 'spotify'
		}));
	}

	if (tab === 'albums') {
		return data.albums.map((album, index) => ({
			id: album.spotifyAlbumId ?? `album-${album.title}-${album.artist}-${index}`,
			imageKind: 'cover',
			imageUrl: album.coverUrl,
			imageRound: false,
			title: album.title,
			subtitle: album.artist,
			externalUrl: album.externalUrl ?? null,
			spotifyRank: album.spotifyRank,
			topTrackCount: album.topTrackCount,
			source: 'spotify_derived'
		}));
	}

	return data.tracks.map((track, index) => ({
		id: track.spotifyTrackId ?? `track-${track.title}-${track.artist}-${index}`,
		imageKind: 'cover',
		imageUrl: track.coverUrl,
		imageRound: false,
		title: track.title,
		subtitle: track.artist,
		externalUrl: track.externalUrl ?? null,
		spotifyRank: track.spotifyRank,
		source: 'spotify'
	}));
}

function resolveTab(tab: RecapTab, data: MusicData): RecapTab {
	if (getItems(tab, data).length > 0) {
		return tab;
	}

	return tabOptions.find((option) => getItems(option.id, data).length > 0)?.id ?? tab;
}

function rankItems(items: RecapItem[]) {
	return [...items]
		.sort((a, b) => {
			const rankA = a.spotifyRank ?? Number.POSITIVE_INFINITY;
			const rankB = b.spotifyRank ?? Number.POSITIVE_INFINITY;

			if (rankA !== rankB) {
				return rankA - rankB;
			}

			return a.title.localeCompare(b.title);
		})
		.slice(0, 6);
}

function formatNumber(value: number | null | undefined) {
	return numberFormatter.format(value ?? 0);
}

function getMetricLabel(item: RecapItem) {
	if (item.topTrackCount) {
		const trackLabel = item.topTrackCount === 1 ? 'top track' : 'top tracks';
		return `#${item.spotifyRank ?? '--'} • ${formatNumber(item.topTrackCount)} ${trackLabel}`;
	}

	if (item.spotifyRank) {
		return `#${item.spotifyRank}`;
	}

	return 'Spotify';
}

function formatSource(item: RecapItem) {
	return item.source === 'spotify_derived' ? 'From top tracks' : 'Spotify';
}

export default function Recap({
	activeRange = 'short_term',
	onRangeChange = () => {},
	loading = false
}: {
	activeRange?: StatsRangeValue;
	onRangeChange?: (range: StatsRangeValue) => void;
	loading?: boolean;
}) {
	const data = useMusicData();
	const { summary, tracks, artists, albums, musicalDna } = data;

	const [activeTab, setActiveTab] = useState<RecapTab>('tracks');
	const [selectedId, setSelectedId] = useState<string | null>(null);

	const topTrack = tracks[0] ?? null;
	const topArtist = artists[0] ?? null;
	const resolvedTab = useMemo(() => resolveTab(activeTab, data), [activeTab, data]);
	const activeTabItems = useMemo(() => getItems(resolvedTab, data), [resolvedTab, data]);
	const rankedItems = useMemo(() => rankItems(activeTabItems), [activeTabItems]);
	const selectedItem = rankedItems.find((item) => item.id === selectedId) ?? rankedItems[0] ?? null;
	const heroArtwork =
		topTrack?.coverUrl ?? topArtist?.imageUrl ?? summary.currentArtistImageUrl ?? null;
	const heroArtworkAlt = topTrack
		? `${topTrack.album} album artwork`
		: `${summary.currentArtist ?? 'Top artist'} artwork`;
	const heroTitle = topTrack?.title ?? summary.currentArtist ?? 'Listening recap';
	const activeTabLabel = tabOptions.find((option) => option.id === resolvedTab)?.label ?? 'Tracks';
	const activeRangeLabel =
		rangeOptions.find((option) => option.value === activeRange)?.label ?? '4 Weeks';
	const summaryCards = [
		{
			label: 'Top Track',
			value: topTrack?.title ?? 'No data yet',
			icon: Music2
		},
		{
			label: 'Top Artist',
			value: topArtist?.name ?? summary.currentArtist ?? 'No data yet',
			icon: Trophy
		},
		{
			label: 'Tracks',
			value: formatNumber(tracks.length),
			icon: ListMusic
		},
		{
			label: 'Albums',
			value: formatNumber(albums.length),
			icon: BarChart3
		}
	];

	function getTabCount(tab: RecapTab) {
		return getItems(tab, data).length;
	}

	function spotlightTopTrack() {
		setActiveTab('tracks');
		setSelectedId(getItems('tracks', data)[0]?.id ?? null);
	}

	return (
		<section className={styles.recapShell}>
			{loading ? (
				<>
					<section className={`${styles.recapHero} ${styles.loadingHero}`}>
						<div
							className={`${styles.heroArtwork} ${styles.heroArtworkLoading}`}
							aria-hidden="true"
						>
							<span className={`skeleton ${styles.skeletonHeroArt}`}></span>
						</div>

						<div className={styles.heroCopy}>
							<span
								className={`skeleton skeleton-line ${styles.skeletonEyebrow}`}
								aria-hidden="true"
							></span>
							<span className={`skeleton ${styles.skeletonHeroTitle}`} aria-hidden="true"></span>
							<div className={styles.heroRange}>
								<span>{activeRangeLabel}</span>
								<RangeTabs active={activeRange} onSelect={onRangeChange} />
							</div>
						</div>
					</section>

					<section className={styles.metricStrip} aria-hidden="true">
						{summarySkeletonCards.map((item) => (
							<article key={item}>
								<span className={`${styles.metricIcon} skeleton ${styles.skeletonIcon}`}></span>
								<span className={`skeleton skeleton-line ${styles.skeletonLabel}`}></span>
								<span className={`skeleton skeleton-line ${styles.skeletonValue}`}></span>
							</article>
						))}
					</section>

					<section className={styles.recapStudio} aria-hidden="true">
						<div className={styles.sectionToolbar}>
							<span className={`skeleton skeleton-line ${styles.skeletonHeading}`}></span>

							<div className={styles.controlRow}>
								<span className={`skeleton ${styles.skeletonToggle}`}></span>
								<span className={`skeleton ${styles.skeletonPill}`}></span>
							</div>
						</div>

						<div className={styles.recapLayout}>
							<div className={styles.rankedPanel} aria-label="Loading ranked listening list">
								{recapSkeletonRows.map((item) => (
									<div key={item} className={`${styles.rankRow} ${styles.skeletonRankRow}`}>
										<div className={`${styles.rankMain} ${styles.skeletonRankMain}`}>
											<span
												className={`skeleton skeleton-line ${styles.skeletonRankNumber}`}
											></span>
											<span className={`skeleton ${styles.skeletonThumb}`}></span>
											<span className={`${styles.rankCopy} ${styles.skeletonRankCopy}`}>
												<span
													className={`skeleton skeleton-line ${styles.skeletonCopyTitle}`}
												></span>
												<span
													className={`skeleton skeleton-line ${styles.skeletonCopyMeta}`}
												></span>
											</span>
											<span className={styles.rankMeter}>
												<span className={`skeleton skeleton-line ${styles.skeletonMeter}`}></span>
											</span>
										</div>

										<span className={styles.iconButton}>
											<span className={`skeleton ${styles.skeletonIconButton}`}></span>
										</span>
									</div>
								))}
							</div>

							<aside className={styles.detailPanel} aria-label="Loading selected recap item">
								<span className={`skeleton ${styles.skeletonDetailArtwork}`}></span>
								<div className={`${styles.detailCopy} ${styles.skeletonDetailCopy}`}>
									<span className={`skeleton skeleton-line ${styles.skeletonDetailTitle}`}></span>
									<span className={`skeleton skeleton-line ${styles.skeletonDetailMeta}`}></span>
								</div>

								<dl>
									<div>
										<dt className={`skeleton skeleton-line ${styles.skeletonDt}`}></dt>
										<dd className={`skeleton skeleton-line ${styles.skeletonDd}`}></dd>
									</div>
									<div>
										<dt className={`skeleton skeleton-line ${styles.skeletonDt}`}></dt>
										<dd className={`skeleton skeleton-line ${styles.skeletonDd}`}></dd>
									</div>
								</dl>

								<span className={`skeleton ${styles.skeletonLink}`}></span>
							</aside>
						</div>
					</section>

					<section className={styles.dnaSection} aria-hidden="true">
						<div className={styles.sectionToolbar}>
							<span
								className={`skeleton skeleton-line ${styles.skeletonHeading} ${styles.skeletonHeadingSmall}`}
							></span>
						</div>

						<div className={styles.dnaRow}>
							{dnaSkeletonCards.map((item) => (
								<article key={item}>
									<span className={`${styles.dnaIcon} skeleton ${styles.skeletonIcon}`}></span>
									<span className={`skeleton skeleton-line ${styles.skeletonLabel}`}></span>
									<span className={`skeleton skeleton-line ${styles.skeletonValue}`}></span>
								</article>
							))}
						</div>
					</section>
				</>
			) : tracks.length > 0 || artists.length > 0 ? (
				<>
					<section className={styles.recapHero}>
						<div className={styles.heroArtwork}>
							{heroArtwork ? (
								<img src={heroArtwork} alt={heroArtworkAlt} />
							) : (
								<div className={styles.heroPlaceholder}>
									<Music2 size={52} strokeWidth={1.7} />
								</div>
							)}
							<button
								type="button"
								className={styles.heroPlay}
								aria-label="Spotlight top track"
								onClick={spotlightTopTrack}
							>
								<Play size={24} fill="currentColor" strokeWidth={2.1} />
							</button>
						</div>

						<div className={styles.heroCopy}>
							<p className="eyebrow">Top Track</p>
							<h1>{heroTitle}</h1>
							<div className={styles.heroRange}>
								<span>{activeRangeLabel}</span>
								<RangeTabs active={activeRange} onSelect={onRangeChange} />
							</div>
						</div>
					</section>

					<section className={styles.metricStrip} aria-label="Listening totals">
						{summaryCards.map((card) => {
							const Icon = card.icon;
							return (
								<article key={card.label}>
									<span className={styles.metricIcon}>
										<Icon size={19} strokeWidth={2.2} />
									</span>
									<span>{card.label}</span>
									<strong>{card.value}</strong>
								</article>
							);
						})}
					</section>

					<section className={styles.recapStudio}>
						<div className={styles.sectionToolbar}>
							<h2>Top {activeTabLabel}</h2>

							<div className={styles.controlRow}>
								<div className={styles.categoryToggle} aria-label="Recap category">
									{tabOptions.map((option) => (
										<button
											key={option.id}
											type="button"
											className={resolvedTab === option.id ? styles.active : undefined}
											disabled={getTabCount(option.id) === 0}
											onClick={() => {
												setActiveTab(option.id);
												setSelectedId(null);
											}}
										>
											{option.label}
										</button>
									))}
								</div>

								<div className={styles.sourcePill} aria-label="Stats source">
									Rank
								</div>
							</div>
						</div>

						<div className={styles.recapLayout}>
							<div className={styles.rankedPanel} aria-label="Ranked listening list">
								{rankedItems.map((item, index) => (
									<div
										key={item.id}
										className={`${styles.rankRow}${
											selectedItem?.id === item.id ? ` ${styles.selected}` : ''
										}`}
									>
										<button
											type="button"
											className={styles.rankMain}
											aria-pressed={selectedItem?.id === item.id}
											onClick={() => setSelectedId(item.id)}
										>
											<span className={styles.rankNumber}>{index + 1}</span>
											<MediaThumb
												kind={item.imageKind}
												src={item.imageUrl}
												alt={`${item.title} artwork`}
												size="small"
												round={item.imageRound}
												label={item.title}
											/>
											<span className={styles.rankCopy}>
												<strong>{item.title}</strong>
												<small>{item.subtitle}</small>
											</span>
											<span className={styles.rankMeter}>
												<small>{getMetricLabel(item)}</small>
											</span>
										</button>

										{item.externalUrl ? (
											<a
												className={styles.iconButton}
												href={item.externalUrl}
												target="_blank"
												rel="noreferrer noopener"
												aria-label={`Open ${item.title} in Spotify`}
											>
												<ExternalLink size={18} strokeWidth={2.2} />
											</a>
										) : (
											<span
												className={`${styles.iconButton} ${styles.unavailable}`}
												aria-hidden="true"
											>
												<ExternalLink size={18} strokeWidth={2.2} />
											</span>
										)}
									</div>
								))}
							</div>

							<aside className={styles.detailPanel} aria-label="Selected recap item">
								{selectedItem && (
									<>
										<MediaThumb
											kind={selectedItem.imageKind}
											src={selectedItem.imageUrl}
											alt={`${selectedItem.title} artwork`}
											size="large"
											round={selectedItem.imageRound}
											label={selectedItem.title}
										/>
										<div className={styles.detailCopy}>
											<h3>{selectedItem.title}</h3>
											<p>{selectedItem.subtitle}</p>
										</div>

										<dl>
											<div>
												<dt>Rank</dt>
												<dd>{selectedItem.spotifyRank ? `#${selectedItem.spotifyRank}` : '--'}</dd>
											</div>
											<div>
												<dt>Source</dt>
												<dd>{formatSource(selectedItem)}</dd>
											</div>
										</dl>

										{selectedItem.externalUrl && (
											<a
												className={styles.spotifyLink}
												href={selectedItem.externalUrl}
												target="_blank"
												rel="noreferrer noopener"
											>
												Open in Spotify
												<ExternalLink size={17} strokeWidth={2.3} />
											</a>
										)}
									</>
								)}
							</aside>
						</div>
					</section>

					<section className={styles.dnaSection}>
						<div className={styles.sectionToolbar}>
							<h2>DNA</h2>
						</div>

						<div className={styles.dnaRow}>
							{musicalDna.map((item) => (
								<article key={item.label}>
									<span className={styles.dnaIcon}>
										{item.glyph === 'tempo' ? (
											<BarChart3 size={20} strokeWidth={2.2} />
										) : item.glyph === 'mood' ? (
											<Sparkles size={20} strokeWidth={2.2} />
										) : (
											<Play size={20} fill="currentColor" strokeWidth={2.2} />
										)}
									</span>
									<span>{item.label}</span>
									<strong>{item.value}</strong>
								</article>
							))}

							<article>
								<span className={styles.dnaIcon}>
									<Headphones size={20} strokeWidth={2.2} />
								</span>
								<span>Primary format</span>
								<strong>{tracks.length >= albums.length ? 'Tracks' : 'Albums'}</strong>
							</article>
						</div>
					</section>
				</>
			) : (
				<EmptyState title="No recap data yet" />
			)}
		</section>
	);
}
