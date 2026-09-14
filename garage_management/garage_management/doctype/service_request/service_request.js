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
		if (frm.doc.__onload?.default_letter_head) {
			frm.doc.letter_head = frm.doc.__onload.default_letter_head;
		}
		frm.set_df_property("contact_details", "read_only", 1);
		frm.set_df_property("customer_address", "read_only", 1);
		frm.set_df_property("inspection_status", "read_only", 1);
		frm.set_df_property("repair_status", "read_only", 1);
		frm.trigger("render_inspection_panel");
		frm.trigger("render_quotation_panel");
		frm.trigger("render_parts_panel");
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
						<button class="btn btn-xs btn-default text-danger garage-unlink-quote" data-name="${frappe.utils.escape_html(frm.doc.quotation)}" style="margin-left:4px;">${__("Unlink")}</button>
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
		wrap.find(".garage-unlink-quote").on("click", (e) => {
			e.preventDefault();
			frm.events.confirm_and_unlink(frm, "Quotation", frm.doc.quotation);
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

	render_parts_panel(frm) {
		const wrap = frm.fields_dict.parts_html?.$wrapper;
		if (!wrap) return;
		if (frm.is_new()) {
			wrap.html(`<p class="text-muted" style="padding:10px;">${__("Save the Service Request to track Parts & Procurement.")}</p>`);
			return;
		}

		frappe.call({
			method: "garage_management.api.purchase_invoice.get_service_request_procurement_summary",
			args: { service_request: frm.doc.name },
			callback(r) {
				const data = r.message || {};
				const parts = data.parts || [];
				const pos = data.purchase_orders || [];
				const pis = data.purchase_invoices || [];
				const so = data.sales_order || null;
				const currency = frappe.defaults.get_default("currency") || "";
				const readiness_pct = data.readiness_pct || 0;
				const ready_count = data.ready_count || 0;
				const total_parts = data.total_parts || 0;
				const is_all_ready = total_parts === 0 || ready_count >= total_parts;

				const progress_bar_class = readiness_pct === 100 ? "progress-bar-success" : (readiness_pct > 0 ? "progress-bar-info" : "progress-bar-warning");

				const current_po_no = frm.doc.customer_po_no || data.customer_po_no || "";
				const current_po_date = frm.doc.customer_po_date || data.customer_po_date || "";

				let po_display = "";
				if (current_po_no) {
					po_display = `
						<div style="display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;">
							<span class="badge badge-primary" style="font-size:12px;padding:4px 8px;letter-spacing:0.5px;">${frappe.utils.escape_html(current_po_no)}</span>
							${current_po_date ? `<span class="text-muted small">(${frappe.datetime.str_to_user(current_po_date)})</span>` : ""}
							<button class="btn btn-xs btn-default garage-edit-po" style="margin-left:4px;">${__("Edit PO")}</button>
						</div>
					`;
				} else {
					po_display = `
						<div style="display:inline-flex;align-items:center;gap:8px;">
							<span class="text-muted">${__("No PO reference")}</span>
							<button class="btn btn-xs btn-default garage-edit-po">${__("+ Add Customer PO")}</button>
						</div>
					`;
				}

				let so_display = "";
				if (so) {
					const so_link = frappe.utils.get_form_link("Sales Order", so.name);
					so_display = `
						<div style="display:inline-flex;align-items:center;gap:8px;flex-wrap:wrap;">
							<a href="${so_link}" class="garage-related-doc"><b>${frappe.utils.escape_html(so.name)}</b></a>
							<span class="indicator-pill ${so.docstatus === 1 ? "green" : "orange"}">${frappe.utils.escape_html(so.status || "")}</span>
							<span style="font-weight:600;">${format_currency(so.grand_total, currency)}</span>
						</div>
					`;
				} else if (frm.doc.quotation) {
					so_display = `
						<div style="display:inline-flex;align-items:center;gap:8px;">
							<span class="text-muted small">${__("Quotation approved. Ready for Sales Order.")}</span>
							<button class="btn btn-xs btn-primary garage-create-so">${__("Generate Sales Order")}</button>
						</div>
					`;
				} else {
					so_display = `<span class="text-muted small">${__("Create Quotation first before generating Sales Order.")}</span>`;
				}

				let parts_rows = "";
				if (parts.length) {
					parts_rows = parts.map((p) => {
						const is_stock_ok = flt(p.stock_available) >= flt(p.qty_required);
						const stock_badge = is_stock_ok
							? `<span class="indicator-pill green" style="font-weight:600;">${p.stock_available} ${frappe.utils.escape_html(p.uom)}</span>`
							: `<span class="indicator-pill red" style="font-weight:600;">${p.stock_available} ${frappe.utils.escape_html(p.uom)}</span>`;
						const status_badge = p.is_ready
							? `<span class="indicator-pill green">${__("Ready / Available")}</span>`
							: (p.po_ordered_qty > 0
								? `<span class="indicator-pill orange">${__("Ordered ({0})", [p.po_ordered_qty])}</span>`
								: `<span class="indicator-pill red">${__("Shortage / To Order")}</span>`);

						return `<tr>
							<td style="vertical-align:middle;">
								<b>${frappe.utils.escape_html(p.item_code)}</b>
								<div class="text-muted small">${frappe.utils.escape_html(p.item_name)}</div>
							</td>
							<td class="text-center" style="vertical-align:middle;"><b>${p.qty_required}</b> ${frappe.utils.escape_html(p.uom)}</td>
							<td class="text-center" style="vertical-align:middle;">${stock_badge}</td>
							<td class="text-center" style="vertical-align:middle;">${p.po_ordered_qty > 0 ? `<span class="indicator-pill blue">${p.po_ordered_qty}</span>` : `<span class="text-muted">0</span>`}</td>
							<td class="text-center" style="vertical-align:middle;">${p.pi_received_qty > 0 ? `<span class="indicator-pill green">${p.pi_received_qty}</span>` : `<span class="text-muted">0</span>`}</td>
							<td class="text-center" style="vertical-align:middle;">${status_badge}</td>
						</tr>`;
					}).join("");
				} else {
					parts_rows = `<tr><td colspan="6" class="text-muted text-center" style="padding:16px;">${__("No stock items/parts in billing list. Only labor or services required.")}</td></tr>`;
				}

				let po_rows = "";
				if (pos.length) {
					po_rows = pos.map((po) => {
						const href = frappe.utils.get_form_link("Purchase Order", po.name);
						const amt = format_currency(po.grand_total || 0, currency);
						return `<tr>
							<td style="vertical-align:middle;"><a href="${href}"><b>${frappe.utils.escape_html(po.name)}</b></a></td>
							<td style="vertical-align:middle;">${frappe.utils.escape_html(po.supplier || "")}</td>
							<td class="text-right" style="vertical-align:middle;"><b>${amt}</b></td>
							<td class="text-center" style="vertical-align:middle;"><span class="indicator-pill ${po.docstatus === 1 ? "green" : "orange"}">${frappe.utils.escape_html(po.status || "")}</span></td>
							<td class="text-right" style="vertical-align:middle;white-space:nowrap;">
								<button class="btn btn-xs btn-default garage-open-doc" data-doctype="Purchase Order" data-name="${frappe.utils.escape_html(po.name)}">${__("Open")}</button>
								<button class="btn btn-xs btn-default text-danger garage-unlink-doc" data-doctype="Purchase Order" data-name="${frappe.utils.escape_html(po.name)}" style="margin-left:4px;">${__("Unlink")}</button>
							</td>
						</tr>`;
					}).join("");
				} else {
					po_rows = `<tr><td colspan="5" class="text-muted text-center" style="padding:12px;">${__("No supplier Purchase Orders created")}</td></tr>`;
				}

				let pi_rows = "";
				if (pis.length) {
					pi_rows = pis.map((pi) => {
						const href = frappe.utils.get_form_link("Purchase Invoice", pi.name);
						const amt = format_currency(pi.net_total || pi.grand_total || 0, currency);
						return `<tr>
							<td style="vertical-align:middle;"><a href="${href}"><b>${frappe.utils.escape_html(pi.name)}</b></a></td>
							<td style="vertical-align:middle;">${frappe.utils.escape_html(pi.supplier || "")}</td>
							<td class="text-right" style="vertical-align:middle;"><b>${amt}</b></td>
							<td class="text-center" style="vertical-align:middle;"><span class="indicator-pill ${pi.docstatus === 1 ? "green" : "orange"}">${frappe.utils.escape_html(pi.status || "")}</span></td>
							<td class="text-right" style="vertical-align:middle;white-space:nowrap;">
								<button class="btn btn-xs btn-default garage-open-doc" data-doctype="Purchase Invoice" data-name="${frappe.utils.escape_html(pi.name)}">${__("Open")}</button>
								<button class="btn btn-xs btn-default text-danger garage-unlink-doc" data-doctype="Purchase Invoice" data-name="${frappe.utils.escape_html(pi.name)}" style="margin-left:4px;">${__("Unlink")}</button>
							</td>
						</tr>`;
					}).join("");
				} else {
					pi_rows = `<tr><td colspan="5" class="text-muted text-center" style="padding:12px;">${__("No supplier Purchase Invoices received")}</td></tr>`;
				}

				let action_btn = "";
				if (frm.doc.status === "Awaiting Parts" || frm.doc.status === "Quoted" || frm.doc.status === "Awaiting Approval") {
					action_btn = `
						<button class="btn btn-sm btn-success garage-mark-parts-ready" style="font-weight:600;">
							<i class="octicon octicon-check" style="margin-right:4px;"></i>${__("Mark All Parts Ready & Start Repair")}
						</button>
					`;
				}

				wrap.html(`
					<div class="garage-panel" style="margin-bottom:16px;padding:16px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
						
						<!-- Readiness Bar & Action Banner -->
						<div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:14px;margin-bottom:16px;padding-bottom:14px;border-bottom:1px solid var(--border-color);">
							<div style="flex:1;min-width:280px;">
								<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
									<span style="font-weight:600;font-size:13px;color:var(--text-color);">${__("Parts Procurement & Readiness")}:</span>
									<span class="indicator-pill ${is_all_ready ? "green" : "orange"}" style="font-weight:600;">
										${readiness_pct}% ${__("Ready")} (${ready_count}/${total_parts} ${__("Parts")})
									</span>
								</div>
								<div class="progress" style="height:10px;margin-bottom:0;background:var(--bg-color);border-radius:5px;overflow:hidden;">
									<div class="progress-bar ${progress_bar_class}" role="progressbar" style="width:${readiness_pct}%;"></div>
								</div>
							</div>
							${action_btn ? `<div>${action_btn}</div>` : ""}
						</div>

						<!-- Step 1: Customer PO & Sales Order Card -->
						<div class="card" style="margin-bottom:16px;padding:14px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);">
							<div style="font-size:11px;font-weight:bold;margin-bottom:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;">
								${__("Step 1: Customer Purchase Order & Sales Order")}
							</div>
							<div class="row" style="align-items:center;">
								<div class="col-sm-6" style="margin-bottom:8px;">
									<span class="text-muted small" style="display:block;margin-bottom:4px;">${__("Customer PO Reference")}</span>
									<div>${po_display}</div>
								</div>
								<div class="col-sm-6" style="margin-bottom:8px;">
									<span class="text-muted small" style="display:block;margin-bottom:4px;">${__("Linked Sales Order")}</span>
									<div>${so_display}</div>
								</div>
							</div>
						</div>

						<!-- Step 2: Required Spare Parts Collection Tracker -->
						<div class="card" style="margin-bottom:16px;padding:14px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);">
							<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;flex-wrap:wrap;gap:8px;">
								<div style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;">
									${__("Step 2: Required Spare Parts Collection Tracker")}
								</div>
								<span class="text-muted small">${__("Quantities checked against warehouse & active supplier orders")}</span>
							</div>
							<div class="table-responsive" style="margin:0;">
								<table class="table table-bordered table-sm" style="margin:0;">
									<thead class="thead-light">
										<tr style="font-size:11px;">
											<th>${__("Spare Part / Item")}</th>
											<th class="text-center" style="width:110px;">${__("Required")}</th>
											<th class="text-center" style="width:120px;">${__("In Stock")}</th>
											<th class="text-center" style="width:110px;">${__("On PO")}</th>
											<th class="text-center" style="width:110px;">${__("Received")}</th>
											<th class="text-center" style="width:150px;">${__("Readiness")}</th>
										</tr>
									</thead>
									<tbody>${parts_rows}</tbody>
								</table>
							</div>
						</div>

						<!-- Step 3: Supplier Purchase Orders -->
						<div class="card" style="margin-bottom:16px;padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);">
							<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
								<span style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;">${__("Step 3: Supplier Purchase Orders")}</span>
								<button class="btn btn-xs btn-default garage-create-po">${__("+ Purchase Order")}</button>
							</div>
							<div class="table-responsive" style="margin:0;">
								<table class="table table-bordered table-sm" style="margin:0;">
									<thead class="thead-light">
										<tr style="font-size:11px;">
											<th>${__("Purchase Order")}</th>
											<th>${__("Supplier")}</th>
											<th class="text-right" style="width:140px;">${__("Grand Total")}</th>
											<th class="text-center" style="width:130px;">${__("Status")}</th>
											<th class="text-right" style="width:140px;">${__("Actions")}</th>
										</tr>
									</thead>
									<tbody>${po_rows}</tbody>
								</table>
							</div>
						</div>

						<!-- Step 4: Supplier Purchase Invoices -->
						<div class="card" style="margin-bottom:16px;padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);">
							<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
								<span style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;">${__("Step 4: Supplier Purchase Invoices")}</span>
								<button class="btn btn-xs btn-default garage-create-pi">${__("+ Purchase Invoice")}</button>
							</div>
							<div class="table-responsive" style="margin:0;">
								<table class="table table-bordered table-sm" style="margin:0;">
									<thead class="thead-light">
										<tr style="font-size:11px;">
											<th>${__("Purchase Invoice")}</th>
											<th>${__("Supplier")}</th>
											<th class="text-right" style="width:140px;">${__("Cost")}</th>
											<th class="text-center" style="width:130px;">${__("Status")}</th>
											<th class="text-right" style="width:140px;">${__("Actions")}</th>
										</tr>
									</thead>
									<tbody>${pi_rows}</tbody>
								</table>
							</div>
						</div>

					</div>
				`);

				wrap.find(".garage-open-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
				});

				wrap.find(".garage-unlink-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					frm.events.confirm_and_unlink(frm, $btn.data("doctype"), $btn.data("name"));
				});

				wrap.find(".garage-edit-po").on("click", (e) => {
					e.preventDefault();
					frappe.prompt(
						[
							{
								fieldname: "customer_po_no",
								fieldtype: "Data",
								label: __("Customer PO No"),
								default: frm.doc.customer_po_no || "",
								reqd: 1,
							},
							{
								fieldname: "customer_po_date",
								fieldtype: "Date",
								label: __("Customer PO Date"),
								default: frm.doc.customer_po_date || frappe.datetime.get_today(),
							},
						],
						(vals) => {
							frm.set_value("customer_po_no", vals.customer_po_no);
							frm.set_value("customer_po_date", vals.customer_po_date);
							frm.save().then(() => {
								frm.trigger("render_parts_panel");
							});
						},
						__("Customer Purchase Order Reference")
					);
				});

				wrap.find(".garage-create-so").on("click", (e) => {
					e.preventDefault();
					frappe.call({
						method: "garage_management.api.service_request.create_sales_order",
						args: { service_request: frm.doc.name },
						freeze: true,
						callback(res) {
							if (!res.message) return;
							after_commercial_created(frm, "Sales Order", res.message);
						},
					});
				});

				wrap.find(".garage-create-po").on("click", (e) => {
					e.preventDefault();
					frappe.new_doc("Purchase Order", {
						service_request: frm.doc.name,
						company: frm.doc.company,
					});
				});

				wrap.find(".garage-create-pi").on("click", (e) => {
					e.preventDefault();
					frappe.new_doc("Purchase Invoice", {
						service_request: frm.doc.name,
						company: frm.doc.company,
					});
				});

				wrap.find(".garage-mark-parts-ready").on("click", (e) => {
					e.preventDefault();
					frappe.call({
						method: "garage_management.api.purchase_invoice.mark_parts_ready_for_repair",
						args: { service_request: frm.doc.name },
						freeze: true,
						callback() {
							frm._focus_tab = "repair_jobs_tab";
							frm.reload_doc();
						},
					});
				});
			},
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

		const currency = frappe.defaults.get_default("currency") || "";

		frappe.call({
			method: "garage_management.api.purchase_invoice.get_service_request_purchases",
			args: { service_request: frm.doc.name },
			callback(res) {
				const purchases = res.message || { invoices: [], total_net: 0, total_grand: 0, sales: {} };
				const sales_data = purchases.sales || {};

				// Determine true actual revenue
				const invoiced_total = sales_data.revenue_net !== undefined ? flt(sales_data.revenue_net) : flt(frm.doc.billing_total || 0);
				const invoiced_grand = sales_data.revenue_grand !== undefined ? flt(sales_data.revenue_grand) : invoiced_total;
				const revenue_source = sales_data.revenue_source || __("Quotation");

				const purchase_cost = flt(purchases.total_net || 0);
				const purchase_grand = flt(purchases.total_grand || 0);
				const gross_profit = invoiced_total - purchase_cost;
				const profit_margin = invoiced_total > 0 ? (gross_profit / invoiced_total) * 100 : 0;
				const profit_class = gross_profit >= 0 ? "text-success" : "text-danger";

				// Build Sales Documents rows
				const all_sales_docs = [];

				if (sales_data.quotations && sales_data.quotations.length) {
					sales_data.quotations.forEach((q) => {
						all_sales_docs.push({
							type: __("Quotation"),
							doctype: "Quotation",
							name: q.name,
							date: q.transaction_date,
							net_total: q.net_total,
							grand_total: q.grand_total,
							status: q.status,
							docstatus: q.docstatus,
							can_unlink: false,
						});
					});
				} else if (frm.doc.quotation) {
					all_sales_docs.push({
						type: __("Quotation"),
						doctype: "Quotation",
						name: frm.doc.quotation,
						date: "",
						net_total: frm.doc.billing_total || 0,
						grand_total: frm.doc.billing_total || 0,
						status: "Linked",
						docstatus: 1,
						can_unlink: false,
					});
				} else {
					all_sales_docs.push({
						type: __("Quotation"),
						doctype: "Quotation",
						name: "",
						date: "",
						net_total: null,
						grand_total: null,
						status: "",
						docstatus: 0,
						can_unlink: false,
					});
				}

				if (sales_data.sales_orders && sales_data.sales_orders.length) {
					sales_data.sales_orders.forEach((so) => {
						all_sales_docs.push({
							type: __("Sales Order"),
							doctype: "Sales Order",
							name: so.name,
							date: so.transaction_date,
							net_total: so.net_total,
							grand_total: so.grand_total,
							status: so.status,
							docstatus: so.docstatus,
							can_unlink: true,
						});
					});
				} else if (frm.doc.sales_order) {
					all_sales_docs.push({
						type: __("Sales Order"),
						doctype: "Sales Order",
						name: frm.doc.sales_order,
						date: "",
						net_total: null,
						grand_total: null,
						status: "Linked",
						docstatus: 1,
						can_unlink: true,
					});
				} else {
					all_sales_docs.push({
						type: __("Sales Order"),
						doctype: "Sales Order",
						name: "",
						date: "",
						net_total: null,
						grand_total: null,
						status: "",
						docstatus: 0,
						can_unlink: false,
					});
				}

				if (sales_data.sales_invoices && sales_data.sales_invoices.length) {
					sales_data.sales_invoices.forEach((si) => {
						all_sales_docs.push({
							type: __("Sales Invoice"),
							doctype: "Sales Invoice",
							name: si.name,
							date: si.posting_date,
							net_total: si.net_total,
							grand_total: si.grand_total,
							status: si.status,
							docstatus: si.docstatus,
							can_unlink: true,
						});
					});
				} else if (frm.doc.sales_invoice) {
					all_sales_docs.push({
						type: __("Sales Invoice"),
						doctype: "Sales Invoice",
						name: frm.doc.sales_invoice,
						date: "",
						net_total: null,
						grand_total: null,
						status: "Linked",
						docstatus: 1,
						can_unlink: true,
					});
				} else {
					all_sales_docs.push({
						type: __("Sales Invoice"),
						doctype: "Sales Invoice",
						name: "",
						date: "",
						net_total: null,
						grand_total: null,
						status: "",
						docstatus: 0,
						can_unlink: false,
					});
				}

				const sales_body = all_sales_docs.map((doc) => {
					if (doc.name) {
						const href = frappe.utils.get_form_link(doc.doctype, doc.name);
						const formatted_date = doc.date ? frappe.datetime.str_to_user(doc.date) : "-";
						const formatted_net = doc.net_total !== null ? format_currency(doc.net_total, currency) : "-";
						const formatted_grand = doc.grand_total !== null ? format_currency(doc.grand_total, currency) : "-";

						let status_color = "orange";
						if (doc.status === "Paid" || doc.status === "Completed") status_color = "green";
						else if (doc.status === "Unpaid" || doc.docstatus === 1) status_color = "blue";
						else if (doc.status === "Cancelled") status_color = "red";

						return `<tr>
							<td style="vertical-align:middle;font-weight:600;">${doc.type}</td>
							<td style="vertical-align:middle;"><a href="${href}" class="garage-related-doc"><b>${frappe.utils.escape_html(doc.name)}</b></a></td>
							<td style="vertical-align:middle;">${formatted_date}</td>
							<td class="text-right" style="vertical-align:middle;">${formatted_net}</td>
							<td class="text-right" style="vertical-align:middle;"><b>${formatted_grand}</b></td>
							<td class="text-center" style="vertical-align:middle;"><span class="indicator-pill ${status_color}">${frappe.utils.escape_html(doc.status)}</span></td>
							<td class="text-right" style="vertical-align:middle;white-space:nowrap;">
								<button class="btn btn-xs btn-default garage-open-doc" data-doctype="${doc.doctype}" data-name="${frappe.utils.escape_html(doc.name)}">${__("Open")}</button>
								${doc.can_unlink ? `<button class="btn btn-xs btn-default text-danger garage-unlink-doc" data-doctype="${doc.doctype}" data-name="${frappe.utils.escape_html(doc.name)}" style="margin-left:4px;">${__("Unlink")}</button>` : ""}
							</td>
						</tr>`;
					} else {
						return `<tr>
							<td style="vertical-align:middle;font-weight:600;">${doc.type}</td>
							<td style="vertical-align:middle;" class="text-muted"><i>${__("Not created")}</i></td>
							<td style="vertical-align:middle;" class="text-muted">-</td>
							<td class="text-right text-muted" style="vertical-align:middle;">-</td>
							<td class="text-right text-muted" style="vertical-align:middle;">-</td>
							<td class="text-center" style="vertical-align:middle;"><span class="indicator-pill gray">${__("None")}</span></td>
							<td class="text-right" style="vertical-align:middle;">
								${doc.doctype === "Sales Order" && frm.doc.quotation ? `<button class="btn btn-xs btn-default garage-create-so">${__("+ Create SO")}</button>` : ""}
								${doc.doctype === "Sales Invoice" ? `<button class="btn btn-xs btn-primary garage-create-invoice">${__("+ Create Invoice")}</button>` : ""}
							</td>
						</tr>`;
					}
				}).join("");

				let purchase_body = "";
				if (purchases.invoices && purchases.invoices.length) {
					purchase_body = purchases.invoices.map((pi) => {
						const href = frappe.utils.get_form_link("Purchase Invoice", pi.name);
						const formatted_date = pi.posting_date ? frappe.datetime.str_to_user(pi.posting_date) : "-";
						const formatted_net = format_currency(pi.net_total || 0, currency);
						const formatted_grand = format_currency(pi.grand_total || pi.net_total || 0, currency);
						const rj_badge = pi.repair_job ? `<span class="badge badge-info" style="font-size:10px;margin-left:6px;">${frappe.utils.escape_html(pi.repair_job)}</span>` : "";
						const status_color = pi.docstatus === 1 ? (pi.status === "Paid" ? "green" : "blue") : "orange";

						return `<tr>
							<td style="vertical-align:middle;"><a href="${href}" class="garage-related-doc"><b>${frappe.utils.escape_html(pi.name)}</b></a>${rj_badge}</td>
							<td style="vertical-align:middle;">${frappe.utils.escape_html(pi.supplier || "")}</td>
							<td style="vertical-align:middle;">${formatted_date}</td>
							<td class="text-right" style="vertical-align:middle;">${formatted_net}</td>
							<td class="text-right" style="vertical-align:middle;"><b>${formatted_grand}</b></td>
							<td class="text-center" style="vertical-align:middle;"><span class="indicator-pill ${status_color}">${frappe.utils.escape_html(pi.status || "")}</span></td>
							<td class="text-right" style="vertical-align:middle;white-space:nowrap;">
								<button class="btn btn-xs btn-default garage-open-doc" data-doctype="Purchase Invoice" data-name="${frappe.utils.escape_html(pi.name)}">${__("Open")}</button>
								<button class="btn btn-xs btn-default text-danger garage-unlink-doc" data-doctype="Purchase Invoice" data-name="${frappe.utils.escape_html(pi.name)}" style="margin-left:4px;">${__("Unlink")}</button>
							</td>
						</tr>`;
					}).join("");
				} else {
					purchase_body = `<tr><td colspan="7" class="text-muted text-center" style="padding:20px;">${__("No linked Purchase Invoices for this Service Request")}</td></tr>`;
				}

				wrap.html(`
					<div class="garage-panel" style="margin-bottom:16px;padding:16px;border:1px solid var(--border-color);border-radius:8px;background:var(--control-bg);">
						
						<!-- Financial Overview KPI Tiles -->
						<div class="row" style="margin-bottom:16px;">
							<div class="col-sm-3" style="margin-bottom:12px;">
								<div class="card" style="padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);height:100%;">
									<div style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;">
										${__("Sales Revenue (Net)")}
									</div>
									<div style="font-size:22px;font-weight:700;color:var(--text-color);margin-bottom:6px;">
										${format_currency(invoiced_total, currency)}
									</div>
									<div style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px;">
										<span>${__("Grand")}: <b>${format_currency(invoiced_grand, currency)}</b></span>
										<span class="badge badge-light" style="font-size:10px;font-weight:600;border:1px solid var(--border-color);">${frappe.utils.escape_html(revenue_source)}</span>
									</div>
								</div>
							</div>
							<div class="col-sm-3" style="margin-bottom:12px;">
								<div class="card" style="padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);height:100%;">
									<div style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;">
										${__("Purchases Cost (Net)")}
									</div>
									<div style="font-size:22px;font-weight:700;color:#e67e22;margin-bottom:6px;">
										${format_currency(purchase_cost, currency)}
									</div>
									<div style="font-size:11px;color:var(--text-muted);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:4px;">
										<span>${__("Grand")}: <b>${format_currency(purchase_grand, currency)}</b></span>
										<span class="badge badge-light" style="font-size:10px;font-weight:600;border:1px solid var(--border-color);">${purchases.invoices ? purchases.invoices.length : 0} ${__("Invoices")}</span>
									</div>
								</div>
							</div>
							<div class="col-sm-3" style="margin-bottom:12px;">
								<div class="card" style="padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);height:100%;">
									<div style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;">
										${__("Gross Profit")}
									</div>
									<div style="font-size:22px;font-weight:700;margin-bottom:6px;" class="${profit_class}">
										${format_currency(gross_profit, currency)}
									</div>
									<div style="font-size:11px;color:var(--text-muted);">
										<span>${__("Net Revenue - Purchase Cost")}</span>
									</div>
								</div>
							</div>
							<div class="col-sm-3" style="margin-bottom:12px;">
								<div class="card" style="padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);height:100%;">
									<div style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;margin-bottom:6px;">
										${__("Gross Margin")}
									</div>
									<div style="font-size:22px;font-weight:700;margin-bottom:6px;" class="${profit_class}">
										${profit_margin.toFixed(1)}%
									</div>
									<div style="font-size:11px;color:var(--text-muted);">
										<span>${__("Margin on Net Revenue")}</span>
									</div>
								</div>
							</div>
						</div>

						<!-- Sales Commercial Documents Card -->
						<div class="card" style="margin-bottom:16px;padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);">
							<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
								<div>
									<span style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;">${__("Sales Commercial Documents")}</span>
									<div class="text-muted small">${__("Quotation, Sales Order, and Customer Sales Invoices")}</div>
								</div>
								<div>
									${!frm.doc.sales_order && frm.doc.quotation ? `<button class="btn btn-xs btn-default garage-create-so" style="margin-right:6px;">${__("+ Sales Order")}</button>` : ""}
									${!frm.doc.sales_invoice ? `<button class="btn btn-xs btn-primary garage-create-invoice">${__("+ Sales Invoice")}</button>` : ""}
								</div>
							</div>
							<div class="table-responsive" style="margin:0;">
								<table class="table table-bordered table-sm" style="margin:0;">
									<thead class="thead-light">
										<tr style="font-size:11px;">
											<th style="width:130px;">${__("Type")}</th>
											<th>${__("Document #")}</th>
											<th style="width:120px;">${__("Date")}</th>
											<th class="text-right" style="width:130px;">${__("Net Amount")}</th>
											<th class="text-right" style="width:130px;">${__("Grand Total")}</th>
											<th class="text-center" style="width:120px;">${__("Status")}</th>
											<th class="text-right" style="width:130px;">${__("Actions")}</th>
										</tr>
									</thead>
									<tbody>${sales_body}</tbody>
								</table>
							</div>
						</div>

						<!-- Purchase Invoices Card -->
						<div class="card" style="margin-bottom:0;padding:16px;border:1px solid var(--border-color);border-radius:6px;background:var(--card-bg);">
							<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;flex-wrap:wrap;gap:8px;">
								<div>
									<span style="font-size:11px;font-weight:bold;color:var(--text-muted);text-transform:uppercase;letter-spacing:0.6px;">${__("Supplier Purchase Invoices")}</span>
									<div class="text-muted small">${__("Spare parts and external procurement costs for this job")}</div>
								</div>
								<button class="btn btn-xs btn-default garage-create-pi">${__("+ Purchase Invoice")}</button>
							</div>
							<div class="table-responsive" style="margin:0;">
								<table class="table table-bordered table-sm" style="margin:0;">
									<thead class="thead-light">
										<tr style="font-size:11px;">
											<th>${__("Invoice #")}</th>
											<th>${__("Supplier")}</th>
											<th style="width:120px;">${__("Date")}</th>
											<th class="text-right" style="width:130px;">${__("Net Cost")}</th>
											<th class="text-right" style="width:130px;">${__("Grand Total")}</th>
											<th class="text-center" style="width:120px;">${__("Status")}</th>
											<th class="text-right" style="width:130px;">${__("Actions")}</th>
										</tr>
									</thead>
									<tbody>${purchase_body}</tbody>
								</table>
							</div>
						</div>

					</div>
				`);

				wrap.find(".garage-open-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					frappe.set_route("Form", $btn.data("doctype"), $btn.data("name"));
				});
				wrap.find(".garage-unlink-doc").on("click", (e) => {
					e.preventDefault();
					const $btn = $(e.currentTarget);
					frm.events.confirm_and_unlink(frm, $btn.data("doctype"), $btn.data("name"));
				});
				wrap.find(".garage-create-so").on("click", (e) => {
					e.preventDefault();
					frappe.call({
						method: "garage_management.api.service_request.create_sales_order",
						args: { service_request: frm.doc.name },
						freeze: true,
						callback(r) {
							if (!r.message) return;
							after_commercial_created(frm, "Sales Order", r.message);
						},
					});
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
				wrap.find(".garage-create-pi").on("click", (e) => {
					e.preventDefault();
					frappe.new_doc("Purchase Invoice", {
						service_request: frm.doc.name,
						company: frm.doc.company,
					});
				});
			},
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

		if (!frm.doc.sales_order && (frm.doc.quotation || (frm.doc.billing_items && frm.doc.billing_items.length))) {
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

		frm.add_custom_button(
			__("Purchase Order"),
			() => {
				frappe.new_doc("Purchase Order", {
					service_request: frm.doc.name,
					company: frm.doc.company,
				});
			},
			__("Create")
		);

		frm.add_custom_button(
			__("Purchase Invoice"),
			() => {
				frappe.new_doc("Purchase Invoice", {
					service_request: frm.doc.name,
					company: frm.doc.company,
				});
			},
			__("Create")
		);

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
		frm.add_custom_button(__("Purchase Orders"), () => {
			frappe.set_route("List", "Purchase Order", { service_request: frm.doc.name });
		}, __("View"));
		frm.add_custom_button(__("Purchase Invoices"), () => {
			frappe.set_route("List", "Purchase Invoice", { service_request: frm.doc.name });
		}, __("View"));
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
						frm._focus_tab = "parts_tab";
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		if (frm.doc.status === "Awaiting Parts") {
			frm.add_custom_button(__("Mark Parts Ready"), () => {
				frappe.call({
					method: "garage_management.api.purchase_invoice.mark_parts_ready_for_repair",
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

		if (frm.doc.status === "Repairing" || frm.doc.status === "In Progress" || frm.doc.status === "Testing") {
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

		if (frm.doc.quotation) {
			frm.add_custom_button(__("Unlink Quotation"), () => {
				frm.events.confirm_and_unlink(frm, "Quotation", frm.doc.quotation);
			}, __("Actions"));
		}
		if (frm.doc.sales_order) {
			frm.add_custom_button(__("Unlink Sales Order"), () => {
				frm.events.confirm_and_unlink(frm, "Sales Order", frm.doc.sales_order);
			}, __("Actions"));
		}
		if (frm.doc.sales_invoice) {
			frm.add_custom_button(__("Unlink Sales Invoice"), () => {
				frm.events.confirm_and_unlink(frm, "Sales Invoice", frm.doc.sales_invoice);
			}, __("Actions"));
		}

		// --- PRINT MENU ---
		frm.add_custom_button(__("Job Report"), () => open_print("Service Request", frm.doc.name, "Job Report"), __("Print"));
		frm.add_custom_button(__("Receiving Report"), () => open_print("Service Request", frm.doc.name, "Receiving Report"), __("Print"));
		frm.add_custom_button(__("Inspection Report"), () => print_linked(frm, "Inspection", "Inspection Report"), __("Print"));
		frm.add_custom_button(__("Job Repair Report"), () => print_linked(frm, "Repair Job", "Job Repair Report"), __("Print"));
	},

	confirm_and_unlink(frm, doctype, docname) {
		const method_map = {
			"Quotation": "garage_management.api.service_request.unlink_quotation",
			"Sales Order": "garage_management.api.service_request.unlink_sales_order",
			"Sales Invoice": "garage_management.api.service_request.unlink_sales_invoice",
			"Purchase Order": "garage_management.api.purchase_invoice.unlink_purchase_order",
			"Purchase Invoice": "garage_management.api.purchase_invoice.unlink_purchase_invoice",
		};
		const method = method_map[doctype];
		if (!method) return;

		frappe.confirm(
			__("Are you sure you want to unlink {0} <b>{1}</b> from this Service Request?", [doctype, frappe.utils.escape_html(docname)]),
			() => {
				const args = (doctype === "Purchase Invoice" || doctype === "Purchase Order")
					? { [frappe.scrub(doctype)]: docname, service_request: frm.doc.name }
					: { service_request: frm.doc.name };
				frappe.call({
					method: method,
					args: args,
					freeze: true,
					callback(r) {
						if (!r.exc) {
							frm.reload_doc();
						}
					},
				});
			}
		);
	},
});

function status_color(status) {
	const map = {
		Draft: "gray",
		"Awaiting Parts": "orange",
		Repairing: "cyan",
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
	const letterhead =
		(cur_frm && cur_frm.doc && (cur_frm.doc.letter_head || cur_frm.doc.__onload?.default_letter_head)) ||
		frappe.defaults.get_default("letter_head") ||
		"";
	let url =
		"/printview?doctype=" +
		encodeURIComponent(doctype) +
		"&name=" +
		encodeURIComponent(name) +
		"&format=" +
		encodeURIComponent(format) +
		"&no_letterhead=0";
	if (letterhead) {
		url += "&letterhead=" + encodeURIComponent(letterhead);
	}
	window.open(frappe.urllib.get_full_url(url), "_blank");
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
	frm._focus_tab = doctype === "Quotation" ? "quotation_tab" : (doctype === "Sales Order" ? "parts_tab" : "invoice_tab");
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
