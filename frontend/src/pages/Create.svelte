<script lang="ts">
	import { ExternalLink, Sparkles, RefreshCw, Loader } from '@lucide/svelte';
	import MediaThumb from '$lib/components/MediaThumb.svelte';
	import SectionHeading from '$lib/components/SectionHeading.svelte';
	import {
		commitPlaylist,
		generatePlaylist,
		rangeOptions,
		type CommitPlaylistResult,
		type ProposedPlaylist,
		type StatsRangeValue
	} from '$lib/data/music';

	let {
		activeRange = 'medium_term'
	}: {
		activeRange?: StatsRangeValue;
		onRangeChange?: (range: StatsRangeValue) => void;
		loading?: boolean;
	} = $props();

	let prompt = $state('');
	let length = $state(25);
	let mix = $state(30);
	let allowExplicit = $state(true);
	let range = $state<StatsRangeValue>(activeRange);

	let status = $state<'idle' | 'generating' | 'ready' | 'error'>('idle');
	let errorMessage = $state<string | null>(null);
	let proposed = $state<ProposedPlaylist | null>(null);

	let committing = $state(false);
	let commitError = $state<string | null>(null);
	let commitResult = $state<CommitPlaylistResult | null>(null);

	const canGenerate = $derived(prompt.trim().length > 0 && status !== 'generating');
	const skeletonRows = Array.from({ length: 8 }, (_, index) => index);

	async function generate() {
		if (!canGenerate) {
			return;
		}

		status = 'generating';
		errorMessage = null;
		commitError = null;
		commitResult = null;

		try {
			proposed = await generatePlaylist({
				prompt: prompt.trim(),
				length,
				mix,
				allowExplicit,
				range
			});
			status = 'ready';
		} catch (error) {
			proposed = null;
			status = 'error';
			errorMessage = error instanceof Error ? error.message : 'Generation failed. Try again.';
		}
	}

	async function save() {
		if (!proposed || committing) {
			return;
		}

		committing = true;
		commitError = null;

		try {
			commitResult = await commitPlaylist(proposed.generationId);
		} catch (error) {
			commitError =
				error instanceof Error ? error.message : 'Could not save the playlist to Spotify.';
		} finally {
			committing = false;
		}
	}
</script>

<section class="page-header">
	<SectionHeading
		title="Create a Playlist"
		subtitle="Describe what you want. Aurafy curates it from your listening history."
	/>
</section>

<div class="builder">
	<form
		class="prompt-card"
		onsubmit={(event) => {
			event.preventDefault();
			void generate();
		}}
	>
		<label class="field">
			<span>What should this playlist feel like?</span>
			<textarea
				bind:value={prompt}
				rows="3"
				placeholder="e.g. upbeat indie for a late-night drive — lean into my recent discoveries but sprinkle in a few new artists"
			></textarea>
		</label>

		<div class="controls">
			<label class="control">
				<span>Length</span>
				<input type="number" min="5" max="50" bind:value={length} />
			</label>

			<label class="control wide">
				<span>Familiar ↔ Discovery ({mix}%)</span>
				<input type="range" min="0" max="100" step="5" bind:value={mix} />
			</label>

			<label class="control">
				<span>Based on</span>
				<select bind:value={range}>
					{#each rangeOptions as option (option.value)}
						<option value={option.value}>{option.label}</option>
					{/each}
				</select>
			</label>

			<label class="control toggle">
				<input type="checkbox" bind:checked={allowExplicit} />
				<span>Allow explicit</span>
			</label>
		</div>

		<button type="submit" class="generate" disabled={!canGenerate}>
			{#if status === 'generating'}
				<Loader class="spin" size={18} strokeWidth={2.2} />
				Curating…
			{:else}
				<Sparkles size={18} strokeWidth={2.2} />
				Generate playlist
			{/if}
		</button>

		{#if status === 'error' && errorMessage}
			<p class="inline-error">{errorMessage}</p>
		{/if}
	</form>

	{#if status === 'generating'}
		<section class="preview">
			<div class="preview-head">
				<span class="skeleton skeleton-line skeleton-name"></span>
				<span class="skeleton skeleton-line skeleton-desc"></span>
			</div>
			<ul class="track-list" aria-hidden="true">
				{#each skeletonRows as row (row)}
					<li class="track-row skeleton-row">
						<span class="skeleton skeleton-thumb"></span>
						<span class="skeleton-copy">
							<span class="skeleton skeleton-line skeleton-title"></span>
							<span class="skeleton skeleton-line skeleton-meta"></span>
						</span>
					</li>
				{/each}
			</ul>
		</section>
	{:else if status === 'ready' && proposed}
		<section class="preview">
			<div class="preview-head">
				<div class="preview-title">
					<h2>{proposed.name}</h2>
					<p>{proposed.description}</p>
					<small>{proposed.tracks.length} tracks</small>
				</div>
				<div class="preview-actions">
					<button type="button" class="ghost" onclick={generate} disabled={committing}>
						<RefreshCw size={17} strokeWidth={2.2} />
						Regenerate
					</button>
					<button type="button" class="save" onclick={save} disabled={committing || !!commitResult}>
						{#if committing}
							<Loader class="spin" size={17} strokeWidth={2.2} />
							Saving…
						{:else}
							Save to Spotify
						{/if}
					</button>
				</div>
			</div>

			{#if commitResult}
				<p class="success">
					Saved {commitResult.trackCount} tracks to Spotify.
					{#if commitResult.spotifyUrl}
						<a href={commitResult.spotifyUrl} target="_blank" rel="noreferrer noopener">
							Open playlist <ExternalLink size={15} strokeWidth={2.2} />
						</a>
					{/if}
				</p>
			{:else if commitError}
				<p class="inline-error">{commitError}</p>
			{/if}

			<ul class="track-list">
				{#each proposed.tracks as track, index (track.spotifyTrackId ?? index)}
					<li class="track-row">
						<span class="track-index">{index + 1}</span>
						<MediaThumb
							kind="cover"
							src={track.coverUrl}
							alt={`${track.album} album artwork`}
							size="small"
							label={track.title}
						/>
						<span class="track-copy">
							<strong>{track.title}</strong>
							<small>{track.artist}</small>
							{#if track.reason}
								<em>{track.reason}</em>
							{/if}
						</span>
						{#if track.externalUrl}
							<a
								class="track-open"
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
			</ul>
		</section>
	{/if}
</div>

<style>
	.page-header {
		margin-bottom: 28px;
	}

	.builder {
		display: grid;
		gap: 28px;
	}

	.prompt-card {
		display: grid;
		gap: 20px;
		padding: 24px;
		border: 1px solid var(--color-border);
		border-radius: 12px;
		background: var(--color-surface-elevated, #181818);
	}

	.field {
		display: grid;
		gap: 10px;
	}

	.field > span,
	.control > span {
		font-weight: 700;
		font-size: 0.9rem;
		color: var(--color-soft, #c5cbc7);
	}

	textarea {
		width: 100%;
		padding: 14px;
		border: 1px solid var(--color-border, #2a2a2a);
		border-radius: 10px;
		background: #0f0f0f;
		color: #fff;
		font: inherit;
		resize: vertical;
	}

	textarea:focus-visible,
	input:focus-visible,
	select:focus-visible {
		outline: 2px solid var(--color-accent, #1ed760);
		outline-offset: 1px;
	}

	.controls {
		display: flex;
		flex-wrap: wrap;
		align-items: end;
		gap: 18px;
	}

	.control {
		display: grid;
		gap: 8px;
	}

	.control.wide {
		flex: 1 1 220px;
	}

	.control input[type='number'],
	.control select {
		min-height: 40px;
		padding: 0 12px;
		border: 1px solid var(--color-border, #2a2a2a);
		border-radius: 8px;
		background: #0f0f0f;
		color: #fff;
		font: inherit;
	}

	.control input[type='number'] {
		width: 84px;
	}

	.control input[type='range'] {
		width: 100%;
		accent-color: var(--color-accent, #1ed760);
	}

	.control.toggle {
		grid-auto-flow: column;
		align-items: center;
		gap: 8px;
	}

	.control.toggle input {
		width: 18px;
		height: 18px;
		accent-color: var(--color-accent, #1ed760);
	}

	.generate {
		display: inline-flex;
		align-items: center;
		justify-content: center;
		gap: 10px;
		justify-self: start;
		min-height: 46px;
		padding: 0 24px;
		border: 0;
		border-radius: 999px;
		background: var(--color-accent, #1ed760);
		color: #061109;
		font-weight: 800;
		cursor: pointer;
		transition: transform 160ms ease, opacity 160ms ease;
	}

	.generate:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.generate:not(:disabled):hover {
		transform: translateY(-1px);
	}

	.preview {
		display: grid;
		gap: 18px;
	}

	.preview-head {
		display: flex;
		align-items: end;
		justify-content: space-between;
		gap: 20px;
		flex-wrap: wrap;
	}

	.preview-title h2 {
		margin: 0;
		font-size: clamp(1.5rem, 3vw, 2rem);
	}

	.preview-title p {
		margin: 6px 0 0;
		color: var(--color-soft, #c5cbc7);
	}

	.preview-title small {
		display: block;
		margin-top: 6px;
		color: var(--color-muted, #a7a7a7);
		text-transform: uppercase;
		font-weight: 800;
		font-size: 0.75rem;
	}

	.preview-actions {
		display: flex;
		gap: 10px;
	}

	.ghost,
	.save {
		display: inline-flex;
		align-items: center;
		gap: 8px;
		min-height: 42px;
		padding: 0 18px;
		border-radius: 999px;
		font-weight: 800;
		cursor: pointer;
		transition: transform 160ms ease, background 160ms ease;
	}

	.ghost {
		border: 1px solid var(--color-border, #2a2a2a);
		background: transparent;
		color: #fff;
	}

	.ghost:hover:not(:disabled) {
		background: #242424;
	}

	.save {
		border: 0;
		background: var(--color-accent, #1ed760);
		color: #061109;
	}

	.save:disabled,
	.ghost:disabled {
		opacity: 0.55;
		cursor: not-allowed;
	}

	.track-list {
		display: grid;
		gap: 4px;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.track-row {
		display: grid;
		grid-template-columns: 26px 48px minmax(0, 1fr) auto;
		align-items: center;
		gap: 14px;
		padding: 8px 10px;
		border-radius: 8px;
		background: #181818;
	}

	.track-row:hover {
		background: #242424;
	}

	.track-index {
		color: var(--color-muted, #a7a7a7);
		font-weight: 700;
		text-align: center;
	}

	.track-copy {
		display: grid;
		min-width: 0;
		gap: 2px;
	}

	.track-copy strong,
	.track-copy small,
	.track-copy em {
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.track-copy small {
		color: var(--color-muted, #a7a7a7);
	}

	.track-copy em {
		font-style: normal;
		font-size: 0.82rem;
		color: var(--color-accent, #1ed760);
	}

	.track-open {
		display: grid;
		width: 34px;
		height: 34px;
		place-items: center;
		border-radius: 999px;
		color: var(--color-soft, #c5cbc7);
	}

	.track-open:hover {
		background: #1ed760;
		color: #071108;
	}

	.success {
		display: flex;
		align-items: center;
		gap: 8px;
		margin: 0;
		padding: 12px 14px;
		border-radius: 8px;
		border: 1px solid rgba(30, 215, 96, 0.3);
		background: rgba(30, 215, 96, 0.08);
		color: #b9f5cf;
	}

	.success a {
		display: inline-flex;
		align-items: center;
		gap: 5px;
		color: var(--color-accent, #1ed760);
		font-weight: 800;
	}

	.inline-error {
		margin: 0;
		padding: 12px 14px;
		border-radius: 8px;
		border: 1px solid rgba(255, 120, 120, 0.32);
		background: rgba(255, 120, 120, 0.08);
		color: #ffd2d2;
	}

	.skeleton-row {
		grid-template-columns: 48px minmax(0, 1fr);
	}

	.skeleton-thumb {
		width: 48px;
		height: 48px;
		border-radius: 8px;
	}

	.skeleton-copy {
		display: grid;
		gap: 8px;
	}

	.skeleton-name {
		width: 240px;
		height: 26px;
	}

	.skeleton-desc {
		width: 340px;
		max-width: 100%;
	}

	.skeleton-title {
		width: 60%;
	}

	.skeleton-meta {
		width: 40%;
	}

	@media (max-width: 640px) {
		.track-row {
			grid-template-columns: 22px 44px minmax(0, 1fr) auto;
			gap: 10px;
		}
	}
</style>
