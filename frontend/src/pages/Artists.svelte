<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { artists, rangeOptions, type StatsRangeValue } from '$lib/data/music';

	let {
		activeRange = 'short_term',
		onRangeChange = () => {}
	}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
	} = $props();

	let selectedId = $state<string | null>(null);

	const activeRangeLabel = $derived(
		rangeOptions.find((option) => option.value === activeRange)?.label ?? '4 Weeks'
	);

	function getArtistId(artist: (typeof artists)[number], index: number) {
		return artist.spotifyArtistId ?? `${artist.name}-${index}`;
	}

	function getArtistMetric(artist: (typeof artists)[number]) {
		return artist.spotifyRank ? `#${artist.spotifyRank}` : 'Spotify';
	}
</script>

<section class="page-header">
	<SectionHeading title="Top Artists" subtitle={`Spotify: ${activeRangeLabel}.`} />
	<RangeTabs active={activeRange} onSelect={onRangeChange} />
</section>

{#if artists.length > 0}
	<section class="artist-grid">
		{#each artists as artist, index (getArtistId(artist, index))}
			{@const artistId = getArtistId(artist, index)}
			<article class:selected={selectedId === artistId}>
				<button
					type="button"
					class="card-main"
					aria-pressed={selectedId === artistId}
					onclick={() => {
						selectedId = artistId;
					}}
				>
					<MediaThumb
						kind="artist"
						src={artist.imageUrl}
						alt={`${artist.name} artist image`}
						size="large"
						round
						label={artist.name}
					/>
					<span class="card-copy">
						<strong>{artist.name}</strong>
						<small>{getArtistMetric(artist)}</small>
					</span>
				</button>

				{#if artist.externalUrl}
					<a
						class="spotify-open"
						href={artist.externalUrl}
						target="_blank"
						rel="noreferrer noopener"
						aria-label={`Open ${artist.name} in Spotify`}
					>
						<ExternalLink size={17} strokeWidth={2.2} />
					</a>
				{/if}
			</article>
		{/each}
	</section>
{:else}
	<EmptyState title="No artist data yet" />
{/if}

<style>
	.page-header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 24px;
		margin-bottom: 34px;
	}

	.artist-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
		gap: 16px;
	}

	article {
		position: relative;
		display: grid;
		border-radius: 8px;
		background: #181818;
		transition:
			background 160ms ease,
			transform 160ms ease;
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
		justify-items: center;
		min-width: 0;
		padding: 18px;
		border: 0;
		background: transparent;
		color: inherit;
		text-align: center;
		cursor: pointer;
	}

	.card-copy {
		display: grid;
		min-width: 0;
		gap: 5px;
		width: 100%;
	}

	.card-copy strong,
	.card-copy small {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-copy strong {
		font-size: 1rem;
	}

	.card-copy small {
		color: #a7a7a7;
		font-weight: 700;
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

		.artist-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
	}

	@media (max-width: 520px) {
		.artist-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
