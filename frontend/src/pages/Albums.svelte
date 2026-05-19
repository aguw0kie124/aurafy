<script lang="ts">
	import { ExternalLink } from '@lucide/svelte';
	import EmptyState from '$lib/components/EmptyState.svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import RangeTabs from '$lib/components/RangeTabs.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import { albums } from '$lib/data/music';

	let selectedId = $state<string | null>(null);

	const selectedAlbum = $derived(
		albums.find((album, index) => getAlbumId(album, index) === selectedId) ?? albums[0] ?? null
	);

	function getAlbumId(album: (typeof albums)[number], index: number) {
		return album.spotifyAlbumId ?? `${album.title}-${album.artist}-${index}`;
	}

	function formatNumber(value: number | null | undefined) {
		return (value ?? 0).toLocaleString();
	}

	function formatMinutes(value: number | null | undefined) {
		return `${formatNumber(value)} min`;
	}
</script>

<section class="page-header">
	<SectionHeading title="Top Albums" subtitle="The albums carrying your listening year." />
	<RangeTabs active="6 Months" />
</section>

{#if albums.length > 0}
	<section class="list-layout">
		<div class="ranked-panel" aria-label="Ranked album list">
			{#each albums as album, index (getAlbumId(album, index))}
				{@const albumId = getAlbumId(album, index)}
				<div class="rank-row" class:selected={selectedAlbum === album}>
					<button
						type="button"
						class="rank-main"
						aria-pressed={selectedAlbum === album}
						onclick={() => {
							selectedId = albumId;
						}}
					>
						<span class="rank-number">{index + 1}</span>
						<MediaThumb
							kind="cover"
							src={album.coverUrl}
							alt={`${album.title} album artwork`}
							size="small"
							label={album.title}
						/>
						<span class="rank-copy">
							<strong>{album.title}</strong>
							<small>{album.artist}</small>
						</span>
						<span class="rank-meta">{formatNumber(album.plays)} plays</span>
					</button>

					{#if album.externalUrl}
						<a
							class="icon-button"
							href={album.externalUrl}
							target="_blank"
							rel="noreferrer noopener"
							aria-label={`Open ${album.title} in Spotify`}
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

		<aside class="detail-panel" aria-label="Selected album">
			{#if selectedAlbum}
				<MediaThumb
					kind="cover"
					src={selectedAlbum.coverUrl}
					alt={`${selectedAlbum.title} album artwork`}
					size="large"
					label={selectedAlbum.title}
				/>
				<div class="detail-copy">
					<h2>{selectedAlbum.title}</h2>
					<p>{selectedAlbum.artist}</p>
				</div>

				<dl>
					<div>
						<dt>Plays</dt>
						<dd>{formatNumber(selectedAlbum.plays)}</dd>
					</div>
					<div>
						<dt>Minutes</dt>
						<dd>{formatMinutes(selectedAlbum.listeningMinutes)}</dd>
					</div>
				</dl>

				{#if selectedAlbum.externalUrl}
					<a
						class="spotify-link"
						href={selectedAlbum.externalUrl}
						target="_blank"
						rel="noreferrer noopener"
					>
						Open in Spotify
						<ExternalLink size={17} strokeWidth={2.3} />
					</a>
				{/if}
			{/if}
		</aside>
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

	.list-layout {
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
		grid-template-columns: 42px 48px minmax(150px, 1fr) minmax(100px, 150px);
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
	.rank-copy small,
	.rank-meta {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.rank-copy small,
	.rank-meta {
		color: #a7a7a7;
	}

	.rank-meta {
		justify-self: end;
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

	.detail-copy h2,
	.detail-copy p {
		margin: 0;
	}

	.detail-copy h2 {
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

	@media (max-width: 980px) {
		.list-layout {
			grid-template-columns: 1fr;
		}

		.detail-panel {
			position: static;
		}
	}

	@media (max-width: 760px) {
		.page-header {
			align-items: start;
			flex-direction: column;
		}

		.rank-row {
			grid-template-columns: minmax(0, 1fr) 44px;
		}

		.rank-main {
			grid-template-columns: 30px 48px minmax(0, 1fr);
			gap: 12px;
			padding-left: 12px;
		}

		.rank-meta {
			grid-column: 3;
			justify-self: start;
		}
	}
</style>
