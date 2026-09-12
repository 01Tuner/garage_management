/**
 * Rich Service Request Kanban card body:
 * ID badge, priority pill, customer & phone call link,
 * job type tag, vehicle/engine tag, complaint preview,
 * inspection & repair status badges, billing amount & quotation/invoice pills.
 */
(() => {
	function is_service_request_kanban() {
		const route = frappe.get_route() || [];
		if (route[0] === "service-request" || route[1] === "Service Request") {
			return true;
		}
		if (cur_list?.doctype === "Service Request") {
			return true;
		}
		if (cur_list?.board?.reference_doctype === "Service Request") {
			return true;
		}
		return false;
	}

	function patch_kanban_card() {
		if (frappe.views?.KanbanBoardCard && !frappe.views.KanbanBoardCard.__garage_patched) {
			const Original = frappe.views.KanbanBoardCard;
			const Patched = function (card, wrapper) {
				const res = Original.apply(this, arguments);
				if (is_service_request_kanban() || card?.doctype === "Service Request") {
					setTimeout(restyle_service_request_cards, 10);
				}
				return res;
			};
			Patched.__garage_patched = true;
			frappe.views.KanbanBoardCard = Patched;
		}

		if (frappe.views?.KanbanBoard && !frappe.views.KanbanBoard.prototype.__garage_patched) {
			const orig_update = frappe.views.KanbanBoard.prototype.update;
			frappe.views.KanbanBoard.prototype.update = function () {
				const res = orig_update.apply(this, arguments);
				if (is_service_request_kanban()) {
					setTimeout(restyle_service_request_cards, 50);
					setTimeout(restyle_service_request_cards, 250);
				}
				return res;
			};
			frappe.views.KanbanBoard.prototype.__garage_patched = true;
		}
	}

	function render_rich_service_request_card(card, $wrapper) {
		if (!card || !$wrapper) return;
		const name = card.name || card.doc?.name || "";
		if (!name) return;

		let $card_wrapper = $wrapper.hasClass("kanban-card-wrapper")
			? $wrapper
			: $wrapper.closest(".kanban-card-wrapper");
		if (!$card_wrapper.length) {
			$card_wrapper = $wrapper.find(`[data-name="${encodeURIComponent(name)}"], [data-name="${name}"]`).first();
		}
		if (!$card_wrapper.length) return;

		// Strictly prevent any nesting or duplicate enhancement
		if ($card_wrapper.find(".garage-kanban-card").length > 0) {
			return;
		}

		let $card = $card_wrapper.children(".kanban-card");
		if (!$card.length) {
			$card = $card_wrapper.find(".kanban-card").first();
		}
		if (!$card.length) {
			$card = $('<div class="kanban-card content"></div>').appendTo($card_wrapper);
		}

		let doc = Object.assign({}, card.doc || {});
		if ((!doc.customer_name || !doc.customer) && cur_list?.data && Array.isArray(cur_list.data)) {
			const d = cur_list.data.find((x) => x.name === name);
			if (d) doc = Object.assign({}, d, doc);
		}
		if ((!doc.customer_name || !doc.inspection_status) && cur_list?.board?.cards && Array.isArray(cur_list.board.cards)) {
			const c = cur_list.board.cards.find((x) => x.name === name);
			if (c?.doc) doc = Object.assign({}, c.doc, doc);
			else if (c) doc = Object.assign({}, c, doc);
		}
		if (!doc.customer_name && frappe.model) {
			const d = frappe.model.get_doc("Service Request", name);
			if (d) doc = Object.assign({}, d, doc);
		}

		const form_link = frappe.utils.get_form_link("Service Request", name);
		const customer_name = doc.customer_name || doc.customer || card.title || name;
		const mobile_no = doc.mobile_no || "";
		const priority = doc.priority || "Normal";
		const job_type = doc.job_type || "";
		const complaint = doc.complaint || "";
		const vehicle = doc.engine_vehicle_notes || "";
		const inspection_status = doc.inspection_status || "Pending";
		const repair_status = doc.repair_status || "Pending";
		const billing_total = flt(doc.billing_total || 0);
		const quotation = doc.quotation || "";
		const sales_invoice = doc.sales_invoice || "";
		const received_date = doc.received_date || card.creation || "";

		// Priority pill
		const p_lower = String(priority).toLowerCase();
		let p_class = "garage-kpill-normal";
		if (p_lower === "urgent") p_class = "garage-kpill-urgent";
		else if (p_lower === "high") p_class = "garage-kpill-high";
		else if (p_lower === "low") p_class = "garage-kpill-low";

		const priority_badge = `<span class="garage-kpill ${p_class}"><span class="kdot"></span>${frappe.utils.escape_html(priority)}</span>`;

		// Date badge
		let date_html = "";
		if (received_date) {
			const raw_date = String(received_date).split(" ")[0];
			const display_date = frappe.datetime?.str_to_user ? frappe.datetime.str_to_user(raw_date) : raw_date;
			date_html = `<span class="garage-kcard-date" title="${received_date}"><i class="fa fa-calendar-o mr-1"></i>${display_date}</span>`;
		}

		// Mobile phone link
		let mobile_html = "";
		if (mobile_no) {
			mobile_html = `<a href="tel:${frappe.utils.escape_html(mobile_no)}" class="garage-kcard-phone" title="${__("Call {0}", [mobile_no])}"><i class="fa fa-phone mr-1"></i>${frappe.utils.escape_html(mobile_no)}</a>`;
		}

		// Tags (Job Type & Vehicle)
		let tags_html = "";
		if (job_type || vehicle) {
			tags_html = `<div class="garage-kcard-tags">
				${job_type ? `<span class="garage-ktag garage-ktag-job" title="${__("Job Type")}"><i class="fa fa-wrench mr-1"></i>${frappe.utils.escape_html(job_type)}</span>` : ""}
				${vehicle ? `<span class="garage-ktag garage-ktag-vehicle ellipsis" title="${__("Vehicle / Engine: {0}", [vehicle])}"><i class="fa fa-truck mr-1"></i>${frappe.utils.escape_html(vehicle)}</span>` : ""}
			</div>`;
		}

		// Complaint
		let complaint_html = "";
		if (complaint && String(complaint).trim()) {
			complaint_html = `<div class="garage-kcard-complaint" title="${frappe.utils.escape_html(complaint)}"><i class="fa fa-exclamation-circle mr-1"></i><span>${frappe.utils.escape_html(complaint)}</span></div>`;
		}

		// Operations Badges
		function get_op_badge(label, status) {
			let badge_class = "garage-kbadge-muted";
			let icon = "fa-clock-o";
			if (status === "Completed") {
				badge_class = "garage-kbadge-success";
				icon = "fa-check";
			} else if (status === "In Progress") {
				badge_class = "garage-kbadge-warning";
				icon = "fa-cog";
			} else if (status === "Testing") {
				badge_class = "garage-kbadge-info";
				icon = "fa-flask";
			}
			return `<span class="garage-kbadge ${badge_class}" title="${label}: ${status}"><i class="fa ${icon} mr-1"></i>${label}: ${status}</span>`;
		}

		const inspection_badge = get_op_badge(__("Insp"), inspection_status);
		const repair_badge = get_op_badge(__("Repair"), repair_status);

		// Commercial links & billing
		let comm_html = "";
		const has_comm = billing_total > 0 || quotation || sales_invoice;
		if (has_comm) {
			const bill_str = format_currency(billing_total, frappe.defaults?.get_default("currency") || "SAR");
			comm_html = `<div class="garage-kcard-commercial">
				${billing_total > 0 ? `<span class="garage-kcard-bill-pill" title="${__("Billing Total")}"><i class="fa fa-tag mr-1"></i>${bill_str}</span>` : ""}
				${quotation ? `<a href="/app/quotation/${encodeURIComponent(quotation)}" class="garage-kcard-doc-pill" title="${__("Quotation")}"><i class="fa fa-file-text-o mr-1"></i>${frappe.utils.escape_html(quotation)}</a>` : ""}
				${sales_invoice ? `<a href="/app/sales-invoice/${encodeURIComponent(sales_invoice)}" class="garage-kcard-doc-pill garage-kcard-doc-inv" title="${__("Sales Invoice")}"><i class="fa fa-check-circle mr-1"></i>${frappe.utils.escape_html(sales_invoice)}</a>` : ""}
			</div>`;
		}

		const rich_html = `
			<div class="garage-kanban-card">
				<div class="garage-kcard-header">
					<a href="${form_link}" class="garage-kcard-id" title="${__("Open Service Request")}">${frappe.utils.escape_html(name)}</a>
					<div class="garage-kcard-header-right">
						${priority_badge}
					</div>
				</div>
				<div class="garage-kcard-customer-row">
					<a href="${form_link}" class="garage-kcard-cust-name" title="${frappe.utils.escape_html(customer_name)}">
						<i class="fa fa-user-circle mr-1 text-primary"></i><span>${frappe.utils.escape_html(customer_name)}</span>
					</a>
				</div>
				${(mobile_html || date_html) ? `
				<div class="garage-kcard-meta-subrow">
					${mobile_html}
					${date_html}
				</div>` : ""}
				${tags_html}
				${complaint_html}
				<div class="garage-kcard-ops">
					${inspection_badge}
					${repair_badge}
				</div>
				${comm_html}
			</div>
		`;

		// Preserve existing Frappe assignments & like button
		const $meta_actions = $card.find(".kanban-assignments, .like-action, .list-comment-count").detach();

		$card.empty().append(rich_html);

		// Append assignees & like footer if present, or provide the container so Frappe can populate it
		const $meta_container = $('<div class="kanban-card-meta garage-kcard-footer"></div>');
		if ($meta_actions.length) {
			$meta_container.append($meta_actions);
		}
		$card.find(".garage-kanban-card").append($meta_container);
		$card_wrapper.data("garage-enhanced", 1);

		// Click handlers
		$card.find(".garage-kcard-id, .garage-kcard-cust-name").on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			frappe.set_route("service-request", name);
		});
		$card.find(".garage-kcard-doc-pill").on("click", (e) => {
			e.preventDefault();
			e.stopPropagation();
			const href = $(e.currentTarget).attr("href");
			if (href) {
				frappe.set_route(href.replace(/^\/app\//, "").split("/"));
			}
		});
		$card.find(".garage-kcard-phone, .kanban-card-meta").on("click mousedown", (e) => {
			e.stopPropagation();
		});
	}

	function restyle_service_request_cards() {
		if (!is_service_request_kanban()) return;

		$(".kanban-card-wrapper").each(function () {
			const $wrapper = $(this);
			if ($wrapper.find(".garage-kanban-card").length) return;

			const name = decodeURIComponent($wrapper.attr("data-name") || "");
			if (!name) return;

			let doc = {};
			if (cur_list?.data && Array.isArray(cur_list.data)) {
				const d = cur_list.data.find((d) => d.name === name);
				if (d) doc = Object.assign({}, d);
			}
			if (cur_list?.board?.cards && Array.isArray(cur_list.board.cards)) {
				const c = cur_list.board.cards.find((c) => c.name === name);
				if (c?.doc) doc = Object.assign({}, c.doc, doc);
				else if (c) doc = Object.assign({}, c, doc);
			}
			if (frappe.model) {
				const d = frappe.model.get_doc("Service Request", name);
				if (d) doc = Object.assign({}, d, doc);
			}

			render_rich_service_request_card({ name, doctype: "Service Request", doc }, $wrapper);
		});
	}

	function enable_camera_for_attach_image() {
		if (frappe.ui?.form?.ControlAttachImage && !frappe.ui.form.ControlAttachImage.__camera_enabled) {
			const orig_set_upload = frappe.ui.form.ControlAttachImage.prototype.set_upload_options;
			frappe.ui.form.ControlAttachImage.prototype.set_upload_options = function () {
				orig_set_upload.call(this);
				this.upload_options.allow_take_photo = true;
			};
			frappe.ui.form.ControlAttachImage.__camera_enabled = true;
		}
	}

	function is_garage_dashboard() {
		const path = (window.location.pathname || "").toLowerCase();
		const route = frappe.get_route() || [];
		if (path.includes("dashboard-view/garage") || (route[0] === "dashboard-view" && route[1]?.toLowerCase() === "garage")) {
			return true;
		}
		if (route[0] === "dashboard-view" && frappe.dashboard?.dashboard_name?.toLowerCase() === "garage") {
			return true;
		}
		return false;
	}

	function render_garage_dashboard_links() {
		if (!is_garage_dashboard()) {
			$("#garage-dashboard-links-bottom").remove();
			return;
		}

		const $container = $(".dashboard .dashboard-graph, .dashboard-graph").filter(":visible").first();
		if (!$container.length) return;

		if ($("#garage-dashboard-links-bottom").length) {
			if ($container.children().last().attr("id") !== "garage-dashboard-links-bottom") {
				$("#garage-dashboard-links-bottom").appendTo($container);
			}
			return;
		}

		const icon_arrow = frappe.utils?.icon
			? frappe.utils.icon("es-line-arrow-up-right", "xs", "", "", "ml-2")
			: `<span class="link-arrow">↗</span>`;

		const sections = [
			{
				title: "Workshop",
				links: [
					{ label: "Service Request", url: "/app/service-request" },
					{ label: "Inspection", url: "/app/inspection" },
					{ label: "Repair Job", url: "/app/repair-job" },
					{ label: "Customer", url: "/app/customer" },
					{ label: "Contact", url: "/app/contact" },
				],
			},
			{
				title: "Commercial",
				links: [
					{ label: "Quotation", url: "/app/quotation" },
					{ label: "Sales Invoice", url: "/app/sales-invoice" },
					{ label: "Payment Entry", url: "/app/payment-entry" },
				],
			},
			{
				title: "Reports",
				links: [
					{ label: "Garage Jobs In Progress", url: "/app/query-report/Garage Jobs In Progress" },
					{ label: "Garage Completed Jobs", url: "/app/query-report/Garage Completed Jobs" },
					{ label: "Garage Technician Performance", url: "/app/query-report/Garage Technician Performance" },
					{ label: "Garage Repeat Repairs", url: "/app/query-report/Garage Repeat Repairs" },
					{ label: "Garage Parts Sold", url: "/app/query-report/Garage Parts Sold" },
					{ label: "Accounts Receivable", url: "/app/query-report/Accounts Receivable" },
				],
			},
			{
				title: "Masters & Setup",
				links: [
					{ label: "Job Type", url: "/app/job-type" },
					{ label: "Part Type", url: "/app/part-type" },
					{ label: "Inspection Finding", url: "/app/inspection-finding" },
					{ label: "Item", url: "/app/item" },
					{ label: "Item Group", url: "/app/item-group" },
					{ label: "Service Job Settings", url: "/app/service-job-settings" },
				],
			},
		];

		const cards_html = sections
			.map(
				(section) => `
			<div class="widget links-widget-box">
				<div class="widget-head">
					<div class="widget-label">
						<div class="widget-title"><span class="ellipsis">${section.title}</span></div>
					</div>
				</div>
				<div class="widget-body">
					${section.links
						.map(
							(link) => `
						<a href="${link.url}" class="link-item ellipsis" title="${link.label}">
							<span class="link-content ellipsis">
								<span class="link-text">${link.label}</span>
								${icon_arrow}
							</span>
						</a>
					`
						)
						.join("")}
				</div>
			</div>
		`
			)
			.join("");

		const full_html = `
			<div id="garage-dashboard-links-bottom" class="garage-dashboard-links-section">
				<div class="garage-links-header">Workshop Links</div>
				<div class="garage-dashboard-links-grid">
					${cards_html}
				</div>
			</div>
		`;

		$container.append(full_html);
	}

	window.render_garage_dashboard_links = render_garage_dashboard_links;
	frappe.provide("frappe.garage");
	frappe.garage.render_dashboard_links = render_garage_dashboard_links;

	$(document).on("click", "#garage-dashboard-links-bottom .link-item", function (e) {
		const href = $(this).attr("href");
		if (href && href.startsWith("/app/")) {
			e.preventDefault();
			frappe.set_route(href.replace(/^\/app\//, "").split("/"));
		}
	});

	frappe.router.on("change", () => {
		patch_kanban_card();
		if (is_service_request_kanban()) {
			setTimeout(restyle_service_request_cards, 100);
			setTimeout(restyle_service_request_cards, 350);
			setTimeout(restyle_service_request_cards, 800);
		}
		if (is_garage_dashboard()) {
			setTimeout(render_garage_dashboard_links, 100);
			setTimeout(render_garage_dashboard_links, 400);
			setTimeout(render_garage_dashboard_links, 1000);
		} else {
			$("#garage-dashboard-links-bottom").remove();
		}
	});

	setInterval(() => {
		patch_kanban_card();
		if (is_service_request_kanban()) {
			restyle_service_request_cards();
		}
		if (is_garage_dashboard()) {
			const $container = $(".dashboard .dashboard-graph");
			if ($container.length) {
				if (!$("#garage-dashboard-links-bottom").length) {
					render_garage_dashboard_links();
				} else if ($container.children().last().attr("id") !== "garage-dashboard-links-bottom") {
					$("#garage-dashboard-links-bottom").appendTo($container);
				}
			}
		} else if ($("#garage-dashboard-links-bottom").length) {
			$("#garage-dashboard-links-bottom").remove();
		}
	}, 350);

	$(document).on("app_ready", () => {
		patch_kanban_card();
		enable_camera_for_attach_image();
		if (is_service_request_kanban()) {
			setTimeout(restyle_service_request_cards, 150);
		}
		if (is_garage_dashboard()) {
			render_garage_dashboard_links();
		}
	});

	const observer = new MutationObserver(() => {
		if (is_service_request_kanban()) {
			restyle_service_request_cards();
		}
		if (is_garage_dashboard()) {
			const $container = $(".dashboard .dashboard-graph");
			if ($container.length && (!$("#garage-dashboard-links-bottom").length || $container.children().last().attr("id") !== "garage-dashboard-links-bottom")) {
				render_garage_dashboard_links();
			}
		}
	});

	$(document).ready(() => {
		patch_kanban_card();
		enable_camera_for_attach_image();
		if (is_service_request_kanban()) {
			setTimeout(restyle_service_request_cards, 150);
		}
		if (is_garage_dashboard()) {
			render_garage_dashboard_links();
		}
		const board = document.querySelector(".kanban") || document.body;
		observer.observe(board, { childList: true, subtree: true });
	});
})();
