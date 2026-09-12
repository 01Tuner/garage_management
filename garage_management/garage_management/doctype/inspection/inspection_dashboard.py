# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "inspection",
		"internal_links": {
			"Service Request": "service_request",
		},
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["Service Request", "Repair Job"],
			},
		],
	}
