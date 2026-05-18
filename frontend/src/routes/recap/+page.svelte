<script lang="ts">
	import EmptyState from '$lib/components/EmptyState.svelte';
</script>

<section class="recap-shell">
	<div class="recap-header">
		<p class="eyebrow">Recap</p>
		<h1>Listening recap</h1>
	</div>

	<EmptyState title="No recap data yet" />
</section>

<style>
	.recap-shell {
		display: grid;
		gap: 18px;
		padding: 28px 0 32px;
	}

	.recap-header h1 {
		margin: 8px 0 0;
		font-size: clamp(2rem, 4vw, 3.2rem);
	}
</style>
