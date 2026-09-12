# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "repair_job",
		"internal_links": {
			"Service Request": "service_request",
			"Inspection": "inspection",
		},
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["Service Request", "Inspection"],
			},
		],
	}
