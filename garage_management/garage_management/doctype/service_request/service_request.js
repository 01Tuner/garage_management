// Copyright (c) 2026, rafeeq and contributors
// For license information, please see license.txt

frappe.ui.form.on("Service Request", {
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
	},

	refresh(frm) {
		frm.set_df_property("contact_details", "read_only", 1);
		frm.set_df_property("customer_address", "read_only", 1);
		frm.set_df_property("inspection_status", "read_only", 1);
		frm.set_df_property("repair_status", "read_only", 1);
		frm.trigger("render_inspection_panel");
		frm.trigger("render_quotation_panel");
		frm.trigger("render_repair_jobs_panel");
		frm.trigger("render_invoice_panel");
		frm.trigger("toggle_buttons");

		if (frm.doc.customer && (!frm.doc.customer_address || !frm.doc.contact_details)) {
			frm.trigger("fetch_customer_details");
		}

		if (frm._focus_tab) {
			const targetTab = frm._focus_tab;
			frm._focus_tab = null;
			frm.layout?.select_tab?.(targetTab);
		}
	},

	before_save(frm) {
		(frm.doc.photos || []).forEach((row) => {
			row.stage = "Receiving";
		});
	},

	customer(frm) {
		if (!frm.doc.customer) {
			frm.set_value("contact_person", null);
			frm.set_value("mobile_no", "");
			frm.set_value("contact_details", "");
			frm.set_value("customer_address", "");
			return;
		}
		frm.trigger("fetch_customer_details");
	},

	fetch_customer_details(frm) {
		if (!frm.doc.customer) return;
		frappe.call({
			method: "garage_management.api.service_request.get_customer_contact_and_address",
			args: { customer: frm.doc.customer },
			callback(r) {
				const data = r.message || {};
				frm.set_value("contact_details", data.contact_details || "");
				frm.set_value("customer_address", data.address_display || "");
				if (data.contact_person) {
					frm.set_value("contact_person", data.contact_person);
				}
				if (data.mobile_no) {
					frm.set_value("mobile_no", data.mobile_no);
				}
			},
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
		frm.refresh_fields(["billing_items", "billing_total"]);
		frappe.show_alert({ message: __("Job Type billing defaults loaded"), indicator: "green" });
	},

	render_inspection_panel(frm) {
		const wrap = frm.fields_dict.inspection_html?.$wrapper || frm.fields_dict.tracking_html?.$wrapper;
		if (!wrap) return;
		if (frm.is_new()) {
			wrap.html(`<p class="text-muted" style="padding:10px;">${__("Save the Service Request to record Inspections.")}</p>`);
			return;
		}

		frappe.call({
			method: "garage_management.api.service_request.get_workshop_docs",
			args: { service_request: frm.doc.name },
			callback(r) {
				const data = r.message || { inspections: [], repair_jobs: [] };
				if (data.inspection_status && frm.doc.inspection_status !== data.inspection_status) {
					frm.set_value("inspection_status", data.inspection_status);
				}
				if (data.repair_status && frm.doc.repair_status !== data.repair_status) {
					frm.set_value("repair_status", data.repair_status);
				}
				const inspections = data.inspections || [];
				let rows = inspections
					.map(
						(d) => `<tr>
							<td><a href="${frappe.utils.get_form_link("Inspection", d.name)}"><b>${frappe.utils.escape_html(d.name)}</b></a></td>
							<td><span class="indicator-pill ${status_color(d.status)}">${frappe.utils.escape_html(d.status || "Draft")}</span></td>
							<td>${frappe.utils.escape_html(d.assigned_to || "")}</td>
							<td class="text-right">
								<button class="btn btn-xs btn-default garage-open-doc" data-doctype="Inspection" data-name="${frappe.utils.escape_html(d.name)}">${__("Open")}</button>
								<button class="btn btn-xs btn-default garage-print-doc" data-doctype="Inspection" data-name="${frappe.utils.escape_html(d.name)}" data-format="Inspection Report">${__("Print")}</button>
							</td>
						</tr>`
					)
					.join("");

				if (!rows) {
					rows = `<tr><td colspan="4" class="text-muted text-center" style="padding:16px;">${__("No Inspections recorded yet. Click 'Create Inspection' to start.")}</td></tr>`;
				}

				wrap.html(`
					<div class="garage-panel" style="margin-bottom:12px;padding:12px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
						<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
							<h5 style="margin:0;">${__("Inspection Records")}</h5>
							<button class="btn btn-xs btn-primary garage-new-insp">${__("Create Inspection")}</button>
						</div>
						<table class="table table-bordered" style="margin:0;background:var(--card-bg);">
							<thead><tr><th>${__("Inspection ID")}</th><th>${__("Status")}</th><th>${__("Assigned To")}</th><th style="width:140px;"></th></tr></thead>
							<tbody>${rows}</tbody>
						</table>
					</div>
				`);

				wrap.find(".garage-open-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
				});
				wrap.find(".garage-print-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					open_print($btn.data("doctype"), $btn.data("name"), $btn.data("format"));
				});
				wrap.find(".garage-new-insp").on("click", (e) => {
					e.preventDefault();
					prompt_assignee(frm, "inspection");
				});
			},
		});
	},

	render_quotation_panel(frm) {
		const wrap = frm.fields_dict.quotation_html?.$wrapper;
		if (!wrap) return;

		const bill = format_currency(frm.doc.billing_total || 0, frappe.defaults.get_default("currency"));
		let quoteStatusHtml = "";

		if (frm.doc.quotation) {
			const href = frappe.utils.get_form_link("Quotation", frm.doc.quotation);
			quoteStatusHtml = `
				<div style="display:flex;justify-content:space-between;align-items:center;">
					<div>
						<b>${__("Linked Quotation")}:</b> <a href="${href}" style="font-weight:600;">${frappe.utils.escape_html(frm.doc.quotation)}</a>
						<span style="margin-left:8px;" class="indicator-pill green">${__("Linked")}</span>
					</div>
					<div>
						<button class="btn btn-xs btn-default garage-open-doc" data-doctype="Quotation" data-name="${frappe.utils.escape_html(frm.doc.quotation)}">${__("Open Quotation")}</button>
					</div>
				</div>
			`;
		} else {
			quoteStatusHtml = `
				<div style="display:flex;justify-content:space-between;align-items:center;">
					<span class="text-muted">${__("Quotation not created yet. Add billing items below or click Create Quotation.")}</span>
					<div>
						<button class="btn btn-xs btn-primary garage-create-quote">${__("Create Quotation")}</button>
					</div>
				</div>
			`;
		}

		wrap.html(`
			<div class="garage-panel" style="margin-bottom:12px;padding:12px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
				<div style="margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;">
					<div><b>${__("Estimated Billing Total")}:</b> <span class="h5 text-primary" style="margin:0 0 0 6px;">${bill}</span></div>
					<div>
						<button class="btn btn-xs btn-default garage-sync-insp" style="margin-right:6px;">${__("Sync Items from Inspection")}</button>
						<button class="btn btn-xs btn-default garage-load-defaults">${__("Load Job Type Defaults")}</button>
					</div>
				</div>
				<hr style="margin:8px 0;"/>
				${quoteStatusHtml}
			</div>
		`);

		wrap.find(".garage-open-doc").on("click", (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
		});
		wrap.find(".garage-create-quote").on("click", (e) => {
			e.preventDefault();
			frappe.call({
				method: "garage_management.api.service_request.create_quotation",
				args: { service_request: frm.doc.name },
				freeze: true,
				callback(r) {
					if (!r.message) return;
					after_commercial_created(frm, "Quotation", r.message);
				},
			});
		});
		wrap.find(".garage-sync-insp").on("click", (e) => {
			e.preventDefault();
			frappe.call({
				method: "garage_management.api.service_request.sync_inspection_items_to_billing",
				args: { service_request: frm.doc.name },
				freeze: true,
				callback() {
					frm.reload_doc();
				},
			});
		});
		wrap.find(".garage-load-defaults").on("click", (e) => {
			e.preventDefault();
			frm.trigger("load_job_type_defaults");
		});
	},

	render_repair_jobs_panel(frm) {
		const wrap = frm.fields_dict.repair_jobs_html?.$wrapper;
		if (!wrap) return;
		if (frm.is_new()) {
			wrap.html(`<p class="text-muted" style="padding:10px;">${__("Save the Service Request to create Repair Jobs.")}</p>`);
			return;
		}

		frappe.call({
			method: "garage_management.api.service_request.get_workshop_docs",
			args: { service_request: frm.doc.name },
			callback(r) {
				const data = r.message || { inspections: [], repair_jobs: [] };
				const jobs = data.repair_jobs || [];
				let rows = jobs
					.map(
						(d) => `<tr>
							<td><a href="${frappe.utils.get_form_link("Repair Job", d.name)}"><b>${frappe.utils.escape_html(d.name)}</b></a></td>
							<td><span class="indicator-pill ${status_color(d.status)}">${frappe.utils.escape_html(d.status || "Draft")}</span></td>
							<td>${frappe.utils.escape_html(d.assigned_to || "")}</td>
							<td>${frappe.utils.escape_html(d.job_type || "")}</td>
							<td class="text-right">
								<button class="btn btn-xs btn-default garage-open-doc" data-doctype="Repair Job" data-name="${frappe.utils.escape_html(d.name)}">${__("Open")}</button>
								<button class="btn btn-xs btn-default garage-print-doc" data-doctype="Repair Job" data-name="${frappe.utils.escape_html(d.name)}" data-format="Job Repair Report">${__("Print")}</button>
							</td>
						</tr>`
					)
					.join("");

				if (!rows) {
					rows = `<tr><td colspan="5" class="text-muted text-center" style="padding:16px;">${__("No Repair Jobs created yet. Click 'Create Repair Job' to assign work.")}</td></tr>`;
				}

				wrap.html(`
					<div class="garage-panel" style="margin-bottom:12px;padding:12px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
						<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
							<h5 style="margin:0;">${__("Repair Jobs & Work Orders")}</h5>
							<button class="btn btn-xs btn-primary garage-new-job">${__("Create Repair Job")}</button>
						</div>
						<table class="table table-bordered" style="margin:0;background:var(--card-bg);">
							<thead><tr><th>${__("Repair Job")}</th><th>${__("Status")}</th><th>${__("Assigned To")}</th><th>${__("Job Type")}</th><th style="width:140px;"></th></tr></thead>
							<tbody>${rows}</tbody>
						</table>
					</div>
				`);

				wrap.find(".garage-open-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
				});
				wrap.find(".garage-print-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					open_print($btn.data("doctype"), $btn.data("name"), $btn.data("format"));
				});
				wrap.find(".garage-new-job").on("click", (e) => {
					e.preventDefault();
					prompt_assignee(frm, "repair_job");
				});
			},
		});
	},

	render_invoice_panel(frm) {
		const wrap = frm.fields_dict.invoice_html?.$wrapper || frm.fields_dict.commercial_html?.$wrapper;
		if (!wrap) return;

		const rows = [
			{ label: __("Quotation"), doctype: "Quotation", name: frm.doc.quotation },
			{ label: __("Sales Order"), doctype: "Sales Order", name: frm.doc.sales_order },
			{ label: __("Sales Invoice"), doctype: "Sales Invoice", name: frm.doc.sales_invoice },
		];

		const bill = format_currency(frm.doc.billing_total || 0, frappe.defaults.get_default("currency"));

		let body = rows
			.map((row) => {
				if (row.name) {
					const href = frappe.utils.get_form_link(row.doctype, row.name);
					return `<tr>
						<td><b>${row.label}</b></td>
						<td><a href="${href}" class="garage-related-doc">${frappe.utils.escape_html(row.name)}</a></td>
						<td class="text-right"><button class="btn btn-xs btn-default garage-open-doc" data-doctype="${row.doctype}" data-name="${frappe.utils.escape_html(row.name)}">${__("Open")}</button></td>
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
			<div class="garage-panel" style="margin-bottom:12px;padding:12px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
				<div style="margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;">
					<div><b>${__("Billing Total")}:</b> <span class="h5 text-primary" style="margin:0 0 0 6px;">${bill}</span></div>
					<div>
						${!frm.doc.sales_invoice ? `<button class="btn btn-xs btn-primary garage-create-invoice">${__("Create Sales Invoice")}</button>` : ""}
					</div>
				</div>
				<table class="table table-bordered" style="margin:0;background:var(--card-bg);">
					<tbody>${body}</tbody>
				</table>
			</div>
		`);

		wrap.find(".garage-open-doc").on("click", (e) => {
			e.preventDefault();
			const $btn = $(e.currentTarget);
			frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
		});
		wrap.find(".garage-create-invoice").on("click", (e) => {
			e.preventDefault();
			frappe.call({
				method: "garage_management.api.service_request.create_sales_invoice",
				args: { service_request: frm.doc.name },
				freeze: true,
				callback(r) {
					if (!r.message) return;
					after_commercial_created(frm, "Sales Invoice", r.message);
				},
			});
		});
	},

	toggle_buttons(frm) {
		if (frm.is_new()) return;

		// --- CREATE MENU ---
		frm.add_custom_button(__("Inspection"), () => prompt_assignee(frm, "inspection"), __("Create"));

		if (!frm.doc.quotation) {
			frm.add_custom_button(
				__("Quotation"),
				() => {
					frappe.call({
						method: "garage_management.api.service_request.create_quotation",
						args: { service_request: frm.doc.name },
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

		frm.add_custom_button(__("Repair Job"), () => prompt_assignee(frm, "repair_job"), __("Create"));

		if (frm.doc.quotation && !frm.doc.sales_order) {
			frm.add_custom_button(
				__("Sales Order"),
				() => {
					frappe.call({
						method: "garage_management.api.service_request.create_sales_order",
						args: { service_request: frm.doc.name },
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

		if (!frm.doc.sales_invoice) {
			frm.add_custom_button(
				__("Sales Invoice"),
				() => {
					frappe.call({
						method: "garage_management.api.service_request.create_sales_invoice",
						args: { service_request: frm.doc.name },
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

		// --- VIEW MENU ---
		if (frm.doc.quotation) {
			frm.add_custom_button(__("Quotation"), () => {
				frappe.set_route("Form", "Quotation", frm.doc.quotation);
			}, __("View"));
		}
		if (frm.doc.sales_order) {
			frm.add_custom_button(__("Sales Order"), () => {
				frappe.set_route("Form", "Sales Order", frm.doc.sales_order);
			}, __("View"));
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Sales Invoice"), () => {
				frappe.set_route("Form", "Sales Invoice", frm.doc.sales_invoice);
			}, __("View"));
		}
		frm.add_custom_button(__("Inspections"), () => {
			frappe.set_route("List", "Inspection", { service_request: frm.doc.name });
		}, __("View"));
		frm.add_custom_button(__("Repair Jobs"), () => {
			frappe.set_route("List", "Repair Job", { service_request: frm.doc.name });
		}, __("View"));

		// --- ACTIONS MENU ---
		if (frm.doc.status === "Quoted" || frm.doc.status === "Awaiting Approval" || frm.doc.quotation) {
			frm.add_custom_button(__("Mark Customer Approved"), () => {
				frappe.call({
					method: "garage_management.api.service_request.mark_customer_approved",
					args: { service_request: frm.doc.name },
					freeze: true,
					callback() {
						frm._focus_tab = "repair_jobs_tab";
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		frm.add_custom_button(__("Sync Items from Inspection"), () => {
			frappe.call({
				method: "garage_management.api.service_request.sync_inspection_items_to_billing",
				args: { service_request: frm.doc.name },
				freeze: true,
				callback() {
					frm.reload_doc();
				},
			});
		}, __("Actions"));

		frm.add_custom_button(__("Load Job Type Defaults"), () => frm.trigger("load_job_type_defaults"), __("Actions"));

		if (frm.doc.status === "In Progress" || frm.doc.status === "Testing") {
			frm.add_custom_button(__("Mark Service Completed"), () => {
				frappe.call({
					method: "garage_management.api.service_request.mark_service_completed",
					args: { service_request: frm.doc.name },
					freeze: true,
					callback() {
						frm._focus_tab = "invoice_tab";
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		if (frm.doc.status === "Completed" || frm.doc.status === "Invoiced") {
			frm.add_custom_button(__("Mark Delivered"), () => {
				frappe.call({
					method: "garage_management.api.service_request.mark_delivered",
					args: { service_request: frm.doc.name },
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		// --- PRINT MENU ---
		frm.add_custom_button(__("Job Report"), () => open_print("Service Request", frm.doc.name, "Job Report"), __("Print"));
		frm.add_custom_button(__("Receiving Report"), () => open_print("Service Request", frm.doc.name, "Receiving Report"), __("Print"));
		frm.add_custom_button(__("Inspection Report"), () => print_linked(frm, "Inspection", "Inspection Report"), __("Print"));
		frm.add_custom_button(__("Job Repair Report"), () => print_linked(frm, "Repair Job", "Job Repair Report"), __("Print"));
	},
});

function status_color(status) {
	const map = {
		Draft: "gray",
		"In Progress": "cyan",
		Testing: "purple",
		Completed: "green",
		Cancelled: "red",
	};
	return map[status] || "blue";
}

function prompt_assignee(frm, kind) {
	const title = kind === "inspection" ? __("Create Inspection") : __("Create Repair Job");
	const fields = [
		{
			fieldname: "assigned_to",
			fieldtype: "Link",
			options: "User",
			label: __("Assign To"),
			reqd: 1,
		},
	];
	if (kind === "repair_job") {
		fields.push({
			fieldname: "inspection",
			fieldtype: "Link",
			options: "Inspection",
			label: __("Inspection"),
			get_query: () => ({ filters: { service_request: frm.doc.name } }),
		});
	}
	frappe.prompt(fields, (values) => {
		const method =
			kind === "inspection"
				? "create_inspection"
				: "create_repair_job";
		frm.call({
			doc: frm.doc,
			method,
			args: values,
			freeze: true,
			callback(r) {
				if (!r.message) return;
				const dt = kind === "inspection" ? "Inspection" : "Repair Job";
				frappe.show_alert({ message: __("{0} {1} created", [dt, r.message]), indicator: "green" });
				frm.reload_doc().then(() => {
					frappe.set_route("Form", dt, r.message);
				});
			},
		});
	}, title);
}

function open_print(doctype, name, format) {
	const url = frappe.urllib.get_full_url(
		"/printview?doctype=" +
			encodeURIComponent(doctype) +
			"&name=" +
			encodeURIComponent(name) +
			"&format=" +
			encodeURIComponent(format) +
			"&no_letterhead=0"
	);
	window.open(url, "_blank");
}

function print_linked(frm, doctype, format) {
	const filters = { service_request: frm.doc.name };
	frappe.db.get_list(doctype, { filters, fields: ["name", "status"], order_by: "creation desc", limit: 20 }).then((rows) => {
		if (!rows.length) {
			frappe.msgprint(__("No {0} linked to this Service Request yet", [doctype]));
			return;
		}
		if (rows.length === 1) {
			open_print(doctype, rows[0].name, format);
			return;
		}
		frappe.prompt(
			[
				{
					fieldname: "name",
					label: doctype,
					fieldtype: "Select",
					options: rows.map((r) => r.name).join("\n"),
					reqd: 1,
					default: rows[0].name,
				},
			],
			(values) => open_print(doctype, values.name, format),
			__("Print {0}", [format])
		);
	});
}

function after_commercial_created(frm, doctype, name) {
	frappe.show_alert({
		message: __("{0} {1} created", [doctype, name]),
		indicator: "green",
	});
	frm._focus_tab = doctype === "Quotation" ? "quotation_tab" : "invoice_tab";
	frm.reload_doc().then(() => {
		frappe.msgprint({
			title: __("{0} Created", [doctype]),
			message: __("Linked on this Service Request. Open {0}?", [name]),
			primary_action: {
				label: __("Open {0}", [doctype]),
				action() {
					frappe.set_route("Form", doctype, name);
				},
			},
		});
	});
}

frappe.ui.form.on("Service Request Billing Item", {
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

frappe.ui.form.on("Service Job Photo", {
	photos_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "stage", "Receiving");
	},
	form_render(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "stage", "Receiving");
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
