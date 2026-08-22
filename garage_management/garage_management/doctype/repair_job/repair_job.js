// Copyright (c) 2026, rafeeq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Repair Job", {
	setup(frm) {
		frm.set_query("inspection", () => {
			if (!frm.doc.service_request) {
				return { filters: { name: "" } };
			}
			return { filters: { service_request: frm.doc.service_request } };
		});
	},

	refresh(frm) {
		if (frm.doc.service_request) {
			frm.add_custom_button(__("Open Service Request"), () => {
				frappe.set_route("Form", "Service Request", frm.doc.service_request);
			});
		}
		if (frm.doc.inspection) {
			frm.add_custom_button(__("Open Inspection"), () => {
				frappe.set_route("Form", "Inspection", frm.doc.inspection);
			});
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Load Job Type QC"), () => frm.trigger("load_job_type_defaults"));
			frm.add_custom_button(__("Job Repair Report"), () => {
				window.open(
					frappe.urllib.get_full_url(
						"/printview?doctype=" +
							encodeURIComponent("Repair Job") +
							"&name=" +
							encodeURIComponent(frm.doc.name) +
							"&format=" +
							encodeURIComponent("Job Repair Report") +
							"&no_letterhead=0"
					),
					"_blank"
				);
			}, __("Print"));
		}
	},

	job_type(frm) {
		if (frm.doc.job_type && !frm.doc.qc_items?.length) {
			frm.trigger("load_job_type_defaults");
		}
	},

	async load_job_type_defaults(frm) {
		if (!frm.doc.job_type) {
			frappe.msgprint(__("Select a Job Type first"));
			return;
		}
		await frm.call("load_job_type_defaults");
		frm.refresh_field("qc_items");
		frappe.show_alert({ message: __("QC checklist loaded"), indicator: "green" });
	},
});
