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
		frm.set_df_property("inspection_status", "read_only", 1);

		if (frm.is_new()) return;

		// --- VIEW MENU ---
		if (frm.doc.service_request) {
			frm.add_custom_button(__("Service Request"), () => {
				frappe.set_route("Form", "Service Request", frm.doc.service_request);
			}, __("View"));
		}
		if (frm.doc.inspection) {
			frm.add_custom_button(__("Inspection"), () => {
				frappe.set_route("Form", "Inspection", frm.doc.inspection);
			}, __("View"));
		}

		// --- ACTIONS MENU ---
		if (frm.doc.status === "Draft") {
			frm.add_custom_button(__("Start Work"), () => {
				frm.call({
					doc: frm.doc,
					method: "start_work",
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		if (frm.doc.status === "In Progress") {
			frm.add_custom_button(__("Send for Testing"), () => {
				frm.call({
					doc: frm.doc,
					method: "send_to_testing",
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		if (frm.doc.status === "In Progress" || frm.doc.status === "Testing") {
			frm.add_custom_button(__("Mark Completed"), () => {
				frm.call({
					doc: frm.doc,
					method: "mark_completed",
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		frm.add_custom_button(__("Load Job Type QC"), () => frm.trigger("load_job_type_defaults"), __("Actions"));

		// --- PRINT MENU ---
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
	before_save(frm) {
		(frm.doc.photos || []).forEach((row) => {
			row.stage = "Completion";
		});
	},
});

frappe.ui.form.on("Service Job Photo", {
	photos_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "stage", "Completion");
	},
	form_render(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "stage", "Completion");
	},
});
