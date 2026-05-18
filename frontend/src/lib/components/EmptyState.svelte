<script lang="ts">
	let {
		title,
		compact = false
	}: {
		title: string;
		compact?: boolean;
	} = $props();
</script>

<div class="empty-state" class:compact>
	<span>{title}</span>
</div>

<style>
	.empty-state {
		display: grid;
		min-height: 180px;
		place-items: center;
		border: 1px dashed rgba(255, 255, 255, 0.14);
		border-radius: 10px;
		color: #aeb5b0;
	}

	.empty-state.compact {
		min-height: 132px;
	}
</style>
