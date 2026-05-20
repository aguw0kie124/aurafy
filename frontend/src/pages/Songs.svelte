<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { rangeOptions, tracks, type StatsRangeValue } from '$lib/data/music';

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
	const skeletonCards = Array.from({ length: 10 }, (_, index) => index);

	const activeRangeLabel = $derived(
		rangeOptions.find((option) => option.value === activeRange)?.label ?? '4 Weeks'
	);

	function getTrackId(track: (typeof tracks)[number], index: number) {
		return track.spotifyTrackId ?? `${track.title}-${track.artist}-${index}`;
	}

	function getTrackMetric(track: (typeof tracks)[number]) {
		if (track.spotifyRank) {
			return `#${track.spotifyRank}`;
		}

		return 'Spotify';
	}
</script>

<section class="page-header">
	<SectionHeading title="Top Tracks" subtitle={`Spotify: ${activeRangeLabel}.`} />
	<RangeTabs active={activeRange} onSelect={onRangeChange} />
</section>

{#if loading}
	<section class="song-grid" aria-hidden="true">
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
{:else if tracks.length > 0}
	<section class="song-grid">
		{#each tracks as track, index (getTrackId(track, index))}
			{@const trackId = getTrackId(track, index)}
			<article class:selected={selectedId === trackId}>
				<button
					type="button"
					class="card-main"
					aria-pressed={selectedId === trackId}
					onclick={() => {
						selectedId = trackId;
					}}
				>
					<MediaThumb
						kind="cover"
						src={track.coverUrl}
						alt={`${track.album} album artwork`}
						size="large"
						label={track.title}
					/>
					<span class="card-copy">
						<strong>{track.title}</strong>
						<small>{track.artist}</small>
						<em>{getTrackMetric(track)}</em>
					</span>
				</button>

				{#if track.externalUrl}
					<a
						class="spotify-open"
						href={track.externalUrl}
						target="_blank"
						rel="noreferrer noopener"
						aria-label={`Open ${track.title} in Spotify`}
					>
						<ExternalLink size={17} strokeWidth={2.2} />
					</a>
				{/if}
			</article>
		{/each}
	</section>
{:else}
	<EmptyState title="No track data yet" />
{/if}

<style>
	.page-header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 24px;
		margin-bottom: 34px;
	}

	.song-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
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
		display: grid;
		gap: 14px;
		min-width: 0;
		padding: 16px;
		border: 0;
		background: transparent;
		color: inherit;
		text-align: left;
		cursor: pointer;
	}

	.skeleton-card {
		gap: 14px;
		padding: 16px;
		pointer-events: none;
	}

	.skeleton-artwork {
		width: 100%;
		aspect-ratio: 1;
		border-radius: 16px;
	}

	.skeleton-copy {
		display: grid;
		gap: 8px;
	}

	.skeleton-title {
		width: 82%;
	}

	.skeleton-meta {
		width: 64%;
	}

	.skeleton-rank {
		width: 42%;
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

		.song-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 520px) {
		.song-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
