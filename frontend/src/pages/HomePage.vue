<template>
	<div class="max-w-2xl" data-testid="sellos-home">
		<h1 class="text-2xl font-semibold text-ink" data-testid="sellos-home-welcome">
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
