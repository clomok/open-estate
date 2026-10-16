"""The default death-of-trustor playbook: what the successor trustee does, and
roughly when, counted in days from the date of death.

Drawn from general U.S. estate- and trust-administration practice (county
"when a loved one dies" guides, IRS fiduciary instructions, and successor-
trustee checklists published by estate attorneys). It is a starting point
for a family to edit, not a statement of anyone's legal duties: deadlines
and notice rules differ by state, and a trust can say otherwise.

This module is data. The migration that introduces playbooks and the v3 ->
v4 backup converter both insert it, so an upgraded database, a restored old
backup and a fresh install all start with the same list. Editing it changes
what new installs get; it never touches a playbook already in a database.
"""

DISCLAIMER = (
    "This software is for organizational purposes only. It is not a substitute "
    "for legal advice, a licensed attorney, or a financial advisor. Always consult "
    "with professionals regarding estate planning and trust administration."
)

NAME = "When a trustor dies"
TRIGGER = "death_of_trustor"
DESCRIPTION = (
    "What the successor trustee does in the first 72 hours, 30 days, 90 days and "
    "first year, counted from the date of death. General practice in the United "
    "States, written for a revocable living trust; deadlines and notice rules vary "
    "by state, and the trust document itself can change what applies. Have the "
    "estate attorney read it through once, and edit any step to fit this family."
)

# (offset_days, kind, who_role, title, instructions, document to locate)
STEPS = [
    # --- First 72 hours ---------------------------------------------------
    (0, "task", "SuccessorTrustee", "Get a legal pronouncement of death",
     "Nothing official can start until a doctor, hospice nurse or medical examiner "
     "pronounces the death. Expected death under hospice: call the hospice nurse. "
     "Unexpected death: call 911. Do not move the body until you are told you may.",
     "Advance directive / POLST"),
    (0, "task", "SuccessorTrustee", "Check for organ or body donation wishes",
     "This one cannot wait: donation has to be arranged within hours. Look at the "
     "driver's licence and any donor card or body-donation agreement, then call the "
     "hospital or the donation programme.",
     "Donor card or body-donation agreement"),
    (0, "task", "SuccessorTrustee", "Make sure dependents and pets are cared for",
     "Anyone who relied on them day to day: children, a spouse who needs care, pets. "
     "Arrange cover for the next few days before anything else.", None),
    (1, "task", "SuccessorTrustee", "Call the funeral home",
     "Follow any written wishes for burial or cremation. You do not have to use the "
     "funeral home a hospital suggests. Ask them to order the death certificates and "
     "whether they report the death to Social Security.",
     "Pre-need funeral contract / final wishes"),
    (1, "task", "SuccessorTrustee", "Tell close family and friends",
     "Use the contacts in this binder. Ask one person to help spread the word so you "
     "are not making every call yourself.", None),
    (2, "task", "SuccessorTrustee", "Secure the home, vehicles and valuables",
     "Lock up, collect the mail, keep the heat and power on, and change the locks if "
     "many people have keys. An obituary tells strangers the house may be empty. Do "
     "not give anything away yet, even items promised to someone.",
     "Keys and access instructions"),
    (2, "task", "SuccessorTrustee", "Find the original trust, will and amendments",
     "You act from the trust document, so find the signed original and every "
     "amendment. If there is an original will, many states require it to be lodged "
     "with the court within a set time: ask the attorney.",
     "Trust instrument, amendments, pour-over will"),
    (3, "task", "SuccessorTrustee", "Order certified death certificates",
     "Order more than you think, often ten or more. Banks, insurers, the DMV and "
     "every title change ask for a certified copy, and some keep it.", None),

    # --- First 30 days ----------------------------------------------------
    (7, "task", "Attorney", "Meet the estate attorney",
     "Confirm you are the successor trustee (and whether there is a co-trustee), "
     "which state's rules apply, and which deadlines below matter for this trust.",
     "Trust instrument"),
    (7, "task", "SuccessorTrustee", "Notify Social Security",
     "Call 1-800-772-1213 if the funeral home has not reported the death. A payment "
     "for the month of death may have to be returned. Ask about survivor benefits "
     "for a spouse or children.", None),
    (10, "task", "SuccessorTrustee", "Notify the employer, pension and retirement plans",
     "Ask about final pay, a pension survivor option, group life insurance and "
     "retirement accounts.", "Pension and retirement statements"),
    (10, "task", "Insurance", "Claim life insurance",
     "Each insurer needs a claim form and a certified death certificate. The named "
     "beneficiary claims it; it usually passes outside the trust.",
     "Life insurance policies"),
    (14, "task", "Accountant", "Get a tax ID (EIN) for the trust",
     "A revocable trust becomes irrevocable at death and usually needs its own "
     "employer identification number (IRS Form SS-4, free on irs.gov). The bank "
     "will ask for it.", None),
    (14, "task", "Accountant", "Tell the IRS you are the fiduciary (Form 56)",
     "Form 56 notifies the IRS that you act for the trust or estate, so its letters "
     "come to you.", None),
    (21, "task", "SuccessorTrustee", "Open a trust bank account",
     "Pay trust bills and receive trust money only through this account. Never mix "
     "trust money with your own.", "Certification of trust"),
    (21, "task", "SuccessorTrustee", "Notify banks, brokerages and custodians",
     "Accounts titled to the trust are retitled to you as successor trustee. "
     "Accounts with a payable-on-death or transfer-on-death beneficiary go straight "
     "to that person.", "Account statements"),
    (21, "task", "SuccessorTrustee", "Freeze credit and tell the credit bureaus",
     "Notify Equifax, Experian and TransUnion to cut the risk of identity theft.",
     None),
    (30, "task", "SuccessorTrustee", "Forward the mail and cancel services",
     "Set up mail forwarding; cancel phone, subscriptions and memberships; keep "
     "anything the house needs.", None),
    (30, "task", "SuccessorTrustee", "Keep the essential bills paid",
     "Mortgage, property tax, utilities and insurance, from the trust account. Do "
     "not let home or auto insurance lapse, and tell the insurer if the home is "
     "empty: many policies change when a house is vacant.", None),

    # --- By 90 days -------------------------------------------------------
    (45, "task", "Accountant", "Value every trust asset as of the date of death",
     "Date-of-death statements for accounts, appraisals for real estate and "
     "valuables. These values usually become the new tax basis, so keep the "
     "paperwork. Add each as a valuation on the holding in this binder.",
     "Statements and appraisals"),
    (45, "task", "SuccessorTrustee", "List the debts and final bills",
     "Collect what is owed: medical bills, cards, loans, final utilities. Debts and "
     "expenses come before anything goes to beneficiaries.", None),
    (60, "deadline", "Attorney", "Send the required notice to beneficiaries and heirs",
     "Many states require a written notice within a set time of the death "
     "(California: 60 days, which starts a 120-day period to contest the trust). "
     "The attorney knows the rule here.", "Trust instrument"),
    (60, "task", "Attorney", "Decide whether anything needs probate",
     "Anything titled in the person's own name with no beneficiary and not in the "
     "trust may need probate or a small-estate affidavit.", None),
    (75, "task", "Financial Advisor", "Help beneficiaries claim beneficiary-form accounts",
     "IRAs, 401(k)s, annuities and TOD accounts pass by their beneficiary form, not "
     "the trust. Inherited retirement accounts carry their own withdrawal deadlines.",
     "Beneficiary designations"),
    (90, "review", "SuccessorTrustee", "Review progress with the attorney and accountant",
     "What is done, what is left, and the tax plan for the year.", None),

    # --- Year one ---------------------------------------------------------
    (120, "task", "Accountant", "Hold back enough for taxes and expenses",
     "Before any distribution, set aside what final taxes and administration will "
     "cost.", None),
    (180, "review", "Accountant", "Decide on the alternate valuation date",
     "Only matters if an estate tax return is filed: assets may be valued six months "
     "after death instead of on the date of death.", None),
    (180, "deadline", "Accountant", "File the final personal income tax return",
     "The decedent's final Form 1040 is due April 15 of the year after the year of "
     "death. Move this event's date to match.", "Last year's tax return"),
    (270, "deadline", "Accountant", "Estate tax return (Form 706), if required",
     "Due nine months after death (a six-month extension is available on Form 4768). "
     "Also the way to pass the unused exemption to a surviving spouse (portability), "
     "even when no tax is owed.", None),
    (300, "task", "SuccessorTrustee", "Prepare an accounting for the beneficiaries",
     "What came in, what was paid out, what is left, and what each beneficiary will "
     "receive.", None),
    (330, "deadline", "Accountant", "Trust income tax return (Form 1041)",
     "Income the trust earns after the death is reported on Form 1041, due the 15th "
     "day of the fourth month after the trust's tax year ends. Ask the accountant "
     "about the section 645 election and a fiscal year.", None),
    (330, "task", "SuccessorTrustee", "Distribute the assets as the trust directs",
     "Get a signed receipt from each beneficiary. A release of the trustee is "
     "something a beneficiary may agree to, never something to require.",
     "Trust schedule of distributions"),
    (365, "task", "SuccessorTrustee", "Close the trust and keep the records",
     "File the final trust return, close the trust account, and keep every record "
     "for at least seven years.", None),
]


def step_rows(playbook_id, audit=None):
    """The steps as plain dicts (column -> value) for a migration or a backup."""
    audit = audit or {}
    return [
        {"playbook_id": playbook_id, "position": i, "offset_days": offset, "kind": kind,
         "who_role": who, "title": title, "instructions": text, "document_type": doc,
         **audit}
        for i, (offset, kind, who, title, text, doc) in enumerate(STEPS)
    ]


def install(session):
    """Add a fresh copy of the default playbook through the ORM. Returns it."""
    from src.models import Playbook, PlaybookStep
    pb = Playbook(name=NAME, description=DESCRIPTION, trigger=TRIGGER)
    session.add(pb)
    session.flush()
    for row in step_rows(pb.id):
        session.add(PlaybookStep(**row))
    session.flush()
    return pb
