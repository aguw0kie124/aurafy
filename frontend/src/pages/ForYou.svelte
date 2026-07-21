<script lang="ts">
	import { Sparkles, ExternalLink, RefreshCw, X, Search } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import {
		previewPlaylist,
		createPlaylist,
		searchLibrary,
		type ProposedPlaylist,
		type PlaylistPreviewInput,
		type LibrarySearchResult,
		type LibrarySearchTrack,
		type LibrarySearchArtist,
		type StatsRangeValue
	} from '$lib/data/music';

	// Page contract props (unused here, but App passes them to every page).
	let {}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
		loading?: boolean;
	} = $props();

	const presets = [
		{ key: 'focus', label: 'Focus', mix: 25 },
		{ key: 'workout', label: 'Workout', mix: 40 },
		{ key: 'rainy_day', label: 'Rainy day', mix: 30 },
		{ key: 'deep_cuts', label: 'Deep cuts', mix: 10 },
		{ key: 'discovery', label: 'Discovery', mix: 85 }
	] as const;

	const mixSegments = [
		{ label: 'Familiar', value: 15 },
		{ label: 'Balanced', value: 40 },
		{ label: 'Adventurous', value: 85 }
	] as const;

	let instruction = $state('');
	let length = $state(25);
	let mix = $state(40);
	let allowExplicit = $state(true);
	let selectedPreset = $state<string | null>(null);
	let seedTracks = $state<LibrarySearchTrack[]>([]);
	let seedArtists = $state<LibrarySearchArtist[]>([]);
	let avoidGenres = $state<string[]>([]);
	let avoidInput = $state('');

	// Anchor picker ("build around these") — search the user's own library.
	let anchorQuery = $state('');
	let anchorResults = $state<LibrarySearchResult>({ tracks: [], artists: [] });
	let anchorOpen = $state(false);
	let searchSeq = 0;
	let searchTimer: ReturnType<typeof setTimeout> | undefined;

	let status = $state<'idle' | 'loading' | 'ready' | 'error'>('idle');
	let errorMessage = $state('');
	let proposed = $state<ProposedPlaylist | null>(null);
	let saving = $state(false);
	let savedUrl = $state<string | null>(null);

	const skeletonCards = Array.from({ length: 8 }, (_, i) => i);
	// Highlight the segment whose band the current mix falls into (presets can set
	// off-segment values like 25 or 10).
	const activeSegment = $derived(mix < 30 ? 15 : mix < 70 ? 40 : 85);
	const hasResults = $derived(
		anchorResults.tracks.length > 0 || anchorResults.artists.length > 0
	);

	function togglePreset(key: string, presetMix: number) {
		if (selectedPreset === key) {
			selectedPreset = null;
		} else {
			selectedPreset = key;
			mix = presetMix;
		}
	}

	function onAnchorInput() {
		anchorOpen = true;
		clearTimeout(searchTimer);
		const q = anchorQuery.trim();
		if (!q) {
			anchorResults = { tracks: [], artists: [] };
			return;
		}
		const seq = ++searchSeq;
		searchTimer = setTimeout(async () => {
			try {
				const res = await searchLibrary(q, 6);
				if (seq === searchSeq) anchorResults = res;
			} catch {
				/* ignore — anchors are optional */
			}
		}, 200);
	}

	function addSeedTrack(track: LibrarySearchTrack) {
		if (!seedTracks.some((s) => s.spotifyTrackId === track.spotifyTrackId)) {
			seedTracks = [...seedTracks, track];
		}
		resetAnchorSearch();
	}

	function addSeedArtist(artist: LibrarySearchArtist) {
		if (!seedArtists.some((s) => s.spotifyArtistId === artist.spotifyArtistId)) {
			seedArtists = [...seedArtists, artist];
		}
		resetAnchorSearch();
	}

	function resetAnchorSearch() {
		anchorQuery = '';
		anchorResults = { tracks: [], artists: [] };
		anchorOpen = false;
	}

	function removeSeedTrack(id: string) {
		seedTracks = seedTracks.filter((s) => s.spotifyTrackId !== id);
	}

	function removeSeedArtist(id: string) {
		seedArtists = seedArtists.filter((s) => s.spotifyArtistId !== id);
	}

	function addAvoid() {
		const value = avoidInput.trim().toLowerCase();
		if (value && !avoidGenres.includes(value)) {
			avoidGenres = [...avoidGenres, value];
		}
		avoidInput = '';
	}

	function removeAvoid(genre: string) {
		avoidGenres = avoidGenres.filter((g) => g !== genre);
	}

	async function generate() {
		status = 'loading';
		errorMessage = '';
		savedUrl = null;

		const input: PlaylistPreviewInput = {
			mode: instruction.trim() ? 'instruction' : 'params',
			instruction: instruction.trim() || undefined,
			length,
			mix,
			allowExplicit,
			avoidGenres,
			preset: selectedPreset ?? undefined,
			seedTrackIds: seedTracks.map((t) => t.spotifyTrackId),
			seedArtistIds: seedArtists.map((a) => a.spotifyArtistId)
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
	<SectionHeading title="For You" subtitle="Build a playlist grounded in your real library." />
</section>

<div class="builder">
	<form
		class="controls"
		onsubmit={(event) => {
			event.preventDefault();
			generate();
		}}
	>
		<div class="field">
			<span>Starter vibe</span>
			<div class="chips">
				{#each presets as preset (preset.key)}
					<button
						type="button"
						class="chip toggle"
						class:on={selectedPreset === preset.key}
						onclick={() => togglePreset(preset.key, preset.mix)}
					>
						{preset.label}
					</button>
				{/each}
			</div>
		</div>

		<div class="field anchor">
			<span>Build around (optional)</span>
			<div class="anchor-search">
				<Search size={16} strokeWidth={2.2} class="anchor-icon" />
				<input
					type="text"
					bind:value={anchorQuery}
					oninput={onAnchorInput}
					onfocus={() => (anchorOpen = true)}
					placeholder="Search your songs & artists…"
				/>
				{#if anchorOpen && hasResults}
					<ul class="anchor-results">
						{#each anchorResults.artists as artist (artist.spotifyArtistId)}
							<li>
								<button type="button" onclick={() => addSeedArtist(artist)}>
									<MediaThumb
										kind="artist"
										src={artist.imageUrl}
										alt={artist.name}
										size="small"
										round
										label={artist.name}
									/>
									<span class="res-copy"><strong>{artist.name}</strong><small>Artist</small></span>
								</button>
							</li>
						{/each}
						{#each anchorResults.tracks as track (track.spotifyTrackId)}
							<li>
								<button type="button" onclick={() => addSeedTrack(track)}>
									<MediaThumb
										kind="cover"
										src={track.coverUrl}
										alt={track.title}
										size="small"
										label={track.title}
									/>
									<span class="res-copy"><strong>{track.title}</strong><small>{track.artist}</small></span>
								</button>
							</li>
						{/each}
					</ul>
				{/if}
			</div>

			{#if seedArtists.length || seedTracks.length}
				<div class="chips seeds">
					{#each seedArtists as artist (artist.spotifyArtistId)}
						<span class="chip seed">
							{artist.name}
							<button type="button" aria-label={`Remove ${artist.name}`} onclick={() => removeSeedArtist(artist.spotifyArtistId)}>
								<X size={13} strokeWidth={2.6} />
							</button>
						</span>
					{/each}
					{#each seedTracks as track (track.spotifyTrackId)}
						<span class="chip seed">
							{track.title}
							<button type="button" aria-label={`Remove ${track.title}`} onclick={() => removeSeedTrack(track.spotifyTrackId)}>
								<X size={13} strokeWidth={2.6} />
							</button>
						</span>
					{/each}
				</div>
			{/if}
		</div>

		<div class="field">
			<span>Mix</span>
			<div class="segmented" role="group" aria-label="Familiar vs discovery">
				{#each mixSegments as seg (seg.value)}
					<button
						type="button"
						class:on={activeSegment === seg.value}
						onclick={() => {
							mix = seg.value;
							selectedPreset = null;
						}}
					>
						{seg.label}
					</button>
				{/each}
			</div>
		</div>

		<div class="field">
			<span>Length: {length} tracks</span>
			<input type="range" min="5" max="50" bind:value={length} />
		</div>

		<div class="field">
			<span>Avoid genres (optional)</span>
			<input
				type="text"
				bind:value={avoidInput}
				placeholder="Type a genre, press Enter"
				onkeydown={(event) => {
					if (event.key === 'Enter') {
						event.preventDefault();
						addAvoid();
					}
				}}
			/>
			{#if avoidGenres.length}
				<div class="chips seeds">
					{#each avoidGenres as genre (genre)}
						<span class="chip seed avoid">
							{genre}
							<button type="button" aria-label={`Remove ${genre}`} onclick={() => removeAvoid(genre)}>
								<X size={13} strokeWidth={2.6} />
							</button>
						</span>
					{/each}
				</div>
			{/if}
		</div>

		<label class="checkbox">
			<input type="checkbox" bind:checked={allowExplicit} />
			<span>Allow explicit tracks</span>
		</label>

		<details class="describe">
			<summary>Or describe it in words</summary>
			<textarea
				bind:value={instruction}
				rows="3"
				placeholder="chill indie for a rainy sunday, mostly stuff I haven't heard"
			></textarea>
			<small>When filled, the AI interprets your description and drives the mix.</small>
		</details>

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
				<p>Pick a starter vibe or anchor a few songs, then generate a playlist from your library.</p>
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
		grid-template-columns: minmax(300px, 360px) 1fr;
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

	.field {
		display: grid;
		gap: 9px;
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

	/* chips (presets, seeds, avoid) */
	.chips {
		display: flex;
		flex-wrap: wrap;
		gap: 8px;
	}

	.chip {
		display: inline-flex;
		align-items: center;
		gap: 6px;
		padding: 7px 12px;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: #1a1a1a;
		color: var(--color-soft);
		font-size: 0.82rem;
		font-weight: 700;
		cursor: pointer;
		transition:
			background 140ms ease,
			color 140ms ease,
			border-color 140ms ease;
	}

	.chip.toggle:hover {
		color: #fff;
		border-color: #3a3a3a;
	}

	.chip.on {
		background: var(--color-accent);
		border-color: var(--color-accent);
		color: #061109;
	}

	.chip.seed {
		cursor: default;
		background: rgba(30, 215, 96, 0.12);
		border-color: rgba(30, 215, 96, 0.3);
		color: #fff;
	}

	.chip.seed.avoid {
		background: rgba(255, 120, 120, 0.1);
		border-color: rgba(255, 120, 120, 0.28);
	}

	.chip.seed button {
		display: grid;
		place-items: center;
		padding: 0;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: inherit;
		cursor: pointer;
		opacity: 0.7;
	}

	.chip.seed button:hover {
		opacity: 1;
	}

	/* anchor search */
	.anchor-search {
		position: relative;
		display: flex;
		align-items: center;
	}

	.anchor-search :global(.anchor-icon) {
		position: absolute;
		left: 11px;
		color: var(--color-muted);
		pointer-events: none;
	}

	.anchor-search input {
		padding-left: 34px;
	}

	.anchor-results {
		position: absolute;
		top: calc(100% + 6px);
		left: 0;
		right: 0;
		z-index: 30;
		margin: 0;
		padding: 6px;
		list-style: none;
		max-height: 320px;
		overflow-y: auto;
		border-radius: 10px;
		background: #282828;
		box-shadow: 0 18px 50px rgba(0, 0, 0, 0.5);
	}

	.anchor-results button {
		display: grid;
		grid-template-columns: 40px minmax(0, 1fr);
		align-items: center;
		gap: 10px;
		width: 100%;
		padding: 7px 8px;
		border: 0;
		border-radius: 7px;
		background: transparent;
		color: #fff;
		text-align: left;
		cursor: pointer;
	}

	.anchor-results button:hover {
		background: #3a3a3a;
	}

	.res-copy {
		display: grid;
		min-width: 0;
		gap: 2px;
	}

	.res-copy strong,
	.res-copy small {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.res-copy small {
		color: var(--color-muted);
		font-size: 0.74rem;
	}

	/* segmented mix */
	.segmented {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: 4px;
		padding: 4px;
		border: 1px solid var(--color-border);
		border-radius: 999px;
		background: #121212;
	}

	.segmented button {
		padding: 8px 4px;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: var(--color-soft);
		font-size: 0.8rem;
		font-weight: 800;
		cursor: pointer;
		transition:
			background 140ms ease,
			color 140ms ease;
	}

	.segmented button:hover {
		color: #fff;
	}

	.segmented button.on {
		background: var(--color-accent);
		color: #061109;
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

	.describe {
		display: grid;
		gap: 9px;
	}

	.describe summary {
		font-size: 0.84rem;
		font-weight: 700;
		color: var(--color-soft);
		cursor: pointer;
	}

	.describe textarea {
		margin-top: 9px;
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
