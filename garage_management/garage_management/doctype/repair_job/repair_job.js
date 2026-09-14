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
		if (frm.doc.__onload?.default_letter_head) {
			frm.doc.letter_head = frm.doc.__onload.default_letter_head;
		}
		frm.trigger("render_inspection_tab");

		if (frm.is_new()) return;

		// --- VIEW MENU ---

		if (frm.doc.service_request) {
			frm.add_custom_button(__("Service Request"), () => {
				frappe.set_route("Form", "Service Request", frm.doc.service_request);
			}, __("View"));

			frappe.db.get_value("Service Request", frm.doc.service_request, "sales_invoice")
				.then((r) => {
					if (r?.message?.sales_invoice) {
						frm.add_custom_button(__("Sales Invoice"), () => {
							frappe.set_route("Form", "Sales Invoice", r.message.sales_invoice);
						}, __("View"));
					} else if (frm.doc.status === "Completed") {
						frm.add_custom_button(__("Create Sales Invoice"), () => {
							frappe.call({
								method: "garage_management.api.service_request.create_sales_invoice",
								args: { service_request: frm.doc.service_request },
								freeze: true,
								callback(res) {
									if (res.message) {
										frappe.set_route("Form", "Sales Invoice", res.message);
									}
								},
							});
						}, __("Actions"));
					}
				});
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

		if (frm.doc.status === "Repairing" || frm.doc.status === "In Progress") {
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

		if (frm.doc.status === "Repairing" || frm.doc.status === "In Progress" || frm.doc.status === "Testing") {
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

		if (frm.doc.service_request && (frm.doc.spare_parts || []).length) {
			frm.add_custom_button(__("Sync Parts to Billing"), () => {
				frm.call({
					doc: frm.doc,
					method: "sync_spare_parts_to_service_request",
					freeze: true,
					callback() {
						frm.reload_doc();
					},
				});
			}, __("Actions"));
		}

		// --- PRINT MENU ---
		frm.add_custom_button(__("Job Repair Report"), () => {
			const lh = frm.doc.letter_head || frm.doc.__onload?.default_letter_head || frappe.defaults.get_default("letter_head") || "";
			let url =
				"/printview?doctype=" +
				encodeURIComponent("Repair Job") +
				"&name=" +
				encodeURIComponent(frm.doc.name) +
				"&format=" +
				encodeURIComponent("Job Repair Report") +
				"&no_letterhead=0";
			if (lh) url += "&letterhead=" + encodeURIComponent(lh);
			window.open(frappe.urllib.get_full_url(url), "_blank");
		}, __("Print"));
	},

	job_type(frm) {
		if (frm.doc.job_type && !frm.doc.qc_items?.length) {
			frm.trigger("load_job_type_defaults");
		}
	},

	inspection(frm) {
		frm._viewing_inspection_name = frm.doc.inspection;
		frm.trigger("render_inspection_tab");
	},

	service_request(frm) {
		frm._viewing_inspection_name = null;
		frm.trigger("render_inspection_tab");
	},

	render_inspection_tab(frm) {
		const wrap = frm.fields_dict.inspection_overview_html?.$wrapper;
		if (!wrap) return;

		if (frm.is_new() && !frm.doc.inspection && !frm.doc.service_request) {
			wrap.html(`
				<div class="text-muted text-center" style="padding: 24px; border: 1px dashed var(--border-color); border-radius: 8px;">
					<p>${__("Save the Repair Job or select an Inspection / Service Request to view inspection details.")}</p>
				</div>
			`);
			return;
		}

		function load_inspection(target_insp_name) {
			frm.call({
				doc: frm.doc,
				method: "get_inspection_details",
				args: {
					inspection_name: target_insp_name || frm._viewing_inspection_name || null,
				},
				callback(r) {
					const data = r.message;
					if (!data || (!data.name && (!data.all_inspections || !data.all_inspections.length))) {
						wrap.html(`
							<div class="alert alert-warning" style="margin: 8px 0;">
								<div style="font-weight:600; margin-bottom:4px;"><i class="fa fa-exclamation-triangle"></i> ${__("No Inspection Found")}</div>
								<div>${__("No linked Inspection found for this Repair Job or Service Request.")}</div>
							</div>
						`);
						return;
					}

					frm._viewing_inspection_name = data.name;
					const href = frappe.utils.get_form_link("Inspection", data.name);
					const status_pill = status_color(data.status);
					const is_linked_to_job = (data.name === frm.doc.inspection);

					let html = `<div class="inspection-overview-container" style="display:flex; flex-direction:column; gap:16px;">`;

					// --- MULTI-INSPECTION SELECTOR BAR ---
					if (data.all_inspections && data.all_inspections.length > 1) {
						let pills_html = data.all_inspections.map((i) => {
							const is_current = (i.name === data.name);
							const pill_status = status_color(i.status);
							const is_job_linked = (i.name === frm.doc.inspection);

							if (is_current) {
								return `
									<div class="btn btn-xs btn-primary" style="padding: 6px 12px; border-radius: 6px; display:inline-flex; align-items:center; gap:6px; cursor:default; font-weight:600;">
										<i class="fa fa-check-circle"></i>
										<span>${frappe.utils.escape_html(i.name)}</span>
										<span class="badge" style="background:rgba(255,255,255,0.25); color:#fff; font-size:10px;">${frappe.utils.escape_html(i.status || "Draft")}</span>
										${is_job_linked ? `<span class="badge badge-success" style="font-size:10px; background:#28a745; color:#fff;">${__("Linked")}</span>` : ""}
										<span style="font-size:11px; opacity:0.9;">(${i.findings_count} findings · ${i.parts_count} parts)</span>
									</div>
								`;
							} else {
								return `
									<button class="btn btn-xs btn-default garage-switch-insp" data-name="${frappe.utils.escape_html(i.name)}" style="padding: 6px 12px; border-radius: 6px; display:inline-flex; align-items:center; gap:6px;">
										<b>${frappe.utils.escape_html(i.name)}</b>
										<span class="indicator-pill ${pill_status}" style="font-size:10px;">${frappe.utils.escape_html(i.status || "Draft")}</span>
										${is_job_linked ? `<span class="badge badge-success" style="font-size:9px;">${__("Linked")}</span>` : ""}
										<span class="text-muted" style="font-size:11px;">(${i.findings_count} findings)</span>
									</button>
								`;
							}
						}).join("");

						html += `
							<div class="garage-panel" style="padding:12px 14px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg, #fff); box-shadow: 0 1px 3px rgba(0,0,0,0.04);">
								<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
									<div style="font-size:13px; font-weight:700; color:var(--text-color); display:flex; align-items:center; gap:8px;">
										<i class="fa fa-list-ul text-primary" style="font-size:14px;"></i>
										<span>${__("Inspections for this Service Request")}</span>
										<span class="badge badge-info" style="font-size:11px;">${data.all_inspections.length} ${__("Inspections")}</span>
									</div>
									<div>
										${!is_linked_to_job ? `
											<button class="btn btn-xs btn-primary garage-link-this-insp" data-name="${frappe.utils.escape_html(data.name)}">
												<i class="fa fa-link"></i> ${__("Link {0} to this Repair Job", [frappe.utils.escape_html(data.name)])}
											</button>
										` : `
											<span class="badge badge-success" style="padding:5px 9px; font-size:11px;">
												<i class="fa fa-link"></i> ${__("Active Linked Inspection")}
											</span>
										`}
									</div>
								</div>
								<div style="display:flex; flex-wrap:wrap; gap:8px; align-items:center;">
									${pills_html}
								</div>
							</div>
						`;
					}

					// --- HEADER CARD FOR SELECTED INSPECTION ---
					html += `
						<div class="garage-panel" style="padding:14px; border:1px solid var(--border-color); border-radius:8px; background:var(--control-bg); display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
							<div>
								<div style="font-size:15px; font-weight:700; display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
									<span>${__("Viewing Inspection")}:</span>
									<a href="${href}" style="color:var(--primary); font-weight:700;">${frappe.utils.escape_html(data.name)}</a>
									<span class="indicator-pill ${status_pill}">${frappe.utils.escape_html(data.status || "Draft")}</span>
									${is_linked_to_job ? `<span class="badge badge-success" style="font-size:11px;"><i class="fa fa-check"></i> ${__("Linked to Job")}</span>` : ""}
								</div>
								<div class="text-muted small" style="margin-top:4px;">
									<span><b>${__("Inspector")}:</b> ${frappe.utils.escape_html(data.assigned_to || "-")}</span>
									${data.creation ? `<span style="margin-left:12px;"><b>${__("Date")}:</b> ${frappe.datetime.str_to_user(data.creation)}</span>` : ""}
								</div>
							</div>
							<div style="display:flex; gap:6px;">
								<button class="btn btn-xs btn-default garage-print-insp" data-name="${frappe.utils.escape_html(data.name)}">
									<i class="fa fa-print"></i> ${__("Print Report")}
								</button>
								<button class="btn btn-xs btn-default garage-open-insp" data-name="${frappe.utils.escape_html(data.name)}">
									<i class="fa fa-external-link"></i> ${__("Open Full Inspection")}
								</button>
							</div>
						</div>
					`;

					// Recommended Work & Notes Card
					if (data.recommended_work || data.inspection_notes) {
						html += `
							<div class="row">
								${data.recommended_work ? `
									<div class="${data.inspection_notes ? 'col-md-6' : 'col-md-12'}">
										<div class="garage-panel" style="padding:12px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg); height:100%;">
											<h6 style="color:var(--text-color); font-weight:700; margin-bottom:8px;">
												<i class="fa fa-wrench text-primary" style="margin-right:6px;"></i>${__("Recommended Work")}
											</h6>
											<div style="font-size:13px; line-height:1.5;">${data.recommended_work}</div>
										</div>
									</div>
								` : ""}
								${data.inspection_notes ? `
									<div class="${data.recommended_work ? 'col-md-6' : 'col-md-12'}">
										<div class="garage-panel" style="padding:12px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg); height:100%;">
											<h6 style="color:var(--text-color); font-weight:700; margin-bottom:8px;">
												<i class="fa fa-sticky-note text-info" style="margin-right:6px;"></i>${__("Inspection Notes")}
											</h6>
											<div style="font-size:13px; line-height:1.5;">${data.inspection_notes}</div>
										</div>
									</div>
								` : ""}
							</div>
						`;
					}

					// Findings Table
					if (data.findings && data.findings.length > 0) {
						let f_rows = data.findings.map((f) => {
							return `<tr>
								<td style="font-weight:600; width:35%;">${frappe.utils.escape_html(f.finding_name || "")}</td>
								<td>${frappe.utils.escape_html(f.description || "-")}</td>
							</tr>`;
						}).join("");

						html += `
							<div class="garage-panel" style="padding:12px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg);">
								<h6 style="font-weight:700; margin-bottom:10px;">
									<i class="fa fa-stethoscope text-warning" style="margin-right:6px;"></i>${__("Inspection Findings & Faults")} (${data.findings.length})
								</h6>
								<div class="table-responsive">
									<table class="table table-bordered table-condensed" style="margin:0;">
										<thead style="background:var(--control-bg);">
											<tr><th>${__("Finding")}</th><th>${__("Description")}</th></tr>
										</thead>
										<tbody>${f_rows}</tbody>
									</table>
								</div>
							</div>
						`;
					}

					// Part Diagnostics & Bench Results
					if (data.part_results && data.part_results.length > 0) {
						let p_rows = data.part_results.map((p) => {
							let cond_pill = "gray";
							if (p.condition === "Perfect Condition" || p.condition === "Good") cond_pill = "green";
							else if (p.condition === "Moderate Damage") cond_pill = "orange";
							else if (p.condition === "Needs Overhaul" || p.condition === "Damaged") cond_pill = "red";

							return `<tr>
								<td style="font-weight:600;">${frappe.utils.escape_html(p.repair_asset || "-")}</td>
								<td>${frappe.utils.escape_html(p.part_no || "-")}${p.serial_number ? ` (SN: ${frappe.utils.escape_html(p.serial_number)})` : ""}</td>
								<td><span class="indicator-pill ${cond_pill}">${frappe.utils.escape_html(p.condition || "Unknown")}</span></td>
								<td>${frappe.utils.escape_html(p.test_bench_results || "-")}</td>
								<td class="text-center" style="width:70px;">
									${p.damaged_part_photo ? `<a href="${p.damaged_part_photo}" target="_blank"><img src="${p.damaged_part_photo}" style="height:36px; width:36px; object-fit:cover; border-radius:4px; border:1px solid var(--border-color);" title="${__("View Photo")}"/></a>` : "-"}
								</td>
							</tr>`;
						}).join("");

						html += `
							<div class="garage-panel" style="padding:12px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg);">
								<h6 style="font-weight:700; margin-bottom:10px;">
									<i class="fa fa-cogs text-primary" style="margin-right:6px;"></i>${__("Part Results & Bench Diagnostics")} (${data.part_results.length})
								</h6>
								<div class="table-responsive">
									<table class="table table-bordered table-condensed" style="margin:0;">
										<thead style="background:var(--control-bg);">
											<tr><th>${__("Component / Asset")}</th><th>${__("Part / Serial")}</th><th>${__("Condition")}</th><th>${__("Test Bench Results")}</th><th>${__("Photo")}</th></tr>
										</thead>
										<tbody>${p_rows}</tbody>
									</table>
								</div>
							</div>
						`;
					}

					// Key Replacement Items
					if (data.key_replacement_items && data.key_replacement_items.length > 0) {
						let k_tags = data.key_replacement_items.map((k) => {
							return `<span class="badge" style="font-size:12px; font-weight:500; padding:6px 10px; margin-right:6px; margin-bottom:6px; background:var(--control-bg); border:1px solid var(--border-color); color:var(--text-color);">
								<i class="fa fa-tag text-muted" style="margin-right:4px;"></i><b>${frappe.utils.escape_html(k.item_code)}</b>: ${frappe.utils.escape_html(k.item_name)}
							</span>`;
						}).join("");

						html += `
							<div class="garage-panel" style="padding:12px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg);">
								<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; flex-wrap:wrap; gap:8px;">
									<h6 style="font-weight:700; margin:0;">
										<i class="fa fa-cube text-success" style="margin-right:6px;"></i>${__("Key Replacement Items Suggested by Inspection")} (${data.key_replacement_items.length})
									</h6>
									<button class="btn btn-xs btn-primary garage-import-all-parts">
										<i class="fa fa-plus-circle"></i> ${__("Add to Spare Parts Table")}
									</button>
								</div>
								<div style="display:flex; flex-wrap:wrap; gap:6px;">${k_tags}</div>
							</div>
						`;
					}

					// Photos Gallery
					if (data.photos && data.photos.length > 0) {
						let photo_cards = data.photos.map((ph) => {
							return `
								<div style="width:140px; border:1px solid var(--border-color); border-radius:6px; overflow:hidden; background:var(--control-bg); text-align:center;">
									<a href="${ph.image}" target="_blank">
										<img src="${ph.image}" style="width:100%; height:100px; object-fit:cover; display:block;" />
									</a>
									${ph.notes ? `<div class="text-muted small" style="padding:4px; text-overflow:ellipsis; overflow:hidden; white-space:nowrap;" title="${frappe.utils.escape_html(ph.notes)}">${frappe.utils.escape_html(ph.notes)}</div>` : ""}
								</div>
							`;
						}).join("");

						html += `
							<div class="garage-panel" style="padding:12px; border:1px solid var(--border-color); border-radius:8px; background:var(--card-bg);">
								<h6 style="font-weight:700; margin-bottom:10px;">
									<i class="fa fa-camera text-info" style="margin-right:6px;"></i>${__("Inspection Photos")} (${data.photos.length})
								</h6>
								<div style="display:flex; flex-wrap:wrap; gap:10px;">${photo_cards}</div>
							</div>
						`;
					}

					html += `</div>`;
					wrap.html(html);

					// --- BIND ACTIONS ---
					wrap.find(".garage-open-insp").on("click", (e) => {
						e.preventDefault();
						frappe.set_route("Form", "Inspection", $(e.currentTarget).data("name"));
					});

					wrap.find(".garage-print-insp").on("click", (e) => {
						e.preventDefault();
						const insp_name = $(e.currentTarget).data("name");
						const lh = frm.doc.letter_head || frm.doc.__onload?.default_letter_head || frappe.defaults.get_default("letter_head") || "";
						let url =
							"/printview?doctype=Inspection&name=" +
							encodeURIComponent(insp_name) +
							"&format=" +
							encodeURIComponent("Inspection Report") +
							"&no_letterhead=0";
						if (lh) url += "&letterhead=" + encodeURIComponent(lh);
						window.open(frappe.urllib.get_full_url(url), "_blank");
					});

					wrap.find(".garage-switch-insp").on("click", (e) => {
						e.preventDefault();
						const target = $(e.currentTarget).data("name");
						load_inspection(target);
					});

					wrap.find(".garage-link-this-insp").on("click", (e) => {
						e.preventDefault();
						const target = $(e.currentTarget).data("name");
						frm.set_value("inspection", target);
						frappe.show_alert({
							message: __("Inspection {0} linked to this Repair Job", [target]),
							indicator: "green",
						});
						load_inspection(target);
					});

					wrap.find(".garage-import-all-parts").on("click", async (e) => {
						e.preventDefault();
						if (!data.key_replacement_items || !data.key_replacement_items.length) return;

						const default_wh = await frappe.db.get_single_value("Service Job Settings", "default_warehouse");
						let added_count = 0;
						const existing = new Set((frm.doc.spare_parts || []).map((r) => r.item_code));

						for (const item of data.key_replacement_items) {
							if (!item.item_code || existing.has(item.item_code)) continue;

							let item_info = await frappe.db.get_value("Item", item.item_code, [
								"item_name",
								"stock_uom",
								"standard_rate",
								"description",
								"is_stock_item",
							]);
							let details = item_info?.message || {};

							let row = frm.add_child("spare_parts");
							row.item_code = item.item_code;
							row.item_name = item.item_name || details.item_name || item.item_code;
							row.uom = details.stock_uom || "Nos";
							row.qty = 1;
							row.rate = flt(details.standard_rate || 0);
							row.amount = flt(row.qty) * flt(row.rate);
							row.description = details.description || "";
							if (details.is_stock_item && default_wh) {
								row.warehouse = default_wh;
							}
							existing.add(item.item_code);
							added_count++;
						}

						if (added_count > 0) {
							frm.dirty();
							recalculate_spare_parts(frm);
							frappe.show_alert({
								message: __("{0} replacement part(s) added to Spare Parts table", [added_count]),
								indicator: "green",
							});
						} else {
							frappe.show_alert({
								message: __("All replacement parts already present in table"),
								indicator: "orange",
							});
						}
					});
				},
			});
		}

		load_inspection();
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
		recalculate_spare_parts(frm);
	},
});

function recalculate_spare_parts(frm) {
	let total = 0;
	(frm.doc.spare_parts || []).forEach((row) => {
		row.amount = flt(row.qty || 1) * flt(row.rate || 0);
		total += flt(row.amount);
	});
	frm.set_value("total_spare_parts_amount", total);
	frm.refresh_fields(["spare_parts", "total_spare_parts_amount"]);
}

frappe.ui.form.on("Repair Job Spare Part", {
	item_code(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (!row.item_code) return;

		frappe.db.get_value("Item", row.item_code, ["item_name", "stock_uom", "description", "standard_rate", "is_stock_item"])
			.then((r) => {
				const data = r.message;
				if (!data) return;
				frappe.model.set_value(cdt, cdn, "item_name", data.item_name);
				frappe.model.set_value(cdt, cdn, "uom", data.stock_uom);
				frappe.model.set_value(cdt, cdn, "description", data.description);
				if (!row.qty) {
					frappe.model.set_value(cdt, cdn, "qty", 1);
				}
				if (!flt(row.rate)) {
					frappe.model.set_value(cdt, cdn, "rate", data.standard_rate || 0);
				}
				frappe.db.get_single_value("Service Job Settings", "default_warehouse")
					.then((wh) => {
						if (wh && data.is_stock_item && !row.warehouse) {
							frappe.model.set_value(cdt, cdn, "warehouse", wh);
						}
					});
				recalculate_spare_parts(frm);
			});
	},
	qty(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty || 1) * flt(row.rate || 0));
		recalculate_spare_parts(frm);
	},
	rate(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		frappe.model.set_value(cdt, cdn, "amount", flt(row.qty || 1) * flt(row.rate || 0));
		recalculate_spare_parts(frm);
	},
	spare_parts_remove(frm) {
		recalculate_spare_parts(frm);
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

function status_color(status) {
	const map = {
		Draft: "gray",
		Repairing: "cyan",
		"In Progress": "cyan",
		Testing: "purple",
		Completed: "green",
		Cancelled: "red",
	};
	return map[status] || "gray";
}

