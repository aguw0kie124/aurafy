<script lang="ts">
	import { Music2, UserRound } from '@lucide/svelte';

	let {
		src = null,
		alt,
		kind,
		size = 'medium',
		round = false,
		label = ''
	}: {
		src?: string | null;
		alt: string;
		kind: 'artist' | 'cover';
		size?: 'small' | 'medium' | 'large';
		round?: boolean;
		label?: string;
	} = $props();

	const initials = $derived(label.trim().slice(0, 2).toUpperCase());
</script>

<span class={`thumb ${size}`} class:round>
	{#if src}
		<img {src} {alt} />
	{:else if initials}
		<strong aria-hidden="true">{initials}</strong>
	{:else if kind === 'artist'}
		<UserRound aria-hidden="true" />
	{:else}
		<Music2 aria-hidden="true" />
	{/if}
</span>

<style>
	.thumb {
		display: grid;
		flex: 0 0 auto;
		place-items: center;
		overflow: hidden;
		background: #2a2d2b;
		color: #aeb5b0;
	}

	img {
		width: 100%;
		height: 100%;
		object-fit: cover;
	}

	strong {
		font-size: 0.95rem;
		letter-spacing: 0;
	}

	.small {
		width: 48px;
		height: 48px;
		border-radius: 8px;
	}

	.medium {
		width: 72px;
		height: 72px;
		border-radius: 10px;
	}

	.large {
		width: 160px;
		height: 160px;
		border-radius: 16px;
	}

	.round {
		border-radius: 999px;
	}
</style>
