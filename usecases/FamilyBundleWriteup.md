# Maple Square Application Dataset

## Overview
Synthetic dataset of 5 families and 5 document bundles generated from the Maple Square affordable housing application. 2 passing cases, 3 failing cases.

---

## Families

| Family | Name | Status | Reason |
|--------|------|--------|--------|
| family_1 | James & Sara Hartley | PASS | Complete |
| family_2 | Dorothy Nguyen | PASS | Complete |
| family_3 | Marcus Webb | FAIL | Missing pay stubs 4 & 5 |
| family_4 | Priya Patel | FAIL | Missing federal tax return and W2/1099-R |
| family_5 | Carlos & Maria Rivera | FAIL | No household member ID submitted |

---

## Bundles

| Bundle | Documents | Status | Gap |
|--------|-----------|--------|-----|
| bundle_1 | 17 | PASS | None |
| bundle_2 | 19 | PASS | None |
| bundle_3 | 17 | FAIL | pay_stub_4.pdf, pay_stub_5.pdf |
| bundle_4 | 15 | FAIL | federal_tax_return_2024.pdf, w2_2024.pdf |
| bundle_5 | 15 | FAIL | Any household member ID (needs 2 for 2-person household) |

> Every bundle includes the three universal documents (`affidavit_and_disclosure_form.pdf`, `application_tips_signed.pdf`, `release_of_information_authorization.pdf`) that the always-on triggers `trig_affidavit_and_disclosure`, `trig_application_tips`, and `trig_release_of_information` require for any non-empty household.

---

## Sample Pairings

| family_id | bundle_id | pass |
|-----------|-----------|------|
| family_1 | bundle_1 | true |
| family_2 | bundle_2 | true |
| family_3 | bundle_3 | false |
| family_4 | bundle_4 | false |
| family_5 | bundle_5 | false |