<script lang="ts">
	import {
		BarChart3,
		ExternalLink,
		Headphones,
		ListMusic,
		Music2,
		Play,
		Sparkles,
		Trophy
	} from '@lucide/svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import {
		albums,
		artists,
		dashboardSummary,
		musicalDna,
		rangeOptions,
		tracks,
		type StatsRangeValue
	} from '$lib/data/music';

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

	let {
		activeRange = 'short_term',
		onRangeChange = () => {},
		loading = false
	}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
		loading?: boolean;
	} = $props();

	let activeTab = $state<RecapTab>('tracks');
	let selectedId = $state<string | null>(null);
	const summarySkeletonCards = Array.from({ length: 4 }, (_, index) => index);
	const recapSkeletonRows = Array.from({ length: 6 }, (_, index) => index);
	const dnaSkeletonCards = Array.from({ length: 4 }, (_, index) => index);

	const topTrack = $derived(tracks[0] ?? null);
	const topArtist = $derived(artists[0] ?? null);
	const resolvedTab = $derived.by(() => resolveTab(activeTab));
	const activeTabItems = $derived.by(() => getItems(resolvedTab));
	const rankedItems = $derived.by(() => rankItems(activeTabItems));
	const selectedItem = $derived(
		rankedItems.find((item) => item.id === selectedId) ?? rankedItems[0] ?? null
	);
	const heroArtwork = $derived(
		topTrack?.coverUrl ?? topArtist?.imageUrl ?? dashboardSummary.currentArtistImageUrl ?? null
	);
	const heroArtworkAlt = $derived(
		topTrack
			? `${topTrack.album} album artwork`
			: `${dashboardSummary.currentArtist ?? 'Top artist'} artwork`
	);
	const heroTitle = $derived(
		topTrack?.title ?? dashboardSummary.currentArtist ?? 'Listening recap'
	);
	const activeTabLabel = $derived(
		tabOptions.find((option) => option.id === resolvedTab)?.label ?? 'Tracks'
	);
	const activeRangeLabel = $derived(
		rangeOptions.find((option) => option.value === activeRange)?.label ?? '4 Weeks'
	);
	const summaryCards = $derived([
		{
			label: 'Top Track',
			value: topTrack?.title ?? 'No data yet',
			icon: Music2
		},
		{
			label: 'Top Artist',
			value: topArtist?.name ?? dashboardSummary.currentArtist ?? 'No data yet',
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
	]);

	function resolveTab(tab: RecapTab) {
		if (getItems(tab).length > 0) {
			return tab;
		}

		return tabOptions.find((option) => getItems(option.id).length > 0)?.id ?? tab;
	}

	function getItems(tab: RecapTab): RecapItem[] {
		if (tab === 'artists') {
			return artists.map((artist, index) => ({
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
			return albums.map((album, index) => ({
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

		return tracks.map((track, index) => ({
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

	function getTabCount(tab: RecapTab) {
		return getItems(tab).length;
	}

	function spotlightTopTrack() {
		activeTab = 'tracks';
		selectedId = getItems('tracks')[0]?.id ?? null;
	}

	function formatNumber(value: number | null | undefined) {
		return numberFormatter.format(value ?? 0);
	}

	function formatSource(item: RecapItem) {
		return item.source === 'spotify_derived' ? 'From top tracks' : 'Spotify';
	}
</script>

<section class="recap-shell">
	{#if loading}
		<section class="recap-hero loading-hero">
			<div class="hero-artwork hero-artwork-loading" aria-hidden="true">
				<span class="skeleton skeleton-hero-art"></span>
			</div>

			<div class="hero-copy">
				<span class="skeleton skeleton-line skeleton-eyebrow" aria-hidden="true"></span>
				<span class="skeleton skeleton-hero-title" aria-hidden="true"></span>
				<div class="hero-range">
					<span>{activeRangeLabel}</span>
					<RangeTabs active={activeRange} onSelect={onRangeChange} />
				</div>
			</div>
		</section>

		<section class="metric-strip" aria-hidden="true">
			{#each summarySkeletonCards as item (item)}
				<article>
					<span class="metric-icon skeleton skeleton-icon"></span>
					<span class="skeleton skeleton-line skeleton-label"></span>
					<span class="skeleton skeleton-line skeleton-value"></span>
				</article>
			{/each}
		</section>

		<section class="recap-studio" aria-hidden="true">
			<div class="section-toolbar">
				<span class="skeleton skeleton-line skeleton-heading"></span>

				<div class="control-row">
					<span class="skeleton skeleton-toggle"></span>
					<span class="skeleton skeleton-pill"></span>
				</div>
			</div>

			<div class="recap-layout">
				<div class="ranked-panel" aria-label="Loading ranked listening list">
					{#each recapSkeletonRows as item (item)}
						<div class="rank-row skeleton-rank-row">
							<div class="rank-main skeleton-rank-main">
								<span class="skeleton skeleton-line skeleton-rank-number"></span>
								<span class="skeleton skeleton-thumb"></span>
								<span class="rank-copy skeleton-rank-copy">
									<span class="skeleton skeleton-line skeleton-copy-title"></span>
									<span class="skeleton skeleton-line skeleton-copy-meta"></span>
								</span>
								<span class="rank-meter">
									<span class="skeleton skeleton-line skeleton-meter"></span>
								</span>
							</div>

							<span class="icon-button">
								<span class="skeleton skeleton-icon-button"></span>
							</span>
						</div>
					{/each}
				</div>

				<aside class="detail-panel" aria-label="Loading selected recap item">
					<span class="skeleton skeleton-detail-artwork"></span>
					<div class="detail-copy skeleton-detail-copy">
						<span class="skeleton skeleton-line skeleton-detail-title"></span>
						<span class="skeleton skeleton-line skeleton-detail-meta"></span>
					</div>

					<dl>
						<div>
							<dt class="skeleton skeleton-line skeleton-dt"></dt>
							<dd class="skeleton skeleton-line skeleton-dd"></dd>
						</div>
						<div>
							<dt class="skeleton skeleton-line skeleton-dt"></dt>
							<dd class="skeleton skeleton-line skeleton-dd"></dd>
						</div>
					</dl>

					<span class="skeleton skeleton-link"></span>
				</aside>
			</div>
		</section>

		<section class="dna-section" aria-hidden="true">
			<div class="section-toolbar">
				<span class="skeleton skeleton-line skeleton-heading skeleton-heading-small"></span>
			</div>

			<div class="dna-row">
				{#each dnaSkeletonCards as item (item)}
					<article>
						<span class="dna-icon skeleton skeleton-icon"></span>
						<span class="skeleton skeleton-line skeleton-label"></span>
						<span class="skeleton skeleton-line skeleton-value"></span>
					</article>
				{/each}
			</div>
		</section>
	{:else if tracks.length > 0 || artists.length > 0}
		<section class="recap-hero">
			<div class="hero-artwork">
				{#if heroArtwork}
					<img src={heroArtwork} alt={heroArtworkAlt} />
				{:else}
					<div class="hero-placeholder">
						<Music2 size={52} strokeWidth={1.7} />
					</div>
				{/if}
				<button
					type="button"
					class="hero-play"
					aria-label="Spotlight top track"
					onclick={spotlightTopTrack}
				>
					<Play size={24} fill="currentColor" strokeWidth={2.1} />
				</button>
			</div>

			<div class="hero-copy">
				<p class="eyebrow">Top Track</p>
				<h1>{heroTitle}</h1>
				<div class="hero-range">
					<span>{activeRangeLabel}</span>
					<RangeTabs active={activeRange} onSelect={onRangeChange} />
				</div>
			</div>
		</section>

		<section class="metric-strip" aria-label="Listening totals">
			{#each summaryCards as card (card.label)}
				{@const Icon = card.icon}
				<article>
					<span class="metric-icon">
						<Icon size={19} strokeWidth={2.2} />
					</span>
					<span>{card.label}</span>
					<strong>{card.value}</strong>
				</article>
			{/each}
		</section>

		<section class="recap-studio">
			<div class="section-toolbar">
				<h2>Top {activeTabLabel}</h2>

				<div class="control-row">
					<div class="category-toggle" aria-label="Recap category">
						{#each tabOptions as option (option.id)}
							<button
								type="button"
								class:active={resolvedTab === option.id}
								disabled={getTabCount(option.id) === 0}
								onclick={() => {
									activeTab = option.id;
									selectedId = null;
								}}
							>
								{option.label}
							</button>
						{/each}
					</div>

					<div class="source-pill" aria-label="Stats source">Rank</div>
				</div>
			</div>

			<div class="recap-layout">
				<div class="ranked-panel" aria-label="Ranked listening list">
					{#each rankedItems as item, index (item.id)}
						<div class="rank-row" class:selected={selectedItem?.id === item.id}>
							<button
								type="button"
								class="rank-main"
								aria-pressed={selectedItem?.id === item.id}
								onclick={() => {
									selectedId = item.id;
								}}
							>
								<span class="rank-number">{index + 1}</span>
								<MediaThumb
									kind={item.imageKind}
									src={item.imageUrl}
									alt={`${item.title} artwork`}
									size="small"
									round={item.imageRound}
									label={item.title}
								/>
								<span class="rank-copy">
									<strong>{item.title}</strong>
									<small>{item.subtitle}</small>
								</span>
								<span class="rank-meter">
									<small>{getMetricLabel(item)}</small>
								</span>
							</button>

							{#if item.externalUrl}
								<a
									class="icon-button"
									href={item.externalUrl}
									target="_blank"
									rel="noreferrer noopener"
									aria-label={`Open ${item.title} in Spotify`}
								>
									<ExternalLink size={18} strokeWidth={2.2} />
								</a>
							{:else}
								<span class="icon-button unavailable" aria-hidden="true">
									<ExternalLink size={18} strokeWidth={2.2} />
								</span>
							{/if}
						</div>
					{/each}
				</div>

				<aside class="detail-panel" aria-label="Selected recap item">
					{#if selectedItem}
						<MediaThumb
							kind={selectedItem.imageKind}
							src={selectedItem.imageUrl}
							alt={`${selectedItem.title} artwork`}
							size="large"
							round={selectedItem.imageRound}
							label={selectedItem.title}
						/>
						<div class="detail-copy">
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

						{#if selectedItem.externalUrl}
							<a
								class="spotify-link"
								href={selectedItem.externalUrl}
								target="_blank"
								rel="noreferrer noopener"
							>
								Open in Spotify
								<ExternalLink size={17} strokeWidth={2.3} />
							</a>
						{/if}
					{/if}
				</aside>
			</div>
		</section>

		<section class="dna-section">
			<div class="section-toolbar">
				<h2>DNA</h2>
			</div>

			<div class="dna-row">
				{#each musicalDna as item (item.label)}
					<article>
						<span class="dna-icon">
							{#if item.glyph === 'tempo'}
								<BarChart3 size={20} strokeWidth={2.2} />
							{:else if item.glyph === 'mood'}
								<Sparkles size={20} strokeWidth={2.2} />
							{:else}
								<Play size={20} fill="currentColor" strokeWidth={2.2} />
							{/if}
						</span>
						<span>{item.label}</span>
						<strong>{item.value}</strong>
					</article>
				{/each}

				<article>
					<span class="dna-icon">
						<Headphones size={20} strokeWidth={2.2} />
					</span>
					<span>Primary format</span>
					<strong>{tracks.length >= albums.length ? 'Tracks' : 'Albums'}</strong>
				</article>
			</div>
		</section>
	{:else}
		<EmptyState title="No recap data yet" />
	{/if}
</section>

<style>
	.recap-shell {
		display: grid;
		gap: 20px;
		padding: 0 0 32px;
	}

	.recap-hero {
		display: grid;
		grid-template-columns: minmax(220px, 300px) minmax(0, 1fr);
		align-items: stretch;
		gap: 24px;
		padding: 24px;
		border-radius: 8px;
		background: linear-gradient(180deg, rgba(82, 62, 62, 0.72), #121212 82%);
	}

	.hero-artwork {
		position: relative;
		display: grid;
		min-height: 300px;
		overflow: hidden;
		border-radius: 8px;
		background: #282828;
		box-shadow: 0 18px 34px rgba(0, 0, 0, 0.35);
	}

	.hero-artwork img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.hero-artwork::after {
		position: absolute;
		inset: 42% 0 0;
		background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.76));
		content: '';
	}

	.loading-hero {
		background: linear-gradient(180deg, rgba(44, 44, 44, 0.72), #121212 82%);
	}

	.hero-artwork-loading::after {
		display: none;
	}

	.skeleton-hero-art {
		width: 100%;
		height: 100%;
		border-radius: 8px;
	}

	.hero-placeholder {
		display: grid;
		place-items: center;
		color: #9b9b9b;
	}

	.hero-play {
		position: absolute;
		right: 16px;
		bottom: 16px;
		z-index: 1;
		display: grid;
		width: 56px;
		height: 56px;
		place-items: center;
		border: 0;
		border-radius: 999px;
		background: #1ed760;
		color: #071108;
		box-shadow: 0 14px 32px rgba(0, 0, 0, 0.34);
		cursor: pointer;
		transition:
			transform 160ms ease,
			background 160ms ease;
	}

	.hero-play:hover {
		background: #3be477;
		transform: translateY(-2px) scale(1.04);
	}

	.hero-copy {
		display: grid;
		align-content: center;
		gap: 14px;
		min-width: 0;
		padding: clamp(6px, 2vw, 20px) 0;
	}

	.hero-copy h1,
	.hero-copy p {
		margin: 0;
	}

	.hero-copy h1 {
		max-width: 900px;
		font-size: clamp(2.8rem, 7vw, 5.6rem);
		line-height: 0.9;
		letter-spacing: 0;
		text-wrap: balance;
	}

	.hero-range {
		display: flex;
		align-items: center;
		flex-wrap: wrap;
		gap: 12px;
		margin-top: 10px;
	}

	.hero-range > span {
		color: #b3b3b3;
		font-weight: 800;
	}

	.skeleton-eyebrow {
		width: 96px;
	}

	.skeleton-hero-title {
		width: min(680px, 100%);
		height: clamp(58px, 8vw, 98px);
		border-radius: 8px;
	}

	.metric-strip,
	.dna-row {
		display: grid;
		grid-template-columns: repeat(4, minmax(0, 1fr));
		gap: 10px;
	}

	.metric-strip article,
	.dna-row article {
		display: grid;
		min-width: 0;
		gap: 6px;
		padding: 14px;
		border-radius: 8px;
		background: #181818;
		transition:
			background 160ms ease,
			transform 160ms ease;
	}

	.metric-strip article:hover,
	.dna-row article:hover {
		background: #222;
		transform: translateY(-1px);
	}

	.metric-icon,
	.dna-icon {
		display: grid;
		width: 30px;
		height: 30px;
		place-items: center;
		border-radius: 999px;
		background: #242424;
		color: #1ed760;
	}

	.skeleton-icon {
		border-radius: 999px;
	}

	.skeleton-label {
		width: 74%;
		height: 10px;
	}

	.skeleton-value {
		width: 62%;
		height: 24px;
	}

	.metric-strip article > span:not(.metric-icon),
	.dna-row article > span:not(.dna-icon) {
		min-width: 0;
		overflow: hidden;
		color: #a7a7a7;
		font-size: 0.78rem;
		font-weight: 800;
		text-overflow: ellipsis;
		text-transform: uppercase;
		white-space: nowrap;
	}

	.metric-strip strong,
	.dna-row strong {
		min-width: 0;
		overflow-wrap: anywhere;
		font-size: clamp(1.2rem, 2vw, 1.65rem);
		line-height: 1.1;
	}

	.recap-studio,
	.dna-section {
		display: grid;
		gap: 12px;
	}

	.section-toolbar {
		display: flex;
		align-items: start;
		flex-direction: column;
		gap: 12px;
	}

	.section-toolbar h2 {
		margin: 0;
		font-size: clamp(1.45rem, 2vw, 1.9rem);
		line-height: 1;
	}

	.skeleton-heading {
		width: 180px;
		height: 28px;
	}

	.skeleton-heading-small {
		width: 78px;
	}

	.control-row {
		display: grid;
		width: 100%;
		grid-template-columns: minmax(0, 1fr) auto;
		align-items: center;
		align-self: start;
		gap: 8px;
		min-width: 0;
	}

	.category-toggle,
	.source-pill {
		display: flex;
		align-items: center;
		gap: 4px;
		width: fit-content;
		padding: 3px;
		border-radius: 999px;
		background: #181818;
	}

	.source-pill {
		justify-self: end;
		min-height: 38px;
		padding-inline: 14px;
		color: #b3b3b3;
		font-weight: 800;
	}

	.skeleton-toggle,
	.skeleton-pill {
		height: 38px;
		border-radius: 999px;
	}

	.skeleton-toggle {
		width: min(280px, 100%);
	}

	.skeleton-pill {
		justify-self: end;
		width: 76px;
	}

	.category-toggle button {
		display: inline-flex;
		min-height: 32px;
		align-items: center;
		justify-content: center;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: #b3b3b3;
		font-weight: 800;
		padding: 0 12px;
		cursor: pointer;
		transition:
			background 160ms ease,
			color 160ms ease;
	}

	.category-toggle button:hover:not(:disabled) {
		color: #fff;
	}

	.category-toggle button.active {
		background: #fff;
		color: #121212;
	}

	.category-toggle button:disabled {
		cursor: not-allowed;
		opacity: 0.42;
	}

	.recap-layout {
		display: grid;
		grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
		gap: 12px;
		align-items: start;
	}

	.ranked-panel {
		display: grid;
		overflow: hidden;
		border-radius: 8px;
		background: #121212;
	}

	.rank-row {
		display: grid;
		grid-template-columns: minmax(0, 1fr) 48px;
		align-items: stretch;
		border-bottom: 1px solid rgba(255, 255, 255, 0.055);
		transition: background 160ms ease;
	}

	.rank-row:last-child {
		border-bottom: 0;
	}

	.rank-row:hover,
	.rank-row.selected {
		background: #232323;
	}

	.rank-row.selected {
		box-shadow: inset 3px 0 0 #1ed760;
	}

	.skeleton-rank-row {
		pointer-events: none;
	}

	.rank-main {
		display: grid;
		grid-template-columns: 42px 48px minmax(150px, 1fr) minmax(110px, 160px);
		align-items: center;
		gap: 14px;
		min-width: 0;
		min-height: 72px;
		padding: 10px 14px 10px 18px;
		border: 0;
		background: transparent;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.skeleton-rank-main {
		cursor: default;
	}

	.rank-number {
		color: #a7a7a7;
		font-weight: 800;
		text-align: center;
	}

	.skeleton-rank-number {
		width: 18px;
		justify-self: center;
	}

	.skeleton-thumb {
		width: 48px;
		height: 48px;
		border-radius: 8px;
	}

	.skeleton-rank-copy {
		width: 100%;
	}

	.skeleton-copy-title {
		width: min(260px, 82%);
	}

	.skeleton-copy-meta {
		width: min(180px, 58%);
	}

	.rank-copy {
		display: grid;
		min-width: 0;
		gap: 4px;
	}

	.rank-copy strong,
	.rank-copy small {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.rank-copy strong {
		color: #fff;
	}

	.rank-copy small,
	.rank-meter small {
		color: #a7a7a7;
	}

	.rank-meter {
		display: grid;
		min-width: 0;
		justify-items: end;
	}

	.skeleton-meter {
		width: 70px;
	}

	.icon-button {
		display: grid;
		width: 48px;
		min-height: 72px;
		place-items: center;
		color: #b3b3b3;
		transition:
			color 160ms ease,
			background 160ms ease;
	}

	.icon-button:hover {
		background: rgba(255, 255, 255, 0.05);
		color: #fff;
	}

	.icon-button.unavailable {
		opacity: 0.25;
	}

	.skeleton-icon-button {
		width: 22px;
		height: 22px;
		border-radius: 999px;
	}

	.detail-panel {
		position: sticky;
		top: 96px;
		display: grid;
		justify-items: start;
		gap: 18px;
		padding: 20px;
		border-radius: 8px;
		background: #181818;
	}

	.skeleton-detail-artwork {
		width: 160px;
		height: 160px;
		border-radius: 16px;
	}

	.skeleton-detail-copy {
		width: 100%;
	}

	.skeleton-detail-title {
		width: min(260px, 84%);
		height: 22px;
	}

	.skeleton-detail-meta {
		width: 44%;
	}

	.detail-copy {
		display: grid;
		gap: 6px;
		min-width: 0;
	}

	.detail-copy h3,
	.detail-copy p {
		margin: 0;
	}

	.detail-copy h3 {
		font-size: clamp(1.35rem, 2vw, 1.85rem);
		line-height: 1.05;
		overflow-wrap: anywhere;
	}

	.detail-copy p {
		color: #b3b3b3;
	}

	dl {
		display: grid;
		width: 100%;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 10px;
		margin: 0;
	}

	dl div {
		display: grid;
		gap: 6px;
		padding: 12px;
		border-radius: 8px;
		background: #121212;
	}

	.skeleton-dt {
		width: 54px;
		height: 9px;
	}

	.skeleton-dd {
		width: 68px;
		height: 18px;
	}

	dt {
		color: #a7a7a7;
		font-size: 0.74rem;
		font-weight: 800;
		text-transform: uppercase;
	}

	dd {
		margin: 0;
		font-size: 1.2rem;
		font-weight: 800;
	}

	.skeleton-link {
		width: 150px;
		height: 42px;
		border-radius: 999px;
	}

	.spotify-link {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		min-height: 42px;
		padding: 0 18px;
		border-radius: 999px;
		background: #1ed760;
		color: #071108;
		font-weight: 900;
		transition:
			background 160ms ease,
			transform 160ms ease;
	}

	.spotify-link:hover {
		background: #3be477;
		transform: translateY(-1px);
	}

	@media (max-width: 1080px) {
		.recap-hero,
		.recap-layout {
			grid-template-columns: 1fr;
		}

		.detail-panel {
			position: static;
		}

		.metric-strip,
		.dna-row {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 760px) {
		.recap-shell {
			padding-top: 0;
		}

		.recap-hero {
			padding: 16px;
		}

		.hero-artwork {
			min-height: 260px;
		}

		.section-toolbar {
			align-items: start;
			flex-direction: column;
		}

		.control-row,
		.category-toggle,
		.source-pill {
			width: 100%;
		}

		.source-pill {
			justify-content: center;
		}

		.category-toggle button {
			flex: 1;
			min-width: 0;
			padding-inline: 10px;
		}

		.rank-row {
			grid-template-columns: minmax(0, 1fr) 44px;
		}

		.rank-main {
			grid-template-columns: 30px 48px minmax(0, 1fr);
			gap: 12px;
			padding-left: 12px;
		}

		.rank-meter {
			grid-column: 3;
			width: 100%;
			justify-items: start;
		}

		.skeleton-meter {
			width: 84px;
		}
	}

	@media (max-width: 560px) {
		.metric-strip,
		.dna-row {
			grid-template-columns: 1fr;
		}

		.hero-copy h1 {
			font-size: clamp(2.55rem, 16vw, 4rem);
		}

		.control-row {
			align-items: stretch;
			grid-template-columns: 1fr;
		}

		.skeleton-toggle,
		.skeleton-pill {
			width: 100%;
		}

		dl {
			grid-template-columns: 1fr;
		}
	}
</style>
