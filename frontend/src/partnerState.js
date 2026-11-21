import { reactive } from "vue";

import { partnersApi } from "./company/partnersApi";

// What the signed in partner's firm allows (SOS-P7-01). A partner whose firm is not Approved is sent to the
// firm page, which says why. A login with no firm is an older partner login and is not held back.
export const partnerState = reactive({ loaded: false, status: null });

export function setPartnerFirm(firm) {
	partnerState.status = firm ? firm.status : null;
	partnerState.loaded = true;
}

export async function loadPartnerState(force = false) {
	if (partnerState.loaded && !force) return partnerState;
	try {
		setPartnerFirm((await partnersApi.mine()).firm);
	} catch {
		partnerState.status = null;
		partnerState.loaded = true;
	}
	return partnerState;
}

export const partnerMayWork = () =>
	partnerState.status === null || partnerState.status === "Approved";
