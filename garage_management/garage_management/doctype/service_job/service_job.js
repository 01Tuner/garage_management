// Copyright (c) 2026, rafeeq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Job", {
	setup(frm) {
		frm.set_query("contact_person", () => {
			if (!frm.doc.customer) {
				return { filters: { name: "" } };
			}
			return {
				query: "frappe.contacts.doctype.contact.contact.contact_query",
				filters: {
					link_doctype: "Customer",
					link_name: frm.doc.customer,
				},
			};
		});
		frm.set_query("repair_asset", "components", () => ({
			filters: { disabled: 0 },
		}));
		// Table MultiSelect has no grid — set_query on the parent field (extends Link)
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
	},

	refresh(frm) {
		frm.trigger("render_commercial_panel");
		frm.trigger("toggle_buttons");
		if (frm._focus_commercial_tab) {
			frm._focus_commercial_tab = false;
			frm.layout?.select_tab?.("commercial_tab");
		}
	},

	customer(frm) {
		if (!frm.doc.customer) {
			frm.set_value("contact_person", null);
			return;
		}
		frappe.db.get_value("Customer", frm.doc.customer, "customer_primary_contact", (r) => {
			if (r && r.customer_primary_contact && !frm.doc.contact_person) {
				frm.set_value("contact_person", r.customer_primary_contact);
			}
		});
	},

	contact_person(frm) {
		if (!frm.doc.contact_person) return;
		frappe.db.get_value("Contact", frm.doc.contact_person, "mobile_no", (r) => {
			if (r && r.mobile_no && !frm.doc.mobile_no) {
				frm.set_value("mobile_no", r.mobile_no);
			}
		});
	},

	job_type(frm) {
		if (frm.doc.job_type && !frm.doc.billing_items?.length) {
			frm.trigger("load_job_type_defaults");
		}
	},

	async load_job_type_defaults(frm) {
		if (!frm.doc.job_type) {
			frappe.msgprint(__("Select a Job Type first"));
			return;
		}
		await frm.call("load_job_type_defaults");
		frm.refresh_fields(["billing_items", "qc_items", "billing_total"]);
		frappe.show_alert({ message: __("Job Type defaults loaded"), indicator: "green" });
	},

	render_commercial_panel(frm) {
		const wrap = frm.fields_dict.commercial_html?.$wrapper;
		if (!wrap) return;

		const rows = [
			{
				label: __("Quotation"),
				doctype: "Quotation",
				name: frm.doc.quotation,
			},
			{
				label: __("Sales Order"),
				doctype: "Sales Order",
				name: frm.doc.sales_order,
			},
			{
				label: __("Sales Invoice"),
				doctype: "Sales Invoice",
				name: frm.doc.sales_invoice,
			},
		];

		const bill = format_currency(frm.doc.billing_total || 0, frappe.defaults.get_default("currency"));

		let body = rows
			.map((row) => {
				if (row.name) {
					const href = frappe.utils.get_form_link(row.doctype, row.name);
					return `<tr>
						<td><b>${row.label}</b></td>
						<td><a href="${href}" class="garage-related-doc">${frappe.utils.escape_html(row.name)}</a></td>
						<td><button class="btn btn-xs btn-default garage-open-doc" data-doctype="${row.doctype}" data-name="${frappe.utils.escape_html(row.name)}">${__("Open")}</button></td>
					</tr>`;
				}
				return `<tr>
					<td><b>${row.label}</b></td>
					<td class="text-muted">${__("Not created")}</td>
					<td></td>
				</tr>`;
			})
			.join("");

		wrap.html(`
			<div class="garage-commercial-panel" style="margin-bottom:12px;padding:12px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
				<div style="margin-bottom:8px;"><b>${__("Billing Total")}:</b> ${bill}</div>
				<table class="table table-bordered" style="margin:0;">
					<tbody>${body}</tbody>
				</table>
				<p class="text-muted small" style="margin:8px 0 0;">
					${__("Use Create → Quotation / Sales Order / Sales Invoice from the toolbar.")}
				</p>
			</div>
		`);

		wrap.find(".garage-open-doc").on("click", (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
		});
	},

	toggle_buttons(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Load Job Type Defaults"), () => frm.trigger("load_job_type_defaults"), __("Actions"));

		if (frm.doc.quotation) {
			frm.add_custom_button(__("Open Quotation"), () => {
				frappe.set_route("Form", "Quotation", frm.doc.quotation);
			}, __("Related"));
		}
		if (frm.doc.sales_order) {
			frm.add_custom_button(__("Open Sales Order"), () => {
				frappe.set_route("Form", "Sales Order", frm.doc.sales_order);
			}, __("Related"));
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Open Sales Invoice"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			}, __("Related"));
		}

		if (!frm.doc.quotation) {
			frm.add_custom_button(
				__("Create Quotation"),
				() => {
					frappe.call({
						method: "garage_management.api.service_job.create_quotation",
						args: { service_job: frm.doc.name },
						freeze: true,
						callback(r) {
							if (!r.message) return;
							after_commercial_created(frm, "Quotation", r.message);
						},
					});
				},
				__("Create")
			);
		}

		if (frm.doc.quotation && !frm.doc.sales_order) {
			frm.add_custom_button(
				__("Create Sales Order"),
				() => {
					frappe.call({
						method: "garage_management.api.service_job.create_sales_order",
						args: { service_job: frm.doc.name },
						freeze: true,
						callback(r) {
							if (!r.message) return;
							after_commercial_created(frm, "Sales Order", r.message);
						},
					});
				},
				__("Create")
			);
		}

		if ((frm.doc.sales_order || frm.doc.quotation) && !frm.doc.sales_invoice) {
			frm.add_custom_button(
				__("Create Sales Invoice"),
				() => {
					frappe.call({
						method: "garage_management.api.service_job.create_sales_invoice",
						args: { service_job: frm.doc.name },
						freeze: true,
						callback(r) {
							if (!r.message) return;
							after_commercial_created(frm, "Sales Invoice", r.message);
						},
					});
				},
				__("Create")
			);
		}

		if (frm.doc.status === "Quoted" || frm.doc.status === "Awaiting Approval") {
			frm.add_custom_button(__("Mark Customer Approved"), () => {
				frappe.call({
					method: "garage_management.api.service_job.mark_customer_approved",
					args: { service_job: frm.doc.name },
					freeze: true,
					callback() {
						frm._focus_commercial_tab = true;
						frm.reload_doc();
					},
				});
			});
		}
	},
});

function after_commercial_created(frm, doctype, name) {
	frappe.show_alert({
		message: __("{0} {1} created", [doctype, name]),
		indicator: "green",
	});
	frm._focus_commercial_tab = true;
	frm.reload_doc().then(() => {
		frappe.msgprint({
			title: __("{0} Created", [doctype]),
			message: __("Linked on this Service Job. Open {0}?", [name]),
			primary_action: {
				label: __("Open {0}", [doctype]),
				action() {
					frappe.set_route("Form", doctype, name);
				},
			},
		});
	});
}

frappe.ui.form.on("Service Job Billing Item", {
	qty(frm, cdt, cdn) {
		calc_amount(frm, cdt, cdn);
	},
	rate(frm, cdt, cdn) {
		calc_amount(frm, cdt, cdn);
	},
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;
		frappe.db.get_value("Item", row.item_code, ["item_name", "description", "is_stock_item"], (r) => {
			if (!r) return;
			frappe.model.set_value(cdt, cdn, "item_name", r.item_name);
			frappe.model.set_value(cdt, cdn, "description", r.description);
			frappe.model.set_value(cdt, cdn, "is_stock_item", r.is_stock_item);
			calc_amount(frm, cdt, cdn);
		});
	},
});

function calc_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	let total = 0;
	(frm.doc.billing_items || []).forEach((d) => {
		total += flt(d.amount);
	});
	frm.set_value("billing_total", total);
}
