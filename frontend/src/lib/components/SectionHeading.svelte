<script lang="ts">
	let {
		title,
		subtitle
	}: {
		title: string;
		subtitle?: string;
	} = $props();
</script>

<div class="section-heading">
	<h1>{title}</h1>
	{#if subtitle}
		<p>{subtitle}</p>
	{/if}
</div>

<style>
	.section-heading h1,
	.section-heading p {
		margin: 0;
	}

	.section-heading h1 {
		font-size: clamp(1.8rem, 3vw, 2.45rem);
		line-height: 1.1;
	}

	.section-heading p {
		margin-top: 10px;
		color: #c5cbc7;
		font-size: 1.02rem;
	}
</style>
