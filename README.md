# Bureau of Internal Revenue (BIR)

A custom **Frappe application** developed by **Ambibuzz Technologies LLP** that replicates and extends standard ERPNext financial reports to support **Bureau of Internal Revenue (BIR)**– Philippines(PHP) style statutory reporting and presentation requirements.

The application focuses on compliance-friendly reporting while keeping ERPNext core code untouched and upgrade-safe.


---

## Purpose

ERPNext’s standard financial reports are functionally correct but often require:
- Simplified hierarchical views for statutory submissions
- Presentation-specific formatting
- Compliance-aligned terminology

This app **replicates standard ERPNext reports** (starting with the Balance Sheet) and applies controlled, non-destructive customizations tailored for BIR-style reporting.

---

## Included Reports

### Balance Sheet BIR

A replicated version of ERPNext’s standard **Balance Sheet** report with additional presentation and filtering capabilities.

#### Key Features

- Replicated from ERPNext Balance Sheet (no core overrides)
- Built using `erpnext.accounts.report.financial_statements`
- Level-based account hierarchy filtering
- Presentation-only hiding of zero or parent-level amounts: display details only up to Level 3, roll up deeper levels into Level 3, hide lower-level accounts and Level 1 totals at the bottom.
- Custom label renaming to match BIR terminology
- Safe for ERPNext and Frappe upgrades

---

## Design Principles

- **No Core Modifications** – ERPNext source code remains untouched  
- **Presentation Focused** – formatting does not affect ledger data  
- **Upgrade Safe** – compatible with future upgrades  
- **Extensible** – easy to add more BIR-aligned reports  

---

## Supported Versions

- **Frappe Framework**: v15  
- **ERPNext**: v15  

---

## Installation

### 1. Get the App

From your bench directory:

```bash
bench get-app bureau_of_internal_revenue https://github.com/Ambibuzz/bureau_of_internal_revenue.git