<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import { artists, dashboardSummary, tasteProfile, tracks } from '$lib/data/music';

	const summaryCards = [
		{
			label: 'Total minutes',
			value: dashboardSummary.totalMinutes?.toLocaleString() ?? null
		},
		{
			label: 'Artists discovered',
			value: dashboardSummary.artistsDiscovered?.toLocaleString() ?? null
		},
		{
			label: 'Top genre',
			value: dashboardSummary.topGenre
		}
	];
</script>

<section class="overview-card">
	<div class="hero-art">
		{#if dashboardSummary.currentArtistImageUrl && dashboardSummary.currentArtist}
			<img
				src={dashboardSummary.currentArtistImageUrl}
				alt={`${dashboardSummary.currentArtist} artist artwork`}
			/>
		{:else}
			<div class="hero-placeholder">
				<span>No artist data yet</span>
			</div>
		{/if}

		{#if dashboardSummary.currentArtist}
			<div class="hero-overlay">
				{#if dashboardSummary.currentRank !== null}
					<span>Current #{dashboardSummary.currentRank}</span>
				{/if}
				<strong>{dashboardSummary.currentArtist}</strong>
			</div>
		{/if}
	</div>

	<div class="overview-copy">
		<div>
			<h1>Overview</h1>
			<p>Your listening overview appears here once data is available.</p>
		</div>

		<div class="overview-actions">
			<button type="button" disabled={tracks.length === 0}>Play Top Tracks</button>
			<a href="/recap">View Full Report</a>
		</div>

		<div class="summary-grid">
			{#each summaryCards as card (card.label)}
				<article>
					<span>{card.label}</span>
					<strong>{card.value ?? 'No data yet'}</strong>
				</article>
			{/each}
		</div>
	</div>
</section>

<section class="split-grid">
	<article class="panel">
		<header>
			<h2>Top Artists</h2>
			<span>4 Weeks</span>
		</header>

		{#if artists.length > 0}
			<ol class="artist-list">
				{#each artists.slice(0, 3) as artist, index (artist.name)}
					<li>
						<em>{index + 1}</em>
						<MediaThumb
							kind="artist"
							src={artist.imageUrl}
							alt={`${artist.name} artist image`}
							size="medium"
							round
							label={artist.name}
						/>
						<strong>{artist.name}</strong>
					</li>
				{/each}
			</ol>
		{:else}
			<EmptyState title="No artist data yet" compact />
		{/if}
	</article>

	<article class="panel">
		<header>
			<h2>Top Tracks</h2>
			<span>4 Weeks</span>
		</header>

		{#if tracks.length > 0}
			<ul class="track-preview">
				{#each tracks.slice(0, 3) as track (track.title)}
					<li>
						<MediaThumb
							kind="cover"
							src={track.coverUrl}
							alt={`${track.album} album artwork`}
							size="medium"
							label={track.title}
						/>
						<div>
							<strong>{track.title}</strong>
							<span>{track.artist}</span>
						</div>
						<em>{track.plays}</em>
					</li>
				{/each}
			</ul>
		{:else}
			<EmptyState title="No track data yet" compact />
		{/if}
	</article>
</section>

<section class="panel taste-panel">
	<h2>Taste Profile</h2>

	{#if tasteProfile.length > 0}
		<div class="taste-list">
			{#each tasteProfile as item (item.label)}
				<div>
					<header>
						<span>{item.label}</span>
						<strong>{item.value}%</strong>
					</header>
					<div class="meter">
						<span style={`width: ${item.value}%`}></span>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<EmptyState title="No taste profile yet" compact />
	{/if}
</section>

<style>
	.overview-card {
		display: grid;
		grid-template-columns: minmax(320px, 410px) minmax(0, 1fr);
		gap: 38px;
		padding: 20px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 10px;
		background: #232323;
	}

	.hero-art {
		position: relative;
		min-height: 380px;
		overflow: hidden;
		border-radius: 8px;
	}

	.hero-art img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	.hero-placeholder {
		display: grid;
		height: 100%;
		min-height: 380px;
		place-items: center;
		background: linear-gradient(135deg, rgba(113, 239, 157, 0.12), transparent 45%), #1b1d1c;
		color: #9fa7a2;
	}

	.hero-art::after {
		position: absolute;
		inset: 38% 0 0;
		background: linear-gradient(180deg, transparent, rgba(7, 10, 9, 0.9));
		content: '';
	}

	.hero-overlay {
		position: absolute;
		right: 18px;
		bottom: 18px;
		left: 18px;
		z-index: 1;
		display: grid;
		gap: 12px;
	}

	.hero-overlay span {
		width: fit-content;
		border-radius: 999px;
		background: #16c878;
		color: #041108;
		font-weight: 800;
		padding: 8px 14px;
		text-transform: uppercase;
	}

	.hero-overlay strong {
		font-size: clamp(1.7rem, 3vw, 2.3rem);
	}

	.overview-copy {
		display: grid;
		align-content: center;
		gap: 28px;
	}

	.overview-copy h1,
	.overview-copy p {
		margin: 0;
	}

	.overview-copy h1 {
		font-size: clamp(2.6rem, 5vw, 4.3rem);
		line-height: 0.94;
	}

	.overview-copy p {
		margin-top: 12px;
		color: #d1d6d2;
		font-size: 1rem;
	}

	.overview-actions {
		display: flex;
		gap: 16px;
	}

	.overview-actions button,
	.overview-actions a {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		min-height: 46px;
		border-radius: 999px;
		font-weight: 700;
		padding: 0 28px;
	}

	.overview-actions button {
		border: 0;
		background: #16c878;
		color: #041108;
		cursor: pointer;
	}

	.overview-actions button:disabled {
		cursor: not-allowed;
		opacity: 0.45;
	}

	.overview-actions a {
		border: 1px solid rgba(255, 255, 255, 0.48);
	}

	.summary-grid {
		display: grid;
		grid-template-columns: repeat(3, minmax(0, 1fr));
		gap: 18px;
	}

	.summary-grid article {
		display: grid;
		gap: 8px;
		min-height: 92px;
		padding: 18px 20px;
		border: 1px solid rgba(255, 255, 255, 0.16);
		border-radius: 6px;
	}

	.summary-grid span {
		color: #c7ccc8;
		font-size: 0.8rem;
		text-transform: uppercase;
	}

	.summary-grid strong {
		color: #71ef9d;
		font-size: 1.35rem;
		line-height: 1.2;
	}

	.split-grid {
		display: grid;
		grid-template-columns: repeat(2, minmax(0, 1fr));
		gap: 24px;
		margin-top: 28px;
	}

	.panel {
		padding: 22px;
		border: 1px solid rgba(255, 255, 255, 0.12);
		border-radius: 10px;
		background: #242424;
	}

	.panel > header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 24px;
	}

	.panel h2 {
		margin: 0;
		font-size: 1.45rem;
	}

	.panel > header span {
		color: #c8ceca;
		font-size: 0.85rem;
		text-transform: uppercase;
	}

	.artist-list,
	.track-preview {
		display: grid;
		gap: 18px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.artist-list li {
		display: grid;
		grid-template-columns: 24px 72px 1fr;
		align-items: center;
		gap: 18px;
	}

	.artist-list em {
		color: #d4dad5;
		font-style: normal;
	}

	.track-preview li {
		display: grid;
		grid-template-columns: 72px 1fr auto;
		align-items: center;
		gap: 18px;
	}

	.track-preview div {
		display: grid;
		gap: 6px;
	}

	.track-preview span {
		color: #d0d5d1;
	}

	.track-preview em {
		color: #e6ebe8;
		font-style: normal;
	}

	.taste-panel {
		margin-top: 28px;
	}

	.taste-panel h2 {
		margin-bottom: 22px;
	}

	.taste-list {
		display: grid;
		gap: 22px;
	}

	.taste-list header {
		display: flex;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 12px;
		text-transform: uppercase;
	}

	.taste-list strong {
		color: #71ef9d;
	}

	.meter {
		height: 10px;
		overflow: hidden;
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.12);
	}

	.meter span {
		display: block;
		height: 100%;
		border-radius: inherit;
		background: #69eb98;
	}

	@media (max-width: 980px) {
		.overview-card {
			grid-template-columns: 1fr;
		}

		.hero-art {
			min-height: 320px;
		}

		.summary-grid,
		.split-grid {
			grid-template-columns: 1fr;
		}
	}

	@media (max-width: 620px) {
		.overview-card {
			padding: 16px;
		}

		.overview-actions {
			flex-direction: column;
		}

		.summary-grid {
			gap: 12px;
		}
	}
</style>
