"""One-shot builder for the trigger and document-set-requirement catalogs.

Run from the repo root:
    python -m catalog_templates.build_catalogs

Or from inside catalog_templates/:
    python build_catalogs.py

Constructs every Trigger and DocumentSetRequirement as Pydantic objects
(so all model_validators run at build time), cross-checks that every
emits_requirements references a real requirement_id, then writes
req_catalog.json and trigger_catalog.json next to this file.

notes about handcoded

there is no way from the application to be able to trigger
if a member is receiving unemployment. this is a limitation of our MVP

in reality what they do is check against the EIV (government data platform)
which contains a bunch of info about each prospective tenant, including amt and types 
of income they receive, social security info, etc. see chat here: https://gemini.google.com/share/bccb670f4617
next-level of MVP would be some mock-EIV integration as well so there would be income matching
across three incoming data streams: submitted application, corresponding paperwork/documents, & gov't EIV

right now we are grouping #6 on page 18 as 'benefit_letters_and_social_security.pdf', essentially grouping all of 
these different types of documents together. obviously in reality these should be distinguished, but this is another 
simplification in our MVP

there are some additional documentation requirements if the family turns in Appendix A: HOTMA document
for the MVP we are just treating like every other document. If appendix A submitted we assume approval for that condition 

"""
from __future__ import annotations

from pathlib import Path
import sys

# Allow `python build_catalogs.py` from inside catalog_templates/
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).parent))
    from templates import (
        DocumentLeaf, AllOf, OneOf,
        Predicate, Any_, All_,
        SourceReference, Trigger, DocumentSetRequirement,
    )
else:
    from .templates import (
        DocumentLeaf, AllOf, OneOf,
        Predicate, Any_, All_,
        SourceReference, Trigger, DocumentSetRequirement,
    )


PDF = "Maple Square FCFS Application 2026"


# ---------------------------------------------------------------------------
# Construction helpers
# ---------------------------------------------------------------------------

def src(page: int, section: str, quote: str | None = None) -> SourceReference:
    return SourceReference(document=PDF, page=page, section=section, quote=quote)


def doc(t: str, notes: str | None = None) -> DocumentLeaf:
    return DocumentLeaf(type="document", document_type=t, notes=notes)


def all_of(*children) -> AllOf:
    return AllOf(type="all_of", children=list(children))


def one_of(*children) -> OneOf:
    return OneOf(type="one_of", children=list(children))


def pred(field: str, op: str, value=None) -> Predicate:
    return Predicate(type="predicate", field=field, operator=op, value=value)


def any_(*children) -> Any_:
    return Any_(type="any", children=list(children))


def all_cond(*children) -> All_:
    return All_(type="all", children=list(children))


# Universal "applicant exists" predicate — used for documents required of
# every applicant (Affidavit, Application Tips signature, Release of Info,
# Federal Tax Return). Mirrors the idiom used in feedback_agent/catalogs.
ALWAYS = pred("household.total_size", "greater_than", 0)


# ---------------------------------------------------------------------------
# Document-set requirements
# ---------------------------------------------------------------------------

REQUIREMENTS: list[DocumentSetRequirement] = [
    DocumentSetRequirement(
        requirement_id="req_household_member_id",
        description="Government-issued ID for each household member",
        document_spec=one_of(
            doc("birth_certificate.pdf"),
            doc("driver_license.pdf"),
            doc("social_security_card.pdf"),
            doc("passport.pdf"),
        ),
        source_reference=src(18, "Required Documents item 1"),
    ),
    DocumentSetRequirement(
        requirement_id="req_section_8_voucher",
        description="Section 8 / housing voucher: voucher copy or PHA letter",
        document_spec=one_of(
            doc("section_8_housing_voucher.pdf"),
            doc("public_housing_authority_letter.pdf"),
        ),
        source_reference=src(18, "Required Documents item 2"),
    ),
    DocumentSetRequirement(
        requirement_id="req_local_preference",
        description="Proof of local preference (lease, utility bill, voter reg.)",
        document_spec=one_of(
            doc("lease.pdf"),
            doc("utility_bill.pdf"),
            doc("voter_registration.pdf"),
        ),
        source_reference=src(18, "Required Documents item 3"),
    ),
    DocumentSetRequirement(
        requirement_id="req_special_accommodation",
        description="Doctor's letter supporting requested accommodation",
        document_spec=doc("doctors_letter.pdf"),
        source_reference=src(18, "Required Documents item 4"),
    ),
    DocumentSetRequirement(
        requirement_id="req_pay_stubs",
        description="Five most recent consecutive pay stubs",
        document_spec=all_of(
            doc("pay_stub_1.pdf", notes="5 consecutive — count is advisory"),
            doc("pay_stub_2.pdf"),
            doc("pay_stub_3.pdf"),
            doc("pay_stub_4.pdf"),
            doc("pay_stub_5.pdf"),
        ),
        source_reference=src(18, "Required Documents item 5"),
    ),
    DocumentSetRequirement(
        requirement_id="req_employment_offer_letter",
        description="Employment offer letter for jobs started in last 12 months",
        document_spec=doc("employment_offer_letter.pdf"),
        source_reference=src(18, "Required Documents item 5 NOTE"),
    ),
    DocumentSetRequirement(
        requirement_id="req_benefit_letter",
        description="Benefit letter (Social Security / pension / disability / annuity)",
        document_spec=doc("benefit_letters_and_social_security.pdf"),
        source_reference=src(18, "Required Documents item 6"),
    ),
    DocumentSetRequirement(
        requirement_id="req_child_support",
        description="Child support / alimony documentation",
        document_spec=one_of(
            doc("child_support_none_received.pdf"),
            all_of(
                doc("child_support_received.pdf"),
                doc("child_support_court_document.pdf"),
                doc("divorce_papers.pdf"),
            ),
        ),
        source_reference=src(18, "Required Documents item 7"),
    ),
    DocumentSetRequirement(
        requirement_id="req_self_employment",
        description="Self-employment income/expense statement, last 3 federal returns, 3 months business checking + savings",
        document_spec=all_of(
            doc("self_employed_income_statement.pdf"),
            doc("federal_tax_returns_2022.pdf"),
            doc("federal_tax_returns_2023.pdf"),
            doc("federal_tax_return_2024.pdf"),
            doc("last_3_months_business_checking_and_savings_statements.pdf"),
        ),
        source_reference=src(18, "Required Documents item 8"),
    ),
    DocumentSetRequirement(
        requirement_id="req_federal_tax_return",
        description="2024 federal tax return or IRS non-filing verification",
        document_spec=one_of(
            doc("federal_tax_return_2024.pdf"),
            doc("irs_non_filing_verification.pdf"),
        ),
        source_reference=src(19, "Required Documents item 9"),
    ),
    DocumentSetRequirement(
        requirement_id="req_w2_1099r",
        description="W-2 or 1099-R for 2024",
        document_spec=one_of(
            doc("w2_2024.pdf"),
            doc("1099r_2024.pdf"),
        ),
        source_reference=src(19, "Required Documents item 10"),
    ),
    DocumentSetRequirement(
        requirement_id="req_interest_dividends_income",
        description="Interest, dividends, or net income from real/personal property",
        document_spec=doc("interest_dividends_income_statement.pdf"),
        source_reference=src(19, "Required Documents item 11"),
    ),
    DocumentSetRequirement(
        requirement_id="req_checking_statement",
        description="Most recent complete checking account statement",
        document_spec=doc("checking_statement_march2025.pdf"),
        source_reference=src(19, "Required Documents item 12 — Checking"),
    ),
    DocumentSetRequirement(
        requirement_id="req_prepaid_debit_card_statement",
        description="Pre-paid debit card statement",
        document_spec=doc("prepaid_debit_card_statements.pdf"),
        source_reference=src(19, "Required Documents item 12 — Pre-paid debit"),
    ),
    DocumentSetRequirement(
        requirement_id="req_digital_wallet_statement",
        description="Digital wallet statements (Cash App / Venmo / PayPal / Apple Cash)",
        document_spec=doc("digital_wallet_statements.pdf"),
        source_reference=src(19, "Required Documents item 12 — Digital wallets"),
    ),
    DocumentSetRequirement(
        requirement_id="req_savings_statement",
        description="Most recent complete savings account statement",
        document_spec=doc("savings_statement_march2025.pdf"),
        source_reference=src(20, "Required Documents item 12 — Savings"),
    ),
    DocumentSetRequirement(
        requirement_id="req_revocable_trusts",
        description="Revocable trust statement",
        document_spec=doc("revocable_trusts.pdf"),
        source_reference=src(20, "Required Documents item 12 — Revocable trusts"),
    ),
    DocumentSetRequirement(
        requirement_id="req_equity_rental_or_capital_investments",
        description="Equity in rental property or other capital investments",
        document_spec=doc("equity_rental_or_capital_investments.pdf"),
        source_reference=src(20, "Required Documents item 12 — Equity/rental"),
    ),
    DocumentSetRequirement(
        requirement_id="req_investment_accounts",
        description="Investment accounts (stocks, bonds, T-bills, CDs, mutual funds, online accounts)",
        document_spec=doc("investment_accounts.pdf"),
        source_reference=src(20, "Required Documents item 12 — Investments"),
    ),
    DocumentSetRequirement(
        requirement_id="req_retirement_accounts",
        description="Retirement account statements (IRA / Roth / 401K / 403B)",
        document_spec=doc("retirement_accounts.pdf"),
        source_reference=src(20, "Required Documents item 12 — Retirement"),
    ),
    DocumentSetRequirement(
        requirement_id="req_life_insurance_cash_value",
        description="Cash value of whole-life or universal-life insurance",
        document_spec=doc("life_insurance_cash_value.pdf"),
        source_reference=src(20, "Required Documents item 12 — Life insurance"),
    ),
    DocumentSetRequirement(
        requirement_id="req_personal_property_investment",
        description="Personal property held as an investment",
        document_spec=doc("personal_property_investments.pdf"),
        source_reference=src(20, "Required Documents item 12 — Personal property"),
    ),
    DocumentSetRequirement(
        requirement_id="req_lump_sum_one_time_receipts",
        description="Lump-sum or one-time receipts",
        document_spec=doc("lump_sum_one_time_receipts.pdf"),
        source_reference=src(20, "Required Documents item 12 — Lump sum"),
    ),
    DocumentSetRequirement(
        requirement_id="req_student_status_proof",
        description="Letter from school confirming student status",
        document_spec=doc("student_letter_from_school.pdf"),
        source_reference=src(20, "Required Documents item 13"),
    ),
    DocumentSetRequirement(
        requirement_id="req_appendix_a_eligibility",
        description="HOTMA Appendix A student eligibility checklist (non-Section-8 students)",
        document_spec=doc("appendix_A_eligibility.pdf"),
        source_reference=src(20, "Required Documents item 13 / Appendix A"),
    ),
    DocumentSetRequirement(
        requirement_id="req_proof_of_pregnancy",
        description="Doctor's letter as proof of pregnancy (unborn member counted in household)",
        document_spec=doc("proof_of_pregnancy.pdf"),
        source_reference=src(20, "Required Documents item 14"),
    ),
    DocumentSetRequirement(
        requirement_id="req_divorce_or_separation",
        description="Legal documentation of divorce or separation status",
        document_spec=doc("proof_of_divorce.pdf"),
        source_reference=src(20, "Required Documents item 15"),
    ),
    DocumentSetRequirement(
        requirement_id="req_affidavit_and_disclosure",
        description="Signed Affidavit & Disclosure Form",
        document_spec=doc("affidavit_and_disclosure_form.pdf"),
        source_reference=src(15, "Affidavit & Disclosure Form"),
    ),
    DocumentSetRequirement(
        requirement_id="req_application_tips",
        description="Signed Application Tips acknowledgement",
        document_spec=doc("application_tips_signed.pdf"),
        source_reference=src(17, "Application Tips"),
    ),
    DocumentSetRequirement(
        requirement_id="req_release_of_information",
        description="Signed Release of Information Authorization Form",
        document_spec=doc("release_of_information_authorization.pdf"),
        source_reference=src(24, "Release of Information Authorization Form"),
    ),
    DocumentSetRequirement(
        requirement_id="req_custody_child_support_affidavit",
        description="Custody & Child Support Affidavit, one per minor",
        document_spec=doc("custody_child_support_affidavit.pdf"),
        source_reference=src(25, "Custody & Child Support Affidavit"),
    ),
]


# ---------------------------------------------------------------------------
# Triggers
# ---------------------------------------------------------------------------

# A "name exists" predicate used as the per_member tautology — every member
# in the input schema has a name field, so this matches every member.
EVERY_MEMBER = pred("name", "exists")


TRIGGERS: list[Trigger] = [
    Trigger(
        trigger_id="trig_household_member_id",
        description="Every household member needs identification",
        activation=ALWAYS,
        emits_requirements=["req_household_member_id"],
        instance_scope="per_member",
        per_member_scope=EVERY_MEMBER,
        source_reference=src(18, "Required Documents item 1"),
    ),

    # --- Section 8 voucher (checklist + structured overlay) ---
    Trigger(
        trigger_id="trig_section_8_voucher_checklist",
        description="Self-attested Section 8 / voucher → require voucher proof",
        activation=pred("eligibility_checklist.section_8_or_housing_voucher", "equals", True),
        emits_requirements=["req_section_8_voucher"],
        source_reference=src(18, "Required Documents item 2"),
    ),
    Trigger(
        trigger_id="trig_section_8_voucher_structured",
        description="Structured Section 8 / voucher field → require voucher proof",
        activation=pred("personal_information.section_8_or_housing_voucher", "equals", True),
        emits_requirements=["req_section_8_voucher"],
        source_reference=src(13, "Personal Information — Section 8"),
    ),

    Trigger(
        trigger_id="trig_local_preference",
        description="Self-attested local preference → require proof",
        activation=pred("eligibility_checklist.proof_of_local_preference", "equals", True),
        emits_requirements=["req_local_preference"],
        source_reference=src(18, "Required Documents item 3"),
    ),

    # --- Special accommodation (checklist + structured overlay incl. wheelchair) ---
    Trigger(
        trigger_id="trig_special_accommodation_checklist",
        description="Self-attested special-accommodation → require doctor's letter",
        activation=pred("eligibility_checklist.special_accommodation_documentation", "equals", True),
        emits_requirements=["req_special_accommodation"],
        source_reference=src(18, "Required Documents item 4"),
    ),
    Trigger(
        trigger_id="trig_special_accommodation_structured",
        description="Special-accommodation or wheelchair-accessible request on form → require doctor's letter",
        activation=any_(
            pred("personal_information.requires_special_accommodation", "equals", True),
            pred("personal_information.requires_wheelchair_accessible_unit", "equals", True),
        ),
        emits_requirements=["req_special_accommodation"],
        source_reference=src(13, "Personal Information — Accommodation"),
    ),

    # --- Pay stubs (checklist + structured overlay) ---
    Trigger(
        trigger_id="trig_pay_stubs_checklist",
        description="Self-attested wage income → require 5 consecutive pay stubs",
        activation=pred("eligibility_checklist.pay_stubs", "equals", True),
        emits_requirements=["req_pay_stubs"],
        source_reference=src(18, "Required Documents item 5"),
    ),
    Trigger(
        trigger_id="trig_pay_stubs_structured",
        description="Date-of-hire present in employment → require pay stubs (sanity overlay)",
        activation=pred("employment.date_of_hire", "exists"),
        emits_requirements=["req_pay_stubs"],
        source_reference=src(14, "Employment Status — Date of Hire"),
    ),

    Trigger(
        trigger_id="trig_employment_offer_letter",
        description="Date-of-hire present (interpreted as last 12 months for MVP) → offer letter",
        activation=pred("employment.date_of_hire", "exists"),
        emits_requirements=["req_employment_offer_letter"],
        source_reference=src(18, "Required Documents item 5 NOTE"),
    ),

    Trigger(
        trigger_id="trig_benefit_letter",
        description="Self-attested periodic benefit income → require benefit letter",
        activation=pred("eligibility_checklist.benefit_letter", "equals", True),
        emits_requirements=["req_benefit_letter"],
        source_reference=src(18, "Required Documents item 6"),
    ),

    Trigger(
        trigger_id="trig_child_support",
        description="Self-attested child support / alimony → require court doc or none-received letter",
        activation=pred("eligibility_checklist.child_support_alimony", "equals", True),
        emits_requirements=["req_child_support"],
        source_reference=src(18, "Required Documents item 7"),
    ),

    Trigger(
        trigger_id="trig_self_employment",
        description="Self-attested self-employment → income statement + 3 yrs returns + business statements",
        activation=pred("eligibility_checklist.self_employment", "equals", True),
        emits_requirements=["req_self_employment"],
        source_reference=src(18, "Required Documents item 8"),
    ),

    Trigger(
        trigger_id="trig_federal_tax_return",
        description="Federal tax return required of every applicant",
        activation=ALWAYS,
        emits_requirements=["req_federal_tax_return"],
        source_reference=src(19, "Required Documents item 9"),
    ),

    Trigger(
        trigger_id="trig_w2_1099r",
        description="Self-attested W-2 / 1099-R → require the form",
        activation=pred("eligibility_checklist.w2_1099r", "equals", True),
        emits_requirements=["req_w2_1099r"],
        source_reference=src(19, "Required Documents item 10"),
    ),

    Trigger(
        trigger_id="trig_interest_dividends_income",
        description="Self-attested interest/dividends OR equity-rental balance > 0 → require statement",
        activation=any_(
            pred("eligibility_checklist.interest_dividends_income", "equals", True),
            pred("assets.equity_rental_or_capital_investments", "greater_than", 0),
        ),
        emits_requirements=["req_interest_dividends_income"],
        source_reference=src(19, "Required Documents item 11"),
    ),

    # --- Asset-statement triggers (checklist + structured balance overlay) ---
    Trigger(
        trigger_id="trig_checking_checklist",
        description="Self-attested checking account → require statement",
        activation=pred("eligibility_checklist.checking_account_statements", "equals", True),
        emits_requirements=["req_checking_statement"],
        source_reference=src(19, "Required Documents item 12 — Checking"),
    ),
    Trigger(
        trigger_id="trig_checking_structured",
        description="Structured checking balance > 0 → require statement",
        activation=pred("assets.checking", "greater_than", 0),
        emits_requirements=["req_checking_statement"],
        source_reference=src(14, "Household Assets — Checking"),
    ),
    Trigger(
        trigger_id="trig_prepaid_debit_card_checklist",
        description="Self-attested pre-paid debit card → require statement",
        activation=pred("eligibility_checklist.prepaid_debit_card_statements", "equals", True),
        emits_requirements=["req_prepaid_debit_card_statement"],
        source_reference=src(19, "Required Documents item 12 — Pre-paid debit"),
    ),
    Trigger(
        trigger_id="trig_prepaid_debit_card_structured",
        description="Structured debit-card balance > 0 → require statement",
        activation=pred("assets.debit_card", "greater_than", 0),
        emits_requirements=["req_prepaid_debit_card_statement"],
        source_reference=src(14, "Household Assets — Debit Card"),
    ),
    Trigger(
        trigger_id="trig_digital_wallet",
        description="Self-attested digital wallet → require statements",
        activation=pred("eligibility_checklist.digital_wallet_statements", "equals", True),
        emits_requirements=["req_digital_wallet_statement"],
        source_reference=src(19, "Required Documents item 12 — Digital wallets"),
    ),
    Trigger(
        trigger_id="trig_savings_checklist",
        description="Self-attested savings account → require statement",
        activation=pred("eligibility_checklist.savings_account_statements", "equals", True),
        emits_requirements=["req_savings_statement"],
        source_reference=src(20, "Required Documents item 12 — Savings"),
    ),
    Trigger(
        trigger_id="trig_savings_structured",
        description="Structured savings balance > 0 → require statement",
        activation=pred("assets.savings", "greater_than", 0),
        emits_requirements=["req_savings_statement"],
        source_reference=src(14, "Household Assets — Savings"),
    ),
    Trigger(
        trigger_id="trig_revocable_trusts_checklist",
        description="Self-attested revocable trust → require statement",
        activation=pred("eligibility_checklist.revocable_trusts", "equals", True),
        emits_requirements=["req_revocable_trusts"],
        source_reference=src(20, "Required Documents item 12 — Revocable trusts"),
    ),
    Trigger(
        trigger_id="trig_revocable_trusts_structured",
        description="Structured revocable-trusts balance > 0 → require statement",
        activation=pred("assets.revocable_trusts", "greater_than", 0),
        emits_requirements=["req_revocable_trusts"],
        source_reference=src(14, "Household Assets — Revocable trusts"),
    ),
    Trigger(
        trigger_id="trig_equity_rental_checklist",
        description="Self-attested equity/rental investment → require statement",
        activation=pred("eligibility_checklist.equity_rental_or_capital_investments", "equals", True),
        emits_requirements=["req_equity_rental_or_capital_investments"],
        source_reference=src(20, "Required Documents item 12 — Equity/rental"),
    ),
    Trigger(
        trigger_id="trig_equity_rental_structured",
        description="Structured equity/rental balance > 0 → require statement",
        activation=pred("assets.equity_rental_or_capital_investments", "greater_than", 0),
        emits_requirements=["req_equity_rental_or_capital_investments"],
        source_reference=src(14, "Household Assets — Equity/rental"),
    ),
    Trigger(
        trigger_id="trig_investment_accounts_checklist",
        description="Self-attested investment accounts → require statement",
        activation=pred("eligibility_checklist.investment_accounts", "equals", True),
        emits_requirements=["req_investment_accounts"],
        source_reference=src(20, "Required Documents item 12 — Investments"),
    ),
    Trigger(
        trigger_id="trig_investment_accounts_structured",
        description="Structured stocks/bonds/T-bills/CDs/mutual-funds balance > 0 → require statement",
        activation=pred("assets.stocks_bonds_tbills_cd_mutual_funds", "greater_than", 0),
        emits_requirements=["req_investment_accounts"],
        source_reference=src(14, "Household Assets — Investments"),
    ),
    Trigger(
        trigger_id="trig_retirement_accounts_checklist",
        description="Self-attested retirement accounts → require statement",
        activation=pred("eligibility_checklist.retirement_accounts", "equals", True),
        emits_requirements=["req_retirement_accounts"],
        source_reference=src(20, "Required Documents item 12 — Retirement"),
    ),
    Trigger(
        trigger_id="trig_retirement_accounts_structured",
        description="Structured IRA/401K/Keogh or pension balance > 0 → require statement",
        activation=any_(
            pred("assets.ira_401k_keogh", "greater_than", 0),
            pred("assets.retirement_pension_withdrawable", "greater_than", 0),
        ),
        emits_requirements=["req_retirement_accounts"],
        source_reference=src(14, "Household Assets — Retirement"),
    ),
    Trigger(
        trigger_id="trig_life_insurance_checklist",
        description="Self-attested life-insurance cash value → require statement",
        activation=pred("eligibility_checklist.life_insurance_cash_value", "equals", True),
        emits_requirements=["req_life_insurance_cash_value"],
        source_reference=src(20, "Required Documents item 12 — Life insurance"),
    ),
    Trigger(
        trigger_id="trig_life_insurance_structured",
        description="Structured life-insurance cash value > 0 → require statement",
        activation=pred("assets.cash_value_life_insurance", "greater_than", 0),
        emits_requirements=["req_life_insurance_cash_value"],
        source_reference=src(14, "Household Assets — Life insurance"),
    ),
    Trigger(
        trigger_id="trig_personal_property_investment",
        description="Self-attested personal property as investment → require statement",
        activation=pred("eligibility_checklist.personal_property_investment", "equals", True),
        emits_requirements=["req_personal_property_investment"],
        source_reference=src(20, "Required Documents item 12 — Personal property"),
    ),
    Trigger(
        trigger_id="trig_lump_sum",
        description="Self-attested lump-sum / one-time receipts → require statement",
        activation=pred("eligibility_checklist.lump_sum_one_time_receipts", "equals", True),
        emits_requirements=["req_lump_sum_one_time_receipts"],
        source_reference=src(20, "Required Documents item 12 — Lump sum"),
    ),

    Trigger(
        trigger_id="trig_student_status",
        description="Self-attested student status → require school letter",
        activation=pred("eligibility_checklist.student_status_proof", "equals", True),
        emits_requirements=["req_student_status_proof"],
        source_reference=src(20, "Required Documents item 13"),
    ),
    Trigger(
        trigger_id="trig_appendix_a",
        description="Student AND not on Section 8 → also require HOTMA Appendix A",
        activation=all_cond(
            pred("eligibility_checklist.student_status_proof", "equals", True),
            pred("eligibility_checklist.section_8_or_housing_voucher", "equals", False),
        ),
        emits_requirements=["req_appendix_a_eligibility"],
        source_reference=src(20, "Required Documents item 13 / Appendix A"),
    ),
    Trigger(
        trigger_id="trig_pregnancy",
        description="Self-attested pregnancy → require doctor's letter",
        activation=pred("eligibility_checklist.proof_of_pregnancy", "equals", True),
        emits_requirements=["req_proof_of_pregnancy"],
        source_reference=src(20, "Required Documents item 14"),
    ),
    Trigger(
        trigger_id="trig_divorce",
        description="Self-attested divorce or separation → require legal documentation",
        activation=pred("eligibility_checklist.divorce_or_separation", "equals", True),
        emits_requirements=["req_divorce_or_separation"],
        source_reference=src(20, "Required Documents item 15"),
    ),

    # --- Universal documents required of every applicant ---
    Trigger(
        trigger_id="trig_affidavit_and_disclosure",
        description="Affidavit & Disclosure Form required of every applicant",
        activation=ALWAYS,
        emits_requirements=["req_affidavit_and_disclosure"],
        source_reference=src(15, "Affidavit & Disclosure Form"),
    ),
    Trigger(
        trigger_id="trig_application_tips",
        description="Signed Application Tips required of every applicant",
        activation=ALWAYS,
        emits_requirements=["req_application_tips"],
        source_reference=src(17, "Application Tips"),
    ),
    Trigger(
        trigger_id="trig_release_of_information",
        description="Release of Information Authorization Form required of every applicant",
        activation=ALWAYS,
        emits_requirements=["req_release_of_information"],
        source_reference=src(24, "Release of Information Authorization Form"),
    ),

    # --- Custody & Child Support Affidavit: per minor when child support attested ---
    Trigger(
        trigger_id="trig_custody_child_support_affidavit",
        description="Child support attested → custody affidavit per minor in household",
        activation=pred("eligibility_checklist.child_support_alimony", "equals", True),
        emits_requirements=["req_custody_child_support_affidavit"],
        instance_scope="per_member",
        per_member_scope=pred("age", "less_than", 18),
        source_reference=src(25, "Custody & Child Support Affidavit"),
    ),
]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _serialize(items) -> str:
    return "[\n" + ",\n".join(item.model_dump_json(indent=2) for item in items) + "\n]\n"


def main() -> None:
    out = Path(__file__).parent

    req_ids = {r.requirement_id for r in REQUIREMENTS}
    for t in TRIGGERS:
        for rid in t.emits_requirements:
            assert rid in req_ids, f"trigger {t.trigger_id} emits unknown requirement {rid}"

    (out / "req_catalog.json").write_text(_serialize(REQUIREMENTS))
    (out / "trigger_catalog.json").write_text(_serialize(TRIGGERS))
    print(f"Wrote {len(REQUIREMENTS)} requirements and {len(TRIGGERS)} triggers to {out}")


if __name__ == "__main__":
    main()
