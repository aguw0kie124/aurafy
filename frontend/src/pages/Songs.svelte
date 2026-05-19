<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { tracks } from '$lib/data/music';
</script>

<section class="page-header">
	<SectionHeading title="Top Tracks" subtitle="Your most played songs over the last 4 weeks." />
	<RangeTabs />
</section>

{#if tracks.length > 0}
	<section class="track-table">
		<header>
			<span>#</span>
			<span>Title</span>
			<span>Album</span>
			<span>Plays</span>
		</header>

		<ol>
			{#each tracks as track, index (track.spotifyTrackId ?? track.title)}
				<li>
					<em>{index + 1}</em>
					<div class="title-cell">
						<MediaThumb
							kind="cover"
							src={track.coverUrl}
							alt={`${track.album} album artwork`}
							size="small"
							label={track.title}
						/>
						<div>
							<strong>{track.title}</strong>
							<span>{track.artist}</span>
						</div>
					</div>
					<span>{track.album}</span>
					<strong>{track.plays}</strong>
				</li>
			{/each}
		</ol>
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

	.track-table {
		overflow: hidden;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 10px;
		background: #141414;
	}

	.track-table > header,
	li {
		display: grid;
		grid-template-columns: 64px minmax(260px, 1.2fr) minmax(220px, 1fr) 72px;
		align-items: center;
		gap: 18px;
	}

	.track-table > header {
		min-height: 58px;
		padding: 0 28px;
		border-bottom: 1px solid rgba(255, 255, 255, 0.12);
		color: #c5cbc7;
		font-size: 0.8rem;
		text-transform: uppercase;
	}

	.track-table > header span:last-child,
	li > strong {
		text-align: right;
	}

	ol {
		margin: 0;
		padding: 0;
		list-style: none;
	}

	li {
		min-height: 94px;
		padding: 0 28px;
	}

	li + li {
		border-top: 1px solid rgba(255, 255, 255, 0.04);
	}

	em {
		color: #71ef9d;
		font-size: 1.8rem;
		font-style: normal;
		font-weight: 700;
	}

	.title-cell {
		display: flex;
		align-items: center;
		gap: 18px;
	}

	.title-cell div {
		display: grid;
		gap: 4px;
	}

	.title-cell span,
	li > span {
		color: #d0d5d1;
	}

	@media (max-width: 760px) {
		.page-header {
			align-items: start;
			flex-direction: column;
		}

		.track-table > header {
			display: none;
		}

		li {
			grid-template-columns: 38px 1fr;
			gap: 14px;
			padding: 18px;
		}

		li > span,
		li > strong {
			grid-column: 2;
			text-align: left;
		}
	}
</style>
