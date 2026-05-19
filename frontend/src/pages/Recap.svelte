<script lang="ts">
	import {
		BarChart3,
		Clock3,
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
	import { albums, artists, dashboardSummary, musicalDna, tracks } from '$lib/data/music';

	type RecapTab = 'tracks' | 'artists' | 'albums';
	type SortMode = 'plays' | 'minutes';

	type RecapItem = {
		id: string;
		imageKind: 'artist' | 'cover';
		imageUrl: string | null;
		imageRound: boolean;
		title: string;
		subtitle: string;
		plays: number;
		minutes: number;
		externalUrl: string | null;
	};

	const numberFormatter = new Intl.NumberFormat('en-US');

	const tabOptions = [
		{ id: 'tracks', label: 'Tracks' },
		{ id: 'artists', label: 'Artists' },
		{ id: 'albums', label: 'Albums' }
	] as const;

	const sortOptions = [
		{ id: 'plays', label: 'Plays' },
		{ id: 'minutes', label: 'Minutes' }
	] as const;

	let activeTab = $state<RecapTab>('tracks');
	let sortMode = $state<SortMode>('plays');
	let selectedId = $state<string | null>(null);

	const topTrack = $derived(tracks[0] ?? null);
	const topArtist = $derived(artists[0] ?? null);
	const totalPlays = $derived(
		dashboardSummary.totalPlays ?? tracks.reduce((sum, track) => sum + track.plays, 0)
	);
	const totalMinutes = $derived(
		dashboardSummary.totalMinutes ??
			tracks.reduce((sum, track) => sum + (track.listeningMinutes ?? 0), 0)
	);
	const uniqueTracks = $derived(dashboardSummary.uniqueTracks ?? tracks.length);
	const resolvedTab = $derived.by(() => resolveTab(activeTab));
	const activeTabItems = $derived.by(() => getItems(resolvedTab));
	const hasMinuteMetrics = $derived(activeTabItems.some((item) => item.minutes > 0));
	const resolvedSortMode = $derived(
		sortMode === 'minutes' && hasMinuteMetrics ? 'minutes' : 'plays'
	);
	const rankedItems = $derived.by(() => rankItems(activeTabItems, resolvedSortMode));
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
	const summaryCards = $derived([
		{
			label: 'Minutes',
			value: formatNumber(totalMinutes),
			icon: Clock3
		},
		{
			label: 'Plays',
			value: formatNumber(totalPlays),
			icon: Headphones
		},
		{
			label: 'Artist',
			value: topArtist?.name ?? dashboardSummary.currentArtist ?? 'No data yet',
			icon: Trophy
		},
		{
			label: 'Tracks',
			value: formatNumber(uniqueTracks),
			icon: ListMusic
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
				plays: artist.plays,
				minutes: artist.listeningMinutes ?? 0,
				externalUrl: artist.externalUrl ?? null
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
				plays: album.plays,
				minutes: album.listeningMinutes ?? 0,
				externalUrl: album.externalUrl ?? null
			}));
		}

		return tracks.map((track, index) => ({
			id: track.spotifyTrackId ?? `track-${track.title}-${track.artist}-${index}`,
			imageKind: 'cover',
			imageUrl: track.coverUrl,
			imageRound: false,
			title: track.title,
			subtitle: track.artist,
			plays: track.plays,
			minutes: track.listeningMinutes ?? 0,
			externalUrl: track.externalUrl ?? null
		}));
	}

	function rankItems(items: RecapItem[], mode: SortMode) {
		return [...items].sort((a, b) => getMetricValue(b, mode) - getMetricValue(a, mode)).slice(0, 6);
	}

	function getMetricValue(item: RecapItem, mode = resolvedSortMode) {
		return mode === 'minutes' ? item.minutes : item.plays;
	}

	function getMetricLabel(item: RecapItem) {
		if (resolvedSortMode === 'minutes') {
			return formatMinutes(item.minutes);
		}

		return `${formatNumber(item.plays)} plays`;
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

	function formatMinutes(value: number | null | undefined) {
		return `${formatNumber(value ?? 0)} min`;
	}
</script>

<section class="recap-shell">
	{#if tracks.length > 0 || artists.length > 0}
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

					<div class="sort-toggle" aria-label="Sort leaderboard">
						{#each sortOptions as option (option.id)}
							<button
								type="button"
								class:active={resolvedSortMode === option.id}
								disabled={option.id === 'minutes' && !hasMinuteMetrics}
								onclick={() => {
									sortMode = option.id;
								}}
							>
								{option.label}
							</button>
						{/each}
					</div>
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
								<dt>Plays</dt>
								<dd>{formatNumber(selectedItem.plays)}</dd>
							</div>
							<div>
								<dt>Minutes</dt>
								<dd>{formatMinutes(selectedItem.minutes)}</dd>
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
	.sort-toggle {
		display: flex;
		align-items: center;
		gap: 4px;
		width: fit-content;
		padding: 3px;
		border-radius: 999px;
		background: #181818;
	}

	.sort-toggle {
		justify-self: end;
	}

	.category-toggle button,
	.sort-toggle button {
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

	.category-toggle button:hover:not(:disabled),
	.sort-toggle button:hover:not(:disabled) {
		color: #fff;
	}

	.category-toggle button.active,
	.sort-toggle button.active {
		background: #fff;
		color: #121212;
	}

	.category-toggle button:disabled,
	.sort-toggle button:disabled {
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

	.rank-number {
		color: #a7a7a7;
		font-weight: 800;
		text-align: center;
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
		.sort-toggle {
			width: 100%;
		}

		.category-toggle button,
		.sort-toggle button {
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

		dl {
			grid-template-columns: 1fr;
		}
	}
</style>
