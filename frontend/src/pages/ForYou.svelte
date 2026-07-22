<script lang="ts">
	import { onMount } from 'svelte';
	import { Sparkles, ExternalLink, RefreshCw } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import PlaylistModal from '$lib/components/PlaylistModal.svelte';
	import {
		recommendations,
		previewPlaylist,
		type Recommendations,
		type RecPlaylist,
		type ProposedPlaylist,
		type StatsRangeValue
	} from '$lib/data/music';

	// Page contract props (unused here, but App passes them to every page).
	let {}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
		loading?: boolean;
	} = $props();

	const lengthOptions = [10, 15, 25, 40, 50];

	let instruction = $state('');
	let length = $state(25);
	let describeError = $state('');

	let feed = $state<Recommendations | null>(null);
	let feedStatus = $state<'loading' | 'ready' | 'error'>('loading');
	let refreshing = $state(false);

	let modalOpen = $state(false);
	let modalLoading = $state(false);
	let modalPlaylist = $state<ProposedPlaylist | RecPlaylist | null>(null);

	const rowSkeletons = Array.from({ length: 3 }, (_, i) => i);
	const cardSkeletons = Array.from({ length: 6 }, (_, i) => i);

	onMount(loadFeed);

	async function loadFeed(refresh = false) {
		// On refresh keep the current feed visible and just spin the button; only the
		// first (cold) load shows the full skeletons.
		if (refresh) refreshing = true;
		else feedStatus = 'loading';
		try {
			feed = await recommendations(refresh);
			feedStatus = 'ready';
		} catch {
			if (!refresh) feedStatus = 'error';
		} finally {
			refreshing = false;
		}
	}

	async function describe() {
		const text = instruction.trim();
		if (!text) return;
		describeError = '';
		modalPlaylist = null;
		modalLoading = true;
		modalOpen = true;
		try {
			modalPlaylist = await previewPlaylist({ mode: 'instruction', instruction: text, length });
		} catch (error) {
			modalOpen = false;
			describeError = error instanceof Error ? error.message : 'Could not build a playlist.';
		} finally {
			modalLoading = false;
		}
	}

	function openPlaylist(playlist: RecPlaylist) {
		describeError = '';
		modalPlaylist = playlist;
		modalLoading = false;
		modalOpen = true;
	}
</script>

<section class="page-header">
	<SectionHeading title="For You" subtitle="New music, picked from what you love." />
	<button
		type="button"
		class="refresh"
		onclick={() => loadFeed(true)}
		disabled={refreshing || feedStatus === 'loading'}
		title="Rebuild your feed with fresh picks"
	>
		<RefreshCw size={16} strokeWidth={2.2} class={refreshing ? 'spin' : undefined} />
		{refreshing ? 'Refreshing…' : 'Refresh'}
	</button>
</section>

<!-- AI describe bar -->
<form
	class="describe"
	onsubmit={(event) => {
		event.preventDefault();
		describe();
	}}
>
	<div class="describe-field">
		<Sparkles size={20} strokeWidth={2.2} class="describe-icon" />
		<input
			type="text"
			bind:value={instruction}
			placeholder="Describe what you want to hear — “late-night drive, moody synths”"
			aria-label="Describe what you want to hear"
		/>
		<select bind:value={length} aria-label="Playlist length" class="length">
			{#each lengthOptions as option (option)}
				<option value={option}>{option} tracks</option>
			{/each}
		</select>
		<button type="submit" class="go" disabled={!instruction.trim()}>Create</button>
	</div>
	{#if describeError}<p class="error">{describeError}</p>{/if}
</form>

<!-- Feed -->
{#if feedStatus === 'loading'}
	<div class="feed">
		{#each rowSkeletons as row (row)}
			<section class="shelf">
				<span class="skeleton skel-heading"></span>
				<div class="rail">
					{#each cardSkeletons as card (card)}
						<article class="song skeleton-card">
							<span class="skeleton skel-art"></span>
							<span class="skeleton skel-line" style="width:80%"></span>
							<span class="skeleton skel-line" style="width:55%"></span>
						</article>
					{/each}
				</div>
			</section>
		{/each}
	</div>
{:else if feedStatus === 'error'}
	<div class="notice">
		<p>Couldn’t load your recommendations.</p>
		<button type="button" class="ghost" onclick={() => loadFeed()}>
			<RefreshCw size={16} strokeWidth={2.2} /> Try again
		</button>
	</div>
{:else if feed}
	<div class="feed">
		{#if feed.playlists.length}
			<section class="shelf">
				<h2>Made for you</h2>
				<div class="playlist-grid">
					{#each feed.playlists as playlist (playlist.key)}
						<button type="button" class="playlist-card" onclick={() => openPlaylist(playlist)}>
							<MediaThumb
								kind="cover"
								src={playlist.coverUrl}
								alt={`${playlist.name} cover`}
								size="large"
								label={playlist.name}
							/>
							<strong>{playlist.name}</strong>
							<small>{playlist.description}</small>
						</button>
					{/each}
				</div>
			</section>
		{/if}

		{#each feed.rows as row (row.key)}
			<section class="shelf">
				<h2>{row.caption}</h2>
				<div class="rail">
					{#each row.tracks as track, index (track.spotifyTrackId ?? index)}
						<article class="song">
							<MediaThumb
								kind="cover"
								src={track.coverUrl}
								alt={`${track.album} artwork`}
								size="large"
								label={track.title}
							/>
							<strong>{track.title}</strong>
							<small>{track.artist}</small>
							{#if track.externalUrl}
								<a
									class="open"
									href={track.externalUrl}
									target="_blank"
									rel="noreferrer noopener"
									aria-label={`Open ${track.title} in Spotify`}
								>
									<ExternalLink size={16} strokeWidth={2.2} />
								</a>
							{/if}
						</article>
					{/each}
				</div>
			</section>
		{/each}

		{#if !feed.rows.length && !feed.playlists.length}
			<div class="notice">
				<p>Sync your Spotify library to get recommendations.</p>
			</div>
		{/if}
	</div>
{/if}

<PlaylistModal
	open={modalOpen}
	loading={modalLoading}
	playlist={modalPlaylist}
	onClose={() => (modalOpen = false)}
/>

<style>
	.page-header {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 20px;
	}

	.refresh {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 38px;
		padding: 0 16px;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: transparent;
		color: var(--color-soft);
		font-weight: 700;
		font-size: 0.86rem;
		cursor: pointer;
		flex: 0 0 auto;
		transition:
			background 160ms ease,
			color 160ms ease;
	}

	.refresh:hover:not(:disabled) {
		background: #1f1f1f;
		color: #fff;
	}

	.refresh:disabled {
		opacity: 0.55;
		cursor: progress;
	}

	/* describe bar */
	.describe {
		margin-bottom: 34px;
	}

	.describe-field {
		display: flex;
		align-items: center;
		gap: 10px;
		padding: 8px 8px 8px 16px;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: var(--color-surface-elevated);
		transition: border-color 160ms ease;
	}

	.describe-field:focus-within {
		border-color: var(--color-accent);
	}

	.describe-field :global(.describe-icon) {
		color: var(--color-accent);
		flex: 0 0 auto;
	}

	.describe-field input {
		flex: 1 1 auto;
		min-width: 0;
		border: 0;
		background: transparent;
		color: #fff;
		font: inherit;
		font-size: 1rem;
		padding: 8px 0;
	}

	.describe-field input:focus {
		outline: none;
	}

	.length {
		flex: 0 0 auto;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: #121212;
		color: var(--color-soft);
		font: inherit;
		font-size: 0.82rem;
		padding: 8px 10px;
		cursor: pointer;
	}

	.go {
		flex: 0 0 auto;
		min-height: 42px;
		padding: 0 22px;
		border: 0;
		border-radius: 999px;
		background: var(--color-accent);
		color: #061109;
		font-weight: 800;
		cursor: pointer;
		transition: transform 160ms ease;
	}

	.go:hover:not(:disabled) {
		transform: translateY(-1px);
	}

	.go:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.error {
		margin: 12px 4px 0;
		color: #ffd2d2;
		font-size: 0.85rem;
	}

	/* feed */
	.feed {
		display: grid;
		gap: 34px;
	}

	.shelf h2 {
		margin: 0 0 14px;
		font-size: 1.3rem;
	}

	.rail {
		display: flex;
		gap: 16px;
		overflow-x: auto;
		padding-bottom: 10px;
		scrollbar-width: thin;
	}

	.song {
		position: relative;
		display: grid;
		align-content: start;
		gap: 4px;
		flex: 0 0 168px;
		width: 168px;
		padding: 12px;
		border-radius: 10px;
		background: #181818;
		transition: background 160ms ease;
	}

	.song:hover {
		background: #242424;
	}

	.song strong,
	.song small {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.song strong {
		margin-top: 8px;
		font-size: 0.92rem;
	}

	.song small {
		color: #a7a7a7;
		font-size: 0.82rem;
	}

	.open {
		position: absolute;
		right: 18px;
		top: 18px;
		display: grid;
		width: 32px;
		height: 32px;
		place-items: center;
		border-radius: 999px;
		background: rgba(0, 0, 0, 0.5);
		color: #fff;
		opacity: 0;
		transition: opacity 160ms ease;
	}

	.song:hover .open {
		opacity: 1;
	}

	.open:hover {
		background: #1ed760;
		color: #071108;
	}

	/* playlists */
	.playlist-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 16px;
	}

	.playlist-card {
		display: grid;
		align-content: start;
		gap: 4px;
		padding: 14px;
		border: 0;
		border-radius: 10px;
		background: #181818;
		color: #fff;
		text-align: left;
		cursor: pointer;
		transition: background 160ms ease;
	}

	.playlist-card:hover {
		background: #242424;
	}

	.playlist-card strong {
		margin-top: 10px;
		font-size: 0.98rem;
	}

	.playlist-card small {
		color: #a7a7a7;
		font-size: 0.82rem;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* states */
	.notice {
		display: grid;
		place-items: center;
		gap: 14px;
		padding: 56px 24px;
		border: 1px dashed var(--color-border);
		border-radius: 12px;
		color: var(--color-muted);
		text-align: center;
	}

	.ghost {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 18px;
		border: 0;
		border-radius: 999px;
		background: #2a2a2a;
		color: #fff;
		font-weight: 800;
		cursor: pointer;
	}

	.skel-heading {
		display: block;
		width: 180px;
		height: 20px;
		margin-bottom: 14px;
		border-radius: 6px;
	}

	.skeleton-card {
		pointer-events: none;
	}

	.skel-art {
		width: 100%;
		aspect-ratio: 1;
		border-radius: 8px;
		margin-bottom: 8px;
	}

	.skel-line {
		height: 11px;
		border-radius: 4px;
	}

	@media (max-width: 640px) {
		.describe-field {
			flex-wrap: wrap;
			border-radius: 16px;
		}

		.describe-field input {
			flex-basis: 100%;
			order: -1;
		}
	}
</style>
