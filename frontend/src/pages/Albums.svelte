<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { albums, rangeOptions, type StatsRangeValue } from '$lib/data/music';

	let {
		activeRange = 'short_term',
		onRangeChange = () => {},
		loading = false
	}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
		loading?: boolean;
	} = $props();

	let selectedId = $state<string | null>(null);
	const skeletonCards = Array.from({ length: 8 }, (_, index) => index);

	const activeRangeLabel = $derived(
		rangeOptions.find((option) => option.value === activeRange)?.label ?? '4 Weeks'
	);

	function getAlbumId(album: (typeof albums)[number], index: number) {
		return album.spotifyAlbumId ?? `${album.title}-${album.artist}-${index}`;
	}

	function getAlbumMetric(album: (typeof albums)[number]) {
		if (album.topTrackCount) {
			const trackLabel = album.topTrackCount === 1 ? 'top track' : 'top tracks';
			return `#${album.spotifyRank ?? '-'} • ${album.topTrackCount} ${trackLabel}`;
		}

		return album.spotifyRank ? `#${album.spotifyRank}` : 'Spotify';
	}
</script>

<section class="page-header">
	<SectionHeading
		title="Top Albums"
		subtitle={`Derived from Spotify top tracks: ${activeRangeLabel}.`}
	/>
	<RangeTabs active={activeRange} onSelect={onRangeChange} />
</section>

{#if loading}
	<section class="album-grid" aria-hidden="true">
		{#each skeletonCards as item (item)}
			<article class="skeleton-card">
				<span class="skeleton skeleton-artwork"></span>
				<span class="skeleton-copy">
					<span class="skeleton skeleton-line skeleton-title"></span>
					<span class="skeleton skeleton-line skeleton-meta"></span>
					<span class="skeleton skeleton-line skeleton-rank"></span>
				</span>
			</article>
		{/each}
	</section>
{:else if albums.length > 0}
	<section class="album-grid">
		{#each albums as album, index (getAlbumId(album, index))}
			{@const albumId = getAlbumId(album, index)}
			<article class:selected={selectedId === albumId}>
				<button
					type="button"
					class="card-main"
					aria-pressed={selectedId === albumId}
					onclick={() => {
						selectedId = albumId;
					}}
				>
					<MediaThumb
						kind="cover"
						src={album.coverUrl}
						alt={`${album.title} album artwork`}
						size="large"
						label={album.title}
					/>
					<span class="card-copy">
						<strong>{album.title}</strong>
						<small>{album.artist}</small>
						<em>{getAlbumMetric(album)}</em>
					</span>
				</button>

				{#if album.externalUrl}
					<a
						class="spotify-open"
						href={album.externalUrl}
						target="_blank"
						rel="noreferrer noopener"
						aria-label={`Open ${album.title} in Spotify`}
					>
						<ExternalLink size={17} strokeWidth={2.2} />
					</a>
				{/if}
			</article>
		{/each}
	</section>
{:else}
	<EmptyState title="No album data yet" />
{/if}

<style>
	.page-header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 24px;
		margin-bottom: 34px;
	}

	.album-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
		gap: 16px;
	}

	article {
		position: relative;
		display: grid;
		border-radius: 8px;
		background: #181818;
		transition: background 160ms ease;
	}

	article:hover,
	article.selected {
		background: #242424;
	}

	article.selected {
		box-shadow: inset 0 0 0 1px rgba(30, 215, 96, 0.55);
	}

	.card-main {
		display: flex;
		align-items: center;
		gap: 16px;
		min-width: 0;
		padding: 16px;
		border: 0;
		background: transparent;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.skeleton-card {
		display: flex;
		align-items: center;
		gap: 16px;
		padding: 16px;
		pointer-events: none;
	}

	.skeleton-artwork {
		flex: 0 0 clamp(96px, 32%, 160px);
		aspect-ratio: 1;
		border-radius: 16px;
	}

	.skeleton-copy {
		display: grid;
		flex: 1 1 auto;
		gap: 8px;
		min-width: 0;
	}

	.skeleton-title {
		width: 82%;
	}

	.skeleton-meta {
		width: 58%;
	}

	.skeleton-rank {
		width: 48%;
	}

	.card-copy {
		display: grid;
		min-width: 0;
		gap: 5px;
	}

	.card-copy strong,
	.card-copy small,
	.card-copy em {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-copy strong {
		font-size: 1rem;
	}

	.card-copy small,
	.card-copy em {
		color: #a7a7a7;
	}

	.card-copy em {
		font-style: normal;
		font-weight: 800;
		text-transform: uppercase;
	}

	.spotify-open {
		position: absolute;
		right: 10px;
		top: 10px;
		display: grid;
		width: 34px;
		height: 34px;
		place-items: center;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.42);
		color: #fff;
		opacity: 0;
		transition:
			opacity 160ms ease,
			background 160ms ease;
	}

	article:hover .spotify-open,
	article.selected .spotify-open,
	.spotify-open:focus-visible {
		opacity: 1;
	}

	.spotify-open:hover {
		background: #1ed760;
		color: #071108;
	}

	@media (max-width: 760px) {
		.page-header {
			align-items: start;
			flex-direction: column;
		}

		.album-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
