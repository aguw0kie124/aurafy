<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { artists } from '$lib/data/music';
</script>

<section class="page-header">
	<SectionHeading
		title="Top Artists"
		subtitle="Your most played artists across all listening sessions."
	/>
	<RangeTabs active="6 Months" />
</section>

{#if artists.length > 0}
	<section class="artist-grid">
		{#each artists as artist (artist.name)}
			<article>
				<MediaThumb
					kind="artist"
					src={artist.imageUrl}
					alt={`${artist.name} artist image`}
					size="large"
					round
					label={artist.name}
				/>
				<h2>{artist.name}</h2>
				<p>{artist.plays} Plays</p>
			</article>
		{/each}
	</section>

	<button class="load-more" type="button">Load More Artists</button>
{:else}
	<EmptyState title="No artist data yet" />
{/if}

<style>
	.page-header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 24px;
		margin-bottom: 42px;
	}

	.artist-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 42px 32px;
	}

	article {
		display: grid;
		justify-items: center;
		gap: 12px;
		text-align: center;
	}

	h2,
	p {
		margin: 0;
	}

	h2 {
		font-size: 1.08rem;
	}

	p {
		color: #c8ceca;
		font-size: 0.88rem;
		text-transform: uppercase;
	}

	.load-more {
		display: block;
		min-width: 210px;
		min-height: 48px;
		margin: 54px auto 0;
		border: 1px solid rgba(255, 255, 255, 0.22);
		border-radius: 999px;
		background: transparent;
		color: #f3f5f4;
		font-weight: 700;
		cursor: pointer;
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
