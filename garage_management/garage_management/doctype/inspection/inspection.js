// Copyright (c) 2026, rafeeq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Inspection", {
	setup(frm) {
		frm.set_query("findings", () => ({
			filters: { disabled: 0 },
		}));
		frm.set_query("key_replacement_items", () => ({
			filters: {
				disabled: 0,
				is_sales_item: 1,
				item_group: ["in", ["Key Replacement Items", "Spare Parts"]],
			},
		}));
		frm.set_query("repair_asset", "part_results", () => ({
			filters: { disabled: 0 },
		}));
	},

	refresh(frm) {
		if (frm.is_new()) return;

		// --- VIEW MENU ---
		if (frm.doc.service_request) {
			frm.add_custom_button(__("Service Request"), () => {
				frappe.set_route("Form", "Service Request", frm.doc.service_request);
			}, __("View"));
		}

		frm.add_custom_button(__("Repair Jobs"), () => {
			frappe.set_route("List", "Repair Job", { inspection: frm.doc.name });
		}, __("View"));

		// --- CREATE MENU ---
		if (frm.doc.service_request) {
			frm.add_custom_button(__("Quotation"), () => {
				frappe.call({
					method: "garage_management.api.service_request.create_quotation",
					args: { service_request: frm.doc.service_request },
					freeze: true,
					callback(r) {
						if (!r.message) return;
						frappe.show_alert({ message: __("Quotation {0} created as Draft", [r.message]), indicator: "green" });
						frappe.set_route("Form", "Quotation", r.message);
					},
				});
			}, __("Create"));
		}

		if (frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Repair Job"), () => {
				frappe.prompt(
					[
						{
							fieldname: "assigned_to",
							label: __("Assign To"),
							fieldtype: "Link",
							options: "User",
							reqd: 1,
							default: frm.doc.assigned_to || frappe.session.user,
						},
					],
					(values) => {
						frm.call({
							doc: frm.doc,
							method: "create_repair_job",
							args: { assigned_to: values.assigned_to },
							freeze: true,
							callback(r) {
								if (!r.message) return;
								frappe.set_route("Form", "Repair Job", r.message);
							},
						});
					},
					__("Create Repair Job")
				);
			}, __("Create"));
		}

		// --- ACTIONS MENU ---
		if (frm.doc.status !== "Completed" && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Complete Inspection"), () => {
				frm.call({
					doc: frm.doc,
					method: "complete_inspection",
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		if (frm.doc.service_request) {
			frm.add_custom_button(__("Sync Items to Billing"), () => {
				frm.call({
					doc: frm.doc,
					method: "sync_to_billing",
					freeze: true,
					callback() {
						frappe.show_alert({ message: __("Inspection items synced to Service Request billing"), indicator: "green" });
					},
				});
			}, __("Actions"));
		}

		// --- PRINT MENU ---
		frm.add_custom_button(__("Inspection Report"), () => {
			const lh = frm.doc.letter_head || frappe.defaults.get_default("letter_head") || "";
			let url =
				"/printview?doctype=Inspection&name=" +
				encodeURIComponent(frm.doc.name) +
				"&format=" +
				encodeURIComponent("Inspection Report") +
				"&no_letterhead=0";
			if (lh) url += "&letterhead=" + encodeURIComponent(lh);
			window.open(frappe.urllib.get_full_url(url), "_blank");
		}, __("Print"));
	},

	service_request(frm) {
		if (!frm.doc.service_request || (frm.doc.part_results || []).length) return;
		frappe.db.get_doc("Service Request", frm.doc.service_request).then((sr) => {
			(sr.components || []).forEach((row) => {
				frm.add_child("part_results", {
					repair_asset: row.repair_asset,
					serial_number: row.serial_number,
					make_type: row.make_type,
					part_no: row.part_no,
				});
			});
			frm.refresh_field("part_results");
		});
	},
	before_save(frm) {
		(frm.doc.photos || []).forEach((row) => {
			row.stage = "Inspection";
		});
	},
});

frappe.ui.form.on("Service Job Photo", {
	photos_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "stage", "Inspection");
	},
	form_render(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "stage", "Inspection");
	},
});
