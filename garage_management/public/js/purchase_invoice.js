// Copyright (c) 2026, rafeeq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Invoice", {
	setup(frm) {
		frm.set_query("service_request", () => {
			return {
				filters: {
					docstatus: ["<", 2],
				},
			};
		});

		frm.set_query("repair_job", () => {
			if (frm.doc.service_request) {
				return {
					filters: {
						service_request: frm.doc.service_request,
						status: ["!=", "Cancelled"],
					},
				};
			}
			return {
				filters: {
					status: ["!=", "Cancelled"],
				},
			};
		});

		frm.set_query("service_request", "items", () => {
			return {
				filters: {
					docstatus: ["<", 2],
				},
			};
		});

		frm.set_query("repair_job", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const sr = row.service_request || frm.doc.service_request;
			if (sr) {
				return {
					filters: {
						service_request: sr,
						status: ["!=", "Cancelled"],
					},
				};
			}
			return {
				filters: {
					status: ["!=", "Cancelled"],
				},
			};
		});
	},

	refresh(frm) {
		if (frm.doc.service_request) {
			frm.add_custom_button(__("Service Request"), () => {
				frappe.set_route("Form", "Service Request", frm.doc.service_request);
			}, __("View"));
		}
		if (frm.doc.repair_job) {
			frm.add_custom_button(__("Repair Job"), () => {
				frappe.set_route("Form", "Repair Job", frm.doc.repair_job);
			}, __("View"));
		}
	},

	service_request(frm) {
		if (!frm.doc.service_request) {
			return;
		}
		// If repair_job is set, verify it belongs to this service_request
		if (frm.doc.repair_job) {
			frappe.db.get_value("Repair Job", frm.doc.repair_job, "service_request").then((r) => {
				if (r?.message?.service_request && r.message.service_request !== frm.doc.service_request) {
					frm.set_value("repair_job", null);
				}
			});
		}
		// Propagate to child items if empty
		(frm.doc.items || []).forEach((item) => {
			if (!item.service_request) {
				frappe.model.set_value(item.doctype, item.name, "service_request", frm.doc.service_request);
			}
		});
	},

	repair_job(frm) {
		if (frm.doc.repair_job) {
			frappe.db.get_value("Repair Job", frm.doc.repair_job, "service_request").then((r) => {
				if (r?.message?.service_request && !frm.doc.service_request) {
					frm.set_value("service_request", r.message.service_request);
				}
			});
			(frm.doc.items || []).forEach((item) => {
				if (!item.repair_job) {
					frappe.model.set_value(item.doctype, item.name, "repair_job", frm.doc.repair_job);
				}
			});
		}
	},
});

frappe.ui.form.on("Purchase Invoice Item", {
	items_add(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (frm.doc.service_request && !row.service_request) {
			frappe.model.set_value(cdt, cdn, "service_request", frm.doc.service_request);
		}
		if (frm.doc.repair_job && !row.repair_job) {
			frappe.model.set_value(cdt, cdn, "repair_job", frm.doc.repair_job);
		}
	},
});
