<script lang="ts">
	import { X, ExternalLink } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import { createPlaylist, type ProposedTrack } from '$lib/data/music';

	type ModalPlaylist = {
		name: string;
		description: string;
		tracks: ProposedTrack[];
		trackUris: string[];
	};

	let {
		open = false,
		loading = false,
		playlist = null,
		onClose
	}: {
		open?: boolean;
		loading?: boolean;
		playlist?: ModalPlaylist | null;
		onClose: () => void;
	} = $props();

	let saving = $state(false);
	let savedUrl = $state<string | null>(null);
	let errorMessage = $state('');
	let savedFor = $state('');

	// Reset the save state whenever a new playlist is shown.
	$effect(() => {
		const id = playlist ? `${playlist.name}:${playlist.trackUris.length}` : '';
		if (id !== savedFor) {
			savedFor = id;
			savedUrl = null;
			errorMessage = '';
			saving = false;
		}
	});

	const skeletonRows = Array.from({ length: 8 }, (_, i) => i);

	async function save() {
		if (!playlist) return;
		saving = true;
		errorMessage = '';
		try {
			const result = await createPlaylist({
				name: playlist.name,
				description: playlist.description,
				trackUris: playlist.trackUris,
				isPublic: false
			});
			savedUrl = result.spotifyUrl;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Could not save to Spotify.';
		} finally {
			saving = false;
		}
	}

	function onBackdrop(event: MouseEvent) {
		if (event.target === event.currentTarget) onClose();
	}
</script>

<svelte:window
	onkeydown={(event) => {
		if (open && event.key === 'Escape') onClose();
	}}
/>

{#if open}
	<div class="overlay" onclick={onBackdrop} role="presentation">
		<div class="modal" role="dialog" aria-modal="true" aria-label="Playlist">
			<button class="close" type="button" aria-label="Close" onclick={onClose}>
				<X size={20} strokeWidth={2.2} />
			</button>

			{#if loading}
				<header class="modal-head">
					<div>
						<h2>Building your playlist…</h2>
						<p>Finding tracks that match your vibe.</p>
					</div>
				</header>
				<ol class="tracklist" aria-hidden="true">
					{#each skeletonRows as row (row)}
						<li class="track skeleton-row">
							<span class="skeleton skel-thumb"></span>
							<span class="skel-copy">
								<span class="skeleton skel-line" style="width:60%"></span>
								<span class="skeleton skel-line" style="width:40%"></span>
							</span>
						</li>
					{/each}
				</ol>
			{:else if playlist}
				<header class="modal-head">
					<div>
						<h2>{playlist.name}</h2>
						{#if playlist.description}<p>{playlist.description}</p>{/if}
						<small>{playlist.tracks.length} tracks</small>
					</div>
					<div class="actions">
						{#if savedUrl}
							<a class="primary" href={savedUrl} target="_blank" rel="noreferrer noopener">
								<ExternalLink size={16} strokeWidth={2.2} /> Open in Spotify
							</a>
						{:else}
							<button type="button" class="primary" onclick={save} disabled={saving}>
								{saving ? 'Saving…' : 'Save to Spotify'}
							</button>
						{/if}
					</div>
				</header>

				{#if errorMessage}<p class="error">{errorMessage}</p>{/if}

				<ol class="tracklist">
					{#each playlist.tracks as track, index (track.spotifyTrackId ?? index)}
						<li class="track">
							<span class="num">{index + 1}</span>
							<MediaThumb
								kind="cover"
								src={track.coverUrl}
								alt={`${track.album} artwork`}
								size="small"
								label={track.title}
							/>
							<span class="track-copy">
								<strong>{track.title}</strong>
								<small>{track.artist}</small>
							</span>
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
						</li>
					{/each}
				</ol>
			{/if}
		</div>
	</div>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		z-index: 60;
		display: grid;
		place-items: center;
		padding: 24px;
		background: rgba(0, 0, 0, 0.62);
		backdrop-filter: blur(2px);
	}

	.modal {
		position: relative;
		display: flex;
		flex-direction: column;
		width: min(640px, 100%);
		max-height: min(80vh, 760px);
		padding: 24px;
		border: 1px solid var(--color-border);
		border-radius: 14px;
		background: var(--color-surface-elevated);
		box-shadow: 0 30px 80px rgba(0, 0, 0, 0.5);
	}

	.close {
		position: absolute;
		right: 14px;
		top: 14px;
		display: grid;
		width: 34px;
		height: 34px;
		place-items: center;
		border: 0;
		border-radius: 999px;
		background: #2a2a2a;
		color: #fff;
		cursor: pointer;
	}

	.close:hover {
		background: #3a3a3a;
	}

	.modal-head {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 16px;
		margin: 0 40px 18px 0;
		flex-wrap: wrap;
	}

	.modal-head h2 {
		margin: 0 0 4px;
		font-size: 1.4rem;
	}

	.modal-head p {
		margin: 0;
		color: var(--color-muted);
	}

	.modal-head small {
		color: var(--color-soft);
		font-size: 0.76rem;
	}

	.actions .primary {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 40px;
		padding: 0 18px;
		border: 0;
		border-radius: 999px;
		background: var(--color-accent);
		color: #061109;
		font-weight: 800;
		cursor: pointer;
		text-decoration: none;
	}

	.actions .primary:disabled {
		opacity: 0.6;
		cursor: progress;
	}

	.tracklist {
		margin: 0;
		padding: 0;
		list-style: none;
		overflow-y: auto;
	}

	.track {
		display: grid;
		grid-template-columns: 22px 40px minmax(0, 1fr) auto;
		align-items: center;
		gap: 12px;
		padding: 7px 8px;
		border-radius: 8px;
	}

	.track:hover {
		background: #242424;
	}

	.num {
		color: var(--color-muted);
		font-size: 0.82rem;
		text-align: right;
	}

	.track-copy {
		display: grid;
		min-width: 0;
		gap: 2px;
	}

	.track-copy strong,
	.track-copy small {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.track-copy small {
		color: #a7a7a7;
	}

	.open {
		display: grid;
		place-items: center;
		width: 32px;
		height: 32px;
		border-radius: 999px;
		color: var(--color-muted);
	}

	.open:hover {
		color: #1ed760;
	}

	.error {
		margin: 0 0 12px;
		padding: 10px 12px;
		border-radius: 8px;
		background: rgba(255, 120, 120, 0.1);
		color: #ffd2d2;
		font-size: 0.85rem;
	}

	.skeleton-row {
		grid-template-columns: 40px minmax(0, 1fr);
		pointer-events: none;
	}

	.skel-thumb {
		width: 40px;
		height: 40px;
		border-radius: 6px;
	}

	.skel-copy {
		display: grid;
		gap: 6px;
	}

	.skel-line {
		height: 10px;
		border-radius: 4px;
	}
</style>
