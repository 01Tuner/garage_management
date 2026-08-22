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
				item_group: "Key Replacement Items",
			},
		}));
		frm.set_query("repair_asset", "part_results", () => ({
			filters: { disabled: 0 },
		}));
	},

	refresh(frm) {
		if (frm.doc.service_request) {
			frm.add_custom_button(__("Open Service Request"), () => {
				frappe.set_route("Form", "Service Request", frm.doc.service_request);
			});
		}
		if (!frm.is_new()) {
			frm.add_custom_button(__("Inspection Report"), () => {
				window.open(
					frappe.urllib.get_full_url(
						"/printview?doctype=Inspection&name=" +
							encodeURIComponent(frm.doc.name) +
							"&format=" +
							encodeURIComponent("Inspection Report") +
							"&no_letterhead=0"
					),
					"_blank"
				);
			}, __("Print"));
		}
		if (!frm.is_new() && frm.doc.status !== "Cancelled") {
			frm.add_custom_button(__("Create Repair Job"), () => {
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
			});
		}
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
});
