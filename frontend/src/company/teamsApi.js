import { apiRequest } from "../api";

// Sales teams (SOS-P1-18) and the team report. A Company Admin manages teams, a Sales Manager reads
// the teams it manages and the report of its own team.
const call = (method, params = {}) =>
	apiRequest({ url: `/api/method/${method}`, method: "POST", params });

export const teamsApi = {
	list: () => call("sellos.access.teams.list_teams"),
	save: (values, name = null) => call("sellos.access.teams.save_team", { name, values }),
	remove: (name) => call("sellos.access.teams.delete_team", { name }),
	report: () => call("sellos.reports.team.team_report"),
	reassign: (lead, assignedTo) =>
		call("sellos.crm.api.reassign_lead", { lead, assigned_to: assignedTo }),
};
