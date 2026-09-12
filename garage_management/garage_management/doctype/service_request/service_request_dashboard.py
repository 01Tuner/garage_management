# Copyright (c) 2026, rafeeq and contributors
# For license information, please see license.txt

from frappe import _


def get_data():
	return {
		"fieldname": "service_request",
		"transactions": [
			{
				"label": _("Operations"),
				"items": ["Inspection", "Repair Job"],
			},
			{
				"label": _("Commercial"),
				"items": ["Quotation", "Sales Invoice"],
			},
		],
	}
