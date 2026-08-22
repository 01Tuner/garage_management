frappe.listview_settings["Inspection"] = {
	add_fields: ["status", "customer_name", "assigned_to", "service_request"],
	get_indicator(doc) {
		const colors = {
			Draft: "gray",
			"In Progress": "cyan",
			Completed: "green",
			Cancelled: "red",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
