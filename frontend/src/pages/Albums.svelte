<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { albums } from '$lib/data/music';
</script>

<section class="page-header">
	<SectionHeading title="Top Albums" subtitle="The albums carrying your listening year." />
	<RangeTabs active="6 Months" />
</section>

{#if albums.length > 0}
	<section class="album-grid">
		{#each albums as album (album.title)}
			<article>
				<MediaThumb
					kind="cover"
					src={album.coverUrl}
					alt={`${album.title} album artwork`}
					size="large"
					label={album.title}
				/>
				<div>
					<h2>{album.title}</h2>
					<p>{album.artist}</p>
					<span>{album.plays} plays</span>
				</div>
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
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 24px;
	}

	article {
		display: flex;
		align-items: center;
		gap: 18px;
		padding: 18px;
		border: 1px solid rgba(255, 255, 255, 0.1);
		border-radius: 10px;
		background: #232323;
	}

	article div {
		display: grid;
		gap: 6px;
	}

	h2,
	p {
		margin: 0;
	}

	h2 {
		font-size: 1.08rem;
	}

	p,
	span {
		color: #c8ceca;
	}

	span {
		font-size: 0.88rem;
		text-transform: uppercase;
	}

	@media (max-width: 980px) {
		.album-grid {
			grid-template-columns: repeat(2, minmax(0, 1fr));
		}
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
