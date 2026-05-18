<script lang="ts">
	import { Activity, Gauge, Smile } from '@lucide/svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { genres, musicalDna } from '$lib/data/music';

	const iconMap = {
		bolt: Activity,
		tempo: Gauge,
		mood: Smile
	};
</script>

<section class="genres-shell">
	<SectionHeading
		title="Your Top Genres"
		subtitle="A breakdown of your listening habits appears here once data is available."
	/>

	{#if genres.length > 0}
		<div class="genre-panel">
			{#each genres as genre, index (genre.label)}
				<div class="genre-row">
					<em>{index + 1}</em>
					<div>
						<header>
							<strong>{genre.label}</strong>
							<span>{genre.value}%</span>
						</header>
						<div class="meter">
							<span style={`width: ${genre.value}%`}></span>
						</div>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="section-gap">
			<EmptyState title="No genre data yet" />
		</div>
	{/if}

	<section class="dna-section">
		<h2>Musical DNA</h2>

		{#if musicalDna.length > 0}
			<div class="dna-grid">
				{#each musicalDna as item (item.label)}
					{@const Icon = iconMap[item.glyph]}
					<article>
						<Icon size={28} strokeWidth={2.2} />
						<span>{item.label}</span>
						<strong>{item.value}</strong>
					</article>
				{/each}
			</div>
		{:else}
			<EmptyState title="No musical DNA yet" compact />
		{/if}
	</section>
</section>

<style>
	.genres-shell {
		width: min(1000px, 100%);
		margin: 0 auto;
	}

	.section-gap {
		margin-top: 48px;
	}

	.genre-panel {
		display: grid;
		gap: 24px;
		margin-top: 48px;
		padding: 28px 32px;
		border-radius: 10px;
		background: #252525;
	}

	.genre-row {
		display: grid;
		grid-template-columns: 18px 1fr;
		gap: 18px;
		align-items: center;
	}

	.genre-row em {
		color: #d5dad7;
		font-style: normal;
	}

	.genre-row header {
		display: flex;
		justify-content: space-between;
		gap: 18px;
		margin-bottom: 12px;
	}

	.genre-row span {
		color: #d0d5d1;
	}

	.meter {
		height: 10px;
		overflow: hidden;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.08);
	}

	.meter span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: #18c878;
	}

	.dna-section {
		margin-top: 72px;
	}

	.dna-section h2 {
		margin: 0 0 28px;
		font-size: 1.7rem;
	}

	.dna-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 22px;
	}

	article {
		display: grid;
		justify-items: center;
		gap: 10px;
		padding: 28px 18px;
		border-radius: 10px;
		background: #252525;
		text-align: center;
	}

	article :global(svg) {
		color: #16c878;
	}

	article span {
		color: #c8ceca;
		font-size: 0.8rem;
		font-weight: 700;
		text-transform: uppercase;
	}

	article strong {
		font-size: 1.5rem;
	}

	@media (max-width: 700px) {
		.genre-panel {
			padding: 22px;
		}

		.dna-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
