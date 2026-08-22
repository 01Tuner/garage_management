/**
 * Richer Service Request Kanban card body: related docs as links,
 * truncated complaint, emphasised bill amount.
 */
(() => {
	function patch_kanban_card() {
		if (!frappe.views?.KanbanBoardCard || frappe.views.KanbanBoardCard.__garage_patched) {
			return;
		}

		const Original = frappe.views.KanbanBoardCard;
		frappe.views.KanbanBoardCard = function (card, wrapper) {
			if (
				card?.doctype === "Service Request" &&
				cur_list?.board?.name === "Service Request by Status"
			) {
				enhance_card_doc(card);
			}
			return Original(card, wrapper);
		};
		frappe.views.KanbanBoardCard.__garage_patched = true;
	}

	function enhance_card_doc(card) {
		if (!card.doc) return;

		if (card.doc.complaint && card.doc.complaint.length > 90) {
			card.doc.complaint = card.doc.complaint.substring(0, 87) + "…";
		}
	}

	function restyle_service_request_cards() {
		if (cur_list?.doctype !== "Service Request") return;

		$(".kanban-card").each(function () {
			const $card = $(this);
			if ($card.data("garage-enhanced")) return;
			$card.data("garage-enhanced", 1);

			$card.find(".kanban-card-body .text-muted").each(function () {
				const $row = $(this);
				const text = $row.text() || "";
				const $link = $row.find("a");

				if (text.includes("Billing Total") || text.includes("Bill")) {
					$row.addClass("garage-kanban-amount");
				}
				if (text.includes("Complaint")) {
					$row.addClass("garage-kanban-complaint");
					$row.removeClass("text-truncate");
				}
				if (
					$link.length &&
					(text.includes("Quotation") ||
						text.includes("Sales Order") ||
						text.includes("Sales Invoice"))
				) {
					$row.addClass("garage-kanban-related");
					$row.removeClass("text-truncate");
					$link.attr("target", "_blank");
					$link.on("mousedown click", (e) => e.stopPropagation());
				}
			});
		});
	}

	$(document).on("app_ready", () => {
		patch_kanban_card();
	});

	const observer = new MutationObserver(() => {
		if (cur_list?.doctype === "Service Request" && cur_list?.view_name === "Kanban") {
			restyle_service_request_cards();
		}
	});

	$(document).ready(() => {
		patch_kanban_card();
		const board = document.querySelector(".kanban") || document.body;
		observer.observe(board, { childList: true, subtree: true });
	});
})();
