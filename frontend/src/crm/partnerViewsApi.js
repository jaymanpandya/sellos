import { apiRequest } from "../api";

// The partner's own deals, earnings and QR code (SOS-P5-06). One whitelisted method that reads only the signed
// in partner's firm.
export const partnerViewsApi = {
	overview: () =>
		apiRequest({
			url: "/api/method/sellos.crm.partner_views.partner_overview",
			method: "POST",
		}),
};
