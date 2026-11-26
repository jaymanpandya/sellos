<template>
	<StatusBadge
		:tone="TONES[status] || 'neutral'"
		:label="status"
		data-testid="sellos-signing-status"
		:data-status="status"
	/>
</template>

<script setup>
// The state of a mandate's electronic signing: Not sent, Sent, Viewed, Signed, Signed offline (an uploaded copy), Declined or Expired.
import StatusBadge from "./StatusBadge.vue";

defineProps({ status: { type: String, default: "Not sent" } });
const TONES = {
	"Not sent": "neutral",
	Sent: "info",
	Viewed: "info",
	Signed: "success",
	"Signed offline": "success",
	Declined: "danger",
	Expired: "warning",
};
</script>
