<script lang="ts">
	import { Sparkles, ExternalLink, RefreshCw } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import {
		previewPlaylist,
		createPlaylist,
		type ProposedPlaylist,
		type PlaylistPreviewInput,
		type StatsRangeValue
	} from '$lib/data/music';

	// Page contract props (unused here, but App passes them to every page).
	let {}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
		loading?: boolean;
	} = $props();

	let instruction = $state('');
	let length = $state(25);
	let mix = $state(30);
	let allowExplicit = $state(true);
	let genresText = $state('');
	let avoidText = $state('');
	let seedText = $state('');

	let status = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
	let errorMessage = $state('');
	let proposed = $state<ProposedPlaylist | null>(null);

	let saving = $state(false);
	let savedUrl = $state<string | null>(null);

	const usingInstruction = $derived(instruction.trim().length > 0);
	const mixLabel = $derived(
		mix <= 15 ? 'Mostly familiar' : mix >= 85 ? 'Mostly new' : `${100 - mix}% familiar · ${mix}% new`
	);
	const skeletonCards = Array.from({ length: 8 }, (_, i) => i);

	function parseList(value: string): string[] {
		return value
			.split(',')
			.map((item) => item.trim())
			.filter(Boolean);
	}

	async function generate() {
		status = 'loading';
		errorMessage = '';
		savedUrl = null;

		const input: PlaylistPreviewInput = usingInstruction
			? { mode: 'instruction', instruction: instruction.trim() }
			: {
					mode: 'params',
					length,
					mix,
					allowExplicit,
					genres: parseList(genresText),
					avoidGenres: parseList(avoidText),
					seedArtistNames: parseList(seedText)
				};

		try {
			proposed = await previewPlaylist(input);
			status = 'ready';
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Could not build a playlist.';
			status = 'error';
		}
	}

	async function save() {
		if (!proposed) return;
		saving = true;
		errorMessage = '';

		try {
			const result = await createPlaylist({
				name: proposed.name,
				description: proposed.description,
				trackUris: proposed.trackUris,
				isPublic: false
			});
			savedUrl = result.spotifyUrl;
		} catch (error) {
			errorMessage = error instanceof Error ? error.message : 'Could not save to Spotify.';
		} finally {
			saving = false;
		}
	}
</script>

<section class="page-header">
	<SectionHeading title="Build a Playlist" subtitle="Grounded in your real library." />
</section>

<div class="builder">
	<form
		class="controls"
		onsubmit={(event) => {
			event.preventDefault();
			generate();
		}}
	>
		<label class="field">
			<span>Describe it (optional)</span>
			<textarea
				bind:value={instruction}
				rows="3"
				placeholder="chill indie for a rainy sunday, mostly stuff I haven't heard"
			></textarea>
			<small>Leave blank to use the controls below.</small>
		</label>

		<fieldset class:muted={usingInstruction} disabled={usingInstruction}>
			<div class="field">
				<span>Length: {length} tracks</span>
				<input type="range" min="5" max="50" bind:value={length} />
			</div>

			<div class="field">
				<span>Mix — {mixLabel}</span>
				<input type="range" min="0" max="100" step="5" bind:value={mix} />
				<div class="mix-ends"><small>Familiar</small><small>Discovery</small></div>
			</div>

			<label class="field">
				<span>Focus genres (optional, comma-separated)</span>
				<input type="text" bind:value={genresText} placeholder="indie rock, dream pop" />
			</label>

			<label class="field">
				<span>Avoid genres (optional, comma-separated)</span>
				<input type="text" bind:value={avoidText} placeholder="rap, country" />
			</label>

			<label class="field">
				<span>Sounds-like artists (optional, comma-separated)</span>
				<input type="text" bind:value={seedText} placeholder="Radiohead, Beach House" />
			</label>

			<label class="checkbox">
				<input type="checkbox" bind:checked={allowExplicit} />
				<span>Allow explicit tracks</span>
			</label>
		</fieldset>

		<button type="submit" class="primary" disabled={status === 'loading'}>
			<Sparkles size={18} strokeWidth={2.2} />
			{status === 'loading' ? 'Building…' : 'Generate playlist'}
		</button>

		{#if errorMessage}
			<p class="error">{errorMessage}</p>
		{/if}
	</form>

	<section class="result" aria-live="polite">
		{#if status === 'loading'}
			<div class="song-grid" aria-hidden="true">
				{#each skeletonCards as item (item)}
					<article class="skeleton-card">
						<span class="skeleton skeleton-artwork"></span>
						<span class="skeleton-copy">
							<span class="skeleton skeleton-line" style="width:80%"></span>
							<span class="skeleton skeleton-line" style="width:60%"></span>
						</span>
					</article>
				{/each}
			</div>
		{:else if status === 'ready' && proposed}
			<header class="result-head">
				<div>
					<h2>{proposed.name}</h2>
					<p>{proposed.description}</p>
				</div>
				<div class="result-actions">
					<button type="button" class="ghost" onclick={generate} disabled={saving}>
						<RefreshCw size={16} strokeWidth={2.2} /> Regenerate
					</button>
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

			<div class="song-grid">
				{#each proposed.tracks as track, index (track.spotifyTrackId ?? index)}
					<article>
						<div class="card-main">
							<MediaThumb
								kind="cover"
								src={track.coverUrl}
								alt={`${track.album} artwork`}
								size="large"
								label={track.title}
							/>
							<span class="card-copy">
								<strong>{track.title}</strong>
								<small>{track.artist}</small>
								<em class:discovery={track.source === 'discovery' || track.source === 'curated'}>
									{track.source === 'curated'
										? 'Curated for you'
										: track.source === 'discovery'
											? 'New'
											: 'From your library'}
								</em>
							</span>
						</div>
						{#if track.externalUrl}
							<a
								class="spotify-open"
								href={track.externalUrl}
								target="_blank"
								rel="noreferrer noopener"
								aria-label={`Open ${track.title} in Spotify`}
							>
								<ExternalLink size={17} strokeWidth={2.2} />
							</a>
						{/if}
					</article>
				{/each}
			</div>
		{:else}
			<div class="placeholder">
				<Sparkles size={26} strokeWidth={1.8} />
				<p>Set your controls or describe a vibe, then generate a playlist from your library.</p>
			</div>
		{/if}
	</section>
</div>

<style>
	.page-header {
		margin-bottom: 28px;
	}

	.builder {
		display: grid;
		grid-template-columns: minmax(280px, 340px) 1fr;
		gap: 28px;
		align-items: start;
	}

	.controls {
		display: grid;
		gap: 18px;
		padding: 20px;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface-elevated);
		position: sticky;
		top: 84px;
	}

	fieldset {
		display: grid;
		gap: 16px;
		margin: 0;
		padding: 0;
		border: 0;
		transition: opacity 160ms ease;
	}

	fieldset.muted {
		opacity: 0.4;
	}

	.field {
		display: grid;
		gap: 7px;
	}

	.field > span {
		font-size: 0.86rem;
		font-weight: 700;
		color: var(--color-soft);
	}

	.field small {
		color: var(--color-muted);
		font-size: 0.76rem;
	}

	textarea,
	input[type='text'] {
		width: 100%;
		padding: 10px 12px;
		border: 1px solid var(--color-border);
		border-radius: 8px;
		background: #121212;
		color: #fff;
		font: inherit;
		resize: vertical;
	}

	input[type='range'] {
		width: 100%;
		accent-color: var(--color-accent);
	}

	.mix-ends {
		display: flex;
		justify-content: space-between;
	}

	.checkbox {
		display: flex;
		align-items: center;
		gap: 10px;
		font-size: 0.9rem;
		color: var(--color-soft);
	}

	.checkbox input {
		accent-color: var(--color-accent);
	}

	.primary,
	.ghost {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 8px;
		min-height: 42px;
		padding: 0 18px;
		border: 0;
		border-radius: 999px;
		font-weight: 800;
		cursor: pointer;
		transition:
			background 160ms ease,
			transform 160ms ease;
	}

	.primary {
		background: var(--color-accent);
		color: #061109;
	}

	.primary:hover:not(:disabled) {
		transform: translateY(-1px);
	}

	.ghost {
		background: #2a2a2a;
		color: #fff;
	}

	.primary:disabled,
	.ghost:disabled {
		opacity: 0.6;
		cursor: progress;
	}

	.error {
		margin: 0;
		padding: 10px 12px;
		border-radius: 8px;
		background: rgba(255, 120, 120, 0.1);
		color: #ffd2d2;
		font-size: 0.85rem;
	}

	.result-head {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 16px;
		margin-bottom: 22px;
		flex-wrap: wrap;
	}

	.result-head h2 {
		margin: 0 0 4px;
		font-size: 1.5rem;
	}

	.result-head p {
		margin: 0;
		color: var(--color-muted);
	}

	.result-actions {
		display: flex;
		gap: 10px;
	}

	.result-actions .primary {
		text-decoration: none;
	}

	.song-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
		gap: 16px;
	}

	article {
		position: relative;
		display: grid;
		border-radius: 8px;
		background: #181818;
		transition: background 160ms ease;
	}

	article:hover {
		background: #242424;
	}

	.card-main {
		display: grid;
		gap: 14px;
		min-width: 0;
		padding: 16px;
	}

	.card-copy {
		display: grid;
		min-width: 0;
		gap: 5px;
	}

	.card-copy strong,
	.card-copy small,
	.card-copy em {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.card-copy small {
		color: #a7a7a7;
	}

	.card-copy em {
		font-style: normal;
		font-weight: 800;
		font-size: 0.7rem;
		text-transform: uppercase;
		color: #8a8a8a;
	}

	.card-copy em.discovery {
		color: var(--color-accent);
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
		transition: opacity 160ms ease;
	}

	article:hover .spotify-open {
		opacity: 1;
	}

	.spotify-open:hover {
		background: #1ed760;
		color: #071108;
	}

	.placeholder {
		display: grid;
		place-items: center;
		gap: 12px;
		padding: 64px 24px;
		border: 1px dashed var(--color-border);
		border-radius: 12px;
		color: var(--color-muted);
		text-align: center;
	}

	.skeleton-card {
		gap: 14px;
		padding: 16px;
		pointer-events: none;
	}

	.skeleton-artwork {
		width: 100%;
		aspect-ratio: 1;
		border-radius: 16px;
	}

	.skeleton-copy {
		display: grid;
		gap: 8px;
	}

	@media (max-width: 900px) {
		.builder {
			grid-template-columns: 1fr;
		}

		.controls {
			position: static;
		}
	}
</style>
