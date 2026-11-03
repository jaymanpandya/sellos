<template>
	<div class="max-w-2xl">
		<h1 class="text-2xl font-semibold text-ink">
			Welcome{{ session.fullName ? ", " + session.fullName : "" }}
		</h1>
		<p class="mt-2 text-ink-muted">
			This is the SellOS app shell. Each role sees its own screens as they are built.
		</p>
	</div>
</template>

<script setup>
import { session } from "../session";
</script>
