"""
Synthetic demo dataset generator (DESIGN.md §8).

Idempotent: wipes all non-admin demo data then rebuilds from scratch.

Usage (inside the backend container):
    python scripts/seed_demo.py           # full seed
    python scripts/seed_demo.py --sample  # render ONE sample PDF to /tmp and exit
"""

import argparse
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import anthropic
from jinja2 import Environment, FileSystemLoader
from sqlalchemy import update as sa_update
from sqlalchemy.orm import Session
from weasyprint import HTML

from app import storage
from app.auth.service import hash_password
from app.checklist import match_and_update_checklist, seed_checklist
from app.database import SessionLocal
from app.models import (
    AuditLog,
    Client,
    ClientType,
    ContextEntry,
    ContextProbe,
    ContextSource,
    Document,
    DocumentStatus,
    Firm,
    Reminder,
    RequiredDocument,
    RequiredDocStatus,
    SourceChannel,
    User,
    UserRole,
)

SCRIPT_DIR = Path(__file__).parent
TEMPLATES_DIR = SCRIPT_DIR / "templates"
FIRM_NAME = "Acme CPA Partners"
ADMIN_EMAIL = "admin@acmecpa.com"
TAX_YEAR = "2023"

jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)), autoescape=False)
claude_client = anthropic.Anthropic()

DOC_TYPE_TO_TEMPLATE = {
    "W-2": "w2.html",
    "1099-INT": "1099_int.html",
    "1099-NEC": "1099_nec.html",
    "1098": "1098.html",
    "prior_year_return": "prior_year_return.html",
    "bank_statement": "bank_statement.html",
    "engagement_letter": "engagement_letter.html",
}


# ── PDF rendering ──────────────────────────────────────────────────────────────

SKIP_PDF = os.environ.get("SKIP_PDF", "0") == "1"

# Minimal valid 1-page PDF used as a placeholder when SKIP_PDF=1
_BLANK_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
    b"0000000058 00000 n\n0000000115 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n190\n%%EOF\n"
)


def render_pdf(template_name: str, fields: dict) -> bytes:
    if SKIP_PDF:
        return _BLANK_PDF
    tmpl = jinja_env.get_template(template_name)
    html_str = tmpl.render(**fields)
    return HTML(string=html_str).write_pdf()


# ── Claude profile generation ──────────────────────────────────────────────────

_PROFILE_PROMPT = """
Generate a realistic demo dataset for a CPA firm called "Acme CPA Partners" based in San Francisco, CA.
Return ONLY a single valid JSON object — no prose, no markdown fences, no extra keys.

RULES:
- SSNs: format "000-XX-XXXX" where X is any digit (e.g., "000-42-7831")
- EINs: format "XX-XXXXXXX" where X is any digit (e.g., "87-3421056")
- Routing numbers: 9-digit numeric strings (e.g., "021000021")
- Dollar amounts: formatted with commas and two decimals (e.g., "72,450.00")
- Use entirely fictional names, companies, and addresses
- Tax year: 2023
- All amounts must be internally consistent (bank statement: ending = beginning + deposits - withdrawals)

TARGET STRUCTURE:

{
  "cpas": [
    { "name": "Full Name", "email": "firstname.lastname@acmecpa.com" }
  ],
  "clients": [
    {
      "name": "Client Full Name",
      "type": "individual",
      "cpa_index": 0,
      "docs_to_receive": [
        {
          "doc_type": "W-2",
          "filename": "LastName_W-2_2023.pdf",
          "fields": { ... }
        }
      ]
    }
  ]
}

CREATE EXACTLY:
- 3 CPAs
- 5 clients: 3 individuals and 2 businesses
- Spread clients across the 3 CPAs (at least one each)

INDIVIDUAL clients receive these docs (docs_to_receive):
  W-2, 1099-INT, engagement_letter
  (leave prior_year_return and 1098/1099-DIV PENDING — not in docs_to_receive)

BUSINESS clients receive these docs (docs_to_receive):
  1099-NEC, bank_statement, engagement_letter
  (leave prior_year_return, profit_and_loss, balance_sheet PENDING)

FIELD SCHEMAS per doc type (supply ALL fields listed):

W-2:
  tax_year, employee_ssn, employer_ein, employer_name, employer_address,
  control_number, employee_name, employee_address, wages, federal_tax_withheld,
  social_security_wages, social_security_tax, medicare_wages, medicare_tax,
  box12 (null or "D 4500.00" if 401k), dependent_care (null),
  state, state_id, state_wages, state_tax

1099-INT:
  tax_year, payer_name, payer_address, payer_tin, recipient_tin, recipient_name,
  recipient_address, recipient_city_state, account_number, interest_income,
  early_withdrawal_penalty, us_bond_interest, federal_tax_withheld,
  state, state_id, state_tax

1099-NEC:
  tax_year, payer_name, payer_address, payer_tin, recipient_tin, recipient_name,
  recipient_address, recipient_city_state, account_number, nonemployee_compensation,
  federal_tax_withheld, state, state_id, state_income, state_tax

bank_statement:
  bank_name, bank_address, bank_phone, bank_website, statement_month,
  period_start, period_end, account_holder, holder_address, last_four,
  account_type, routing_number, beginning_balance, total_credits, total_debits,
  ending_balance,
  transactions: array of 10-12 objects, each:
    { date, description, withdrawal (or null), deposit (or null), balance }

engagement_letter (individual):
  tax_year, firm_name, firm_address, firm_phone, firm_email,
  letter_date, client_name, client_address, salutation_name,
  forms_to_prepare (e.g. ["Form 1040", "CA Form 540"]),
  estimated_fee, cpa_name,
  preparer_name, preparer_ein

engagement_letter (business):
  same fields but forms_to_prepare e.g. ["Form 1065", "CA Form 565"] or ["Form 1120-S", "CA Form 100-S"]

Use realistic occupations, employers, banks, and payment amounts.
Vary the states (CA, TX, NY, WA, CO, MA — no more than 2 of the same).
"""


def generate_profiles() -> dict:
    print("Calling Claude to generate client profiles...")
    response = claude_client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": _PROFILE_PROMPT}],
    )
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


# ── DB helpers ─────────────────────────────────────────────────────────────────

def wipe_demo_data(db: Session, firm_id: uuid.UUID) -> None:
    """Delete all demo CPAs/clients/documents for the firm. Leaves admin + firm intact."""
    demo_users = (
        db.query(User)
        .filter(User.firm_id == firm_id, User.role != UserRole.admin)
        .all()
    )
    demo_user_ids = [u.id for u in demo_users]

    clients = db.query(Client).filter_by(firm_id=firm_id).all()
    client_ids = [c.id for c in clients]

    if client_ids:
        docs = db.query(Document).filter(Document.client_id.in_(client_ids)).all()
        for doc in docs:
            try:
                storage.delete_file(doc.storage_key)
            except Exception:
                pass

        db.query(AuditLog).filter(
            AuditLog.user_id.in_(demo_user_ids)
        ).delete(synchronize_session=False)
        db.query(ContextEntry).filter(
            ContextEntry.client_id.in_(client_ids)
        ).delete(synchronize_session=False)
        db.query(ContextProbe).filter(
            ContextProbe.client_id.in_(client_ids)
        ).delete(synchronize_session=False)
        db.query(Reminder).filter(
            Reminder.client_id.in_(client_ids)
        ).delete(synchronize_session=False)
        db.query(RequiredDocument).filter(
            RequiredDocument.client_id.in_(client_ids)
        ).delete(synchronize_session=False)
        db.query(Document).filter(
            Document.client_id.in_(client_ids)
        ).delete(synchronize_session=False)

        db.execute(
            sa_update(User)
            .where(User.client_id.in_(client_ids))
            .values(client_id=None)
        )
        db.flush()
        db.query(Client).filter(
            Client.id.in_(client_ids)
        ).delete(synchronize_session=False)

    if demo_user_ids:
        db.query(User).filter(
            User.id.in_(demo_user_ids)
        ).delete(synchronize_session=False)

    db.commit()
    print("  Wiped existing demo data.")


def _normalize_filename(client_name: str, doc_type: str, tax_year: int) -> str:
    last = re.sub(r"[^\w]", "", client_name.split()[-1]) if client_name else "Client"
    dt = re.sub(r"[^\w-]", "", doc_type or "unknown")
    return f"{last}_{dt}_{tax_year}.pdf"


def _extract_issuer(doc_type: str, fields: dict) -> str:
    return (
        fields.get("employer_name")
        or fields.get("payer_name")
        or fields.get("lender_name")
        or fields.get("bank_name")
        or fields.get("firm_name")
        or "Unknown"
    )


def _extract_key_amounts(doc_type: str, fields: dict) -> dict:
    mapping: dict[str, dict] = {
        "W-2":              {"wages": fields.get("wages"), "federal_withheld": fields.get("federal_tax_withheld")},
        "1099-INT":         {"interest_income": fields.get("interest_income")},
        "1099-NEC":         {"nonemployee_compensation": fields.get("nonemployee_compensation")},
        "1098":             {"mortgage_interest": fields.get("mortgage_interest")},
        "bank_statement":   {"ending_balance": fields.get("ending_balance")},
        "prior_year_return":{"agi": fields.get("agi")},
    }
    return {k: v for k, v in mapping.get(doc_type, {}).items() if v}


# ── Main seeder ────────────────────────────────────────────────────────────────

def seed_demo(db: Session) -> None:
    admin = db.query(User).filter_by(email=ADMIN_EMAIL).first()
    if not admin:
        print(f"ERROR: Admin user {ADMIN_EMAIL} not found. Run scripts/seed.py first.")
        sys.exit(1)

    firm = db.query(Firm).filter_by(id=admin.firm_id).first()

    wipe_demo_data(db, firm.id)

    profiles = generate_profiles()
    print(f"  Generated {len(profiles['cpas'])} CPAs, {len(profiles['clients'])} clients.")

    # Create CPA users
    cpa_users: list[User] = []
    for cpa_data in profiles["cpas"]:
        cpa = User(
            firm_id=firm.id,
            email=cpa_data["email"],
            password_hash=hash_password("Demo1234!"),
            role=UserRole.cpa,
            name=cpa_data["name"],
            is_active=True,
        )
        db.add(cpa)
        cpa_users.append(cpa)
    db.flush()

    for client_data in profiles["clients"]:
        cpa = cpa_users[client_data["cpa_index"]]
        client_type = (
            ClientType.individual
            if client_data["type"] == "individual"
            else ClientType.business
        )

        client = Client(
            firm_id=firm.id,
            name=client_data["name"],
            type=client_type,
            assigned_cpa_id=cpa.id,
        )
        db.add(client)
        db.flush()

        seed_checklist(client, db)
        db.flush()

        for doc_data in client_data.get("docs_to_receive", []):
            doc_type = doc_data["doc_type"]
            template_name = DOC_TYPE_TO_TEMPLATE.get(doc_type)
            if not template_name:
                print(f"  WARNING: no template for {doc_type}, skipping")
                continue

            try:
                pdf_bytes = render_pdf(template_name, doc_data["fields"])
            except Exception as exc:
                print(f"  WARNING: PDF render failed for {doc_type}: {exc}")
                continue

            storage_key = str(uuid.uuid4())
            storage.save_file(storage_key, pdf_bytes)

            raw_year = doc_data["fields"].get("tax_year", TAX_YEAR)
            try:
                tax_year_int = int(str(raw_year))
            except (TypeError, ValueError):
                tax_year_int = int(TAX_YEAR)

            normalized = _normalize_filename(client_data["name"], doc_type, tax_year_int)

            doc = Document(
                client_id=client.id,
                uploaded_by=admin.id,
                original_filename=doc_data["filename"],
                normalized_filename=normalized,
                storage_key=storage_key,
                mime_type="application/pdf",
                status=DocumentStatus.classified,
                source_channel=SourceChannel.portal,
                doc_type=doc_type,
                tax_year=tax_year_int,
                extracted_summary=f"{doc_type} for {client_data['name']} — tax year {tax_year_int}",
                extracted_fields={
                    "issuer": _extract_issuer(doc_type, doc_data["fields"]),
                    "recipient": client_data["name"],
                    "key_amounts": _extract_key_amounts(doc_type, doc_data["fields"]),
                },
                processed_at=datetime.now(timezone.utc),
            )
            db.add(doc)
            db.flush()

            match_and_update_checklist(doc, db)

            db.add(ContextEntry(
                client_id=client.id,
                content=(
                    f"Received and classified: {doc_type}. "
                    f"Issuer: {_extract_issuer(doc_type, doc_data['fields'])}. "
                    f"Recipient: {client_data['name']}."
                ),
                source=ContextSource.document,
                created_by=admin.id,
            ))

            print(f"  + {client_data['name']}: {doc_type} → {doc_data['filename']}")

    db.commit()
    print("\nDemo dataset seeded.")
    _print_summary(db, firm.id)


def _print_summary(db: Session, firm_id: uuid.UUID) -> None:
    clients = db.query(Client).filter_by(firm_id=firm_id).all()
    print("\n── Demo State ─────────────────────────────────────────────────────")
    for c in clients:
        received = db.query(RequiredDocument).filter_by(
            client_id=c.id, status=RequiredDocStatus.received
        ).count()
        pending = db.query(RequiredDocument).filter_by(
            client_id=c.id, status=RequiredDocStatus.pending
        ).count()
        cpa = db.query(User).filter_by(id=c.assigned_cpa_id).first()
        cpa_name = cpa.name if cpa else "—"
        print(
            f"  {c.name:<30s}  [{c.type.value:<10s}]"
            f"  CPA: {cpa_name:<22s}"
            f"  {received} received / {pending} pending"
        )
    print("───────────────────────────────────────────────────────────────────")


# ── Sample mode ────────────────────────────────────────────────────────────────

_SAMPLE_W2_FIELDS = {
    "tax_year": "2023",
    "employee_ssn": "000-42-7831",
    "employer_ein": "87-3421056",
    "employer_name": "Meridian Technology Group",
    "employer_address": "1200 Innovation Blvd, Austin, TX 78701",
    "control_number": "TX-2023-00142",
    "employee_name": "Jennifer M. Patel",
    "employee_address": "4821 Cedar Ridge Dr, Austin, TX 78745",
    "wages": "112,800.00",
    "federal_tax_withheld": "19,460.00",
    "social_security_wages": "112,800.00",
    "social_security_tax": "6,993.60",
    "medicare_wages": "112,800.00",
    "medicare_tax": "1,635.60",
    "box12": "D 9,600.00",
    "dependent_care": None,
    "state": "TX",
    "state_id": "TX-1200-MTG",
    "state_wages": "112,800.00",
    "state_tax": "0.00",
}


def run_sample() -> None:
    out_path = Path("/tmp/sample_w2_2023.pdf")
    print(f"Rendering sample W-2 to {out_path} ...")
    pdf_bytes = render_pdf("w2.html", _SAMPLE_W2_FIELDS)
    out_path.write_bytes(pdf_bytes)
    print(f"Done — {len(pdf_bytes):,} bytes written to {out_path}")
    print("Copy to host: docker compose cp backend:/tmp/sample_w2_2023.pdf ./sample_w2_2023.pdf")


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Audit Bee demo dataset")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Render one sample W-2 PDF to /tmp and exit (no DB changes)",
    )
    args = parser.parse_args()

    if args.sample:
        run_sample()
        sys.exit(0)

    db = SessionLocal()
    try:
        seed_demo(db)
    finally:
        db.close()
