<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import { artists, dashboardSummary, genres, musicalDna, tracks } from '$lib/data/music';
</script>

<section class="recap-shell">
	<div class="recap-header">
		<p class="eyebrow">Recap</p>
		<h1>Listening recap</h1>
	</div>

	{#if tracks.length > 0 || artists.length > 0 || genres.length > 0}
		<section class="recap-grid">
			<article>
				<span>Total minutes</span>
				<strong>{dashboardSummary.totalMinutes?.toLocaleString() ?? '0'}</strong>
			</article>
			<article>
				<span>Total plays</span>
				<strong>{dashboardSummary.totalPlays?.toLocaleString() ?? '0'}</strong>
			</article>
			<article>
				<span>Top genre</span>
				<strong>{dashboardSummary.topGenre ?? 'No genre yet'}</strong>
			</article>
		</section>

		<section class="recap-section">
			<h2>Top songs</h2>
			<div class="ranked-list">
				{#each tracks.slice(0, 5) as track, index (track.spotifyTrackId ?? track.title)}
					<div>
						<em>{index + 1}</em>
						<MediaThumb
							kind="cover"
							src={track.coverUrl}
							alt={`${track.album} album artwork`}
							size="small"
							label={track.title}
						/>
						<span>
							<strong>{track.title}</strong>
							<small>{track.artist}</small>
						</span>
					</div>
				{/each}
			</div>
		</section>

		<section class="recap-section">
			<h2>Musical DNA</h2>
			<div class="dna-row">
				{#each musicalDna as item (item.label)}
					<article>
						<span>{item.label}</span>
						<strong>{item.value}</strong>
					</article>
				{/each}
			</div>
		</section>
	{:else}
		<EmptyState title="No recap data yet" />
	{/if}
</section>

<style>
	.recap-shell {
		display: grid;
		gap: 28px;
		padding: 28px 0 32px;
	}

	.recap-header h1 {
		margin: 8px 0 0;
		font-size: clamp(2rem, 4vw, 3.2rem);
	}

	.recap-grid,
	.dna-row {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 18px;
	}

	.recap-grid article,
	.dna-row article {
		display: grid;
		gap: 8px;
		padding: 22px;
		border-radius: 10px;
		background: #252525;
	}

	.recap-grid span,
	.dna-row span {
		color: #c8ceca;
		font-size: 0.82rem;
		font-weight: 700;
		text-transform: uppercase;
	}

	.recap-grid strong,
	.dna-row strong {
		font-size: 1.45rem;
	}

	.recap-section {
		display: grid;
		gap: 18px;
	}

	.recap-section h2 {
		margin: 0;
		font-size: 1.45rem;
	}

	.ranked-list {
		display: grid;
		overflow: hidden;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 10px;
		background: #141414;
	}

	.ranked-list > div {
		display: grid;
		grid-template-columns: 42px auto 1fr;
		align-items: center;
		gap: 16px;
		min-height: 74px;
		padding: 12px 18px;
	}

	.ranked-list > div + div {
		border-top: 1px solid rgba(255, 255, 255, 0.06);
	}

	em {
		color: #71ef9d;
		font-style: normal;
		font-weight: 800;
	}

	.ranked-list span {
		display: grid;
		gap: 4px;
	}

	small {
		color: #c8ceca;
	}

	@media (max-width: 760px) {
		.recap-grid,
		.dna-row {
			grid-template-columns: 1fr;
		}
	}
</style>
