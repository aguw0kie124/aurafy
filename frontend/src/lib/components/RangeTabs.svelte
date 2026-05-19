<script lang="ts">
	import { rangeOptions, type StatsRangeValue } from '$lib/data/music';

	let {
		active = 'short_term',
		options = rangeOptions,
		onSelect = () => {}
	}: {
		active?: StatsRangeValue;
		options?: { label: string; value: StatsRangeValue }[];
		onSelect?: (range: StatsRangeValue) => void | Promise<void>;
	} = $props();
</script>

<div class="range-tabs" aria-label="Time range">
	{#each options as option (option.value)}
		<button
			type="button"
			class:active={option.value === active}
			onclick={() => onSelect(option.value)}
		>
			{option.label}
		</button>
	{/each}
</div>

<style>
	.range-tabs {
		display: flex;
		align-items: center;
		padding: 4px;
		border: 1px solid rgba(255, 255, 255, 0.16);
		border-radius: 999px;
		background: rgba(255, 255, 255, 0.02);
	}

	button {
		min-width: 96px;
		border: 0;
		border-radius: 999px;
		background: transparent;
		color: #c8ceca;
		font-weight: 700;
		padding: 10px 16px;
		cursor: pointer;
	}

	button.active {
		background: #62e792;
		color: #06120a;
	}

	@media (max-width: 560px) {
		button {
			min-width: 0;
			padding-inline: 12px;
		}
	}
</style>
