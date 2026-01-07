frappe.ui.form.on("Account", {
	refresh(frm) {
		frm.trigger("toggle_schedule_field");
	},

	is_group(frm) {
		frm.trigger("toggle_schedule_field");
	},

	toggle_schedule_field(frm) {
		// Show Schedule ONLY if is_group is checked
		frm.toggle_display("schedule", !!frm.doc.is_group);

		// Optional: clear schedule when not a group
		if (!frm.doc.is_group && frm.doc.schedule) {
			frm.set_value("schedule", null);
		}
	}
});
