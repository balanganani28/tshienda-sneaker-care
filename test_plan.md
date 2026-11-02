# Tshienda Sneaker Care - Quality Assurance & Test Plan

## 1. Scope & Objectives
Verify the end-to-end functionality, security, POPIA compliance, and performance of the Tshienda Sneaker Care platform across public pages, tracking system, staff portal, and WhatsApp workflows.

---

## 2. Test Matrix

### A. Authentication & Security
| Test ID | Scenario | Expected Outcome | Status |
| :--- | :--- | :--- | :--- |
| SEC-01 | Login with valid credentials | User authenticated, redirected to dashboard with role badge. | PASS |
| SEC-02 | Login with incorrect password | Error shown; failed attempt recorded. | PASS |
| SEC-03 | 5 consecutive failed logins | Account locked for 15 minutes; lockout banner displayed. | PASS |
| SEC-04 | CSRF Protection | Form submissions without valid CSRF token rejected. | PASS |
| SEC-05 | Public order enumeration | Hard-to-guess random codes (`TSH-XXXXX`) + rate limit of 15 req/min. | PASS |
| SEC-06 | Phone number leakage test | Customer phone numbers strictly excluded from public tracking HTML. | PASS |
---
### B. Customer Intake & QR Tags
| Test ID | Scenario | Expected Outcome | Status |
| :--- | :--- | :--- | :--- |
| INT-01 | Drop-off without POPIA consent | Form validation blocks submission; consent checkbox required. | PASS |
| INT-02 | Invalid SA phone format | Validation error on numbers not matching `0[678]...` or `27[678]...`. | PASS |
| INT-03 | Order creation & price math | Multi-pair price correctly calculated from database price setting. | PASS |
| INT-04 | QR tag generation | High-contrast QR tag rendered; encodes valid tracking URL. | PASS |
| INT-05 | Label print style | `@media print` layout formats 80x55mm thermal/paper label. | PASS |

### C. Camera Scanning & Stage Progression
| Test ID | Scenario | Expected Outcome | Status |
| :--- | :--- | :--- | :--- |
| SCN-01 | Camera scan of QR code | BarcodeDetector decodes order; audio beep triggered; order card loaded. | PASS |
| SCN-02 | Manual code fallback | Staff enters code manually; retrieves matching order. | PASS |
| SCN-03 | 1-Tap stage progression | Moves order from current stage to next; logs staff user & timestamp. | PASS |
| SCN-04 | Terminal stage check | Order marked "Collected" cannot advance further. | PASS |

### D. WhatsApp Notifications
| Test ID | Scenario | Expected Outcome | Status |
| :--- | :--- | :--- | :--- |
| WA-01 | Phase 1 wa.me link generation | Generates clean `https://wa.me/27...` link with prefilled template. | PASS |
| WA-02 | Template variable substitution | `{name}`, `{order_number}`, `{stage}`, `{service}` correctly replaced. | PASS |
| WA-03 | Phase 2 feature flag disabled | Returns `skipped` status when `WHATSAPP_CLOUD_API_ENABLED=false`. | PASS |
| WA-04 | Webhook verification GET | Responds with `hub.challenge` when verify token matches. | PASS |

### E. POPIA Data Retention
| Test ID | Scenario | Expected Outcome | Status |
| :--- | :--- | :--- | :--- |
| POP-01 | Cleanup orders > 12 months | Customers with orders collected > 12 months ago have phones set to NULL. | PASS |
| POP-02 | Self-service deletion request | Customer requests erasure at `/privacy/request-deletion`; phone purged. | PASS |
