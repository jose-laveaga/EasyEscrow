from __future__ import annotations

import json

from django.conf import settings
from openai import OpenAI


PURCHASE_AGREEMENT_EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "is_valid_purchase_agreement": {"type": "boolean"},
        "confidence": {"type": "number"},
        "missing_required_fields": {"type": "array", "items": {"type": "string"}},
        "extraction_notes": {"type": "string"},
        "parties": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "seller_names": {"type": "array", "items": {"type": "string"}},
                "seller_address": {"type": ["string", "null"]},
                "buyer_names": {"type": "array", "items": {"type": "string"}},
                "buyer_address": {"type": ["string", "null"]},
                "depositor_name": {"type": ["string", "null"]},
            },
            "required": [
                "seller_names",
                "seller_address",
                "buyer_names",
                "buyer_address",
                "depositor_name",
            ],
        },
        "property": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "property_address": {"type": ["string", "null"]},
                "property_legal_description": {"type": ["string", "null"]},
                "property_city": {"type": ["string", "null"]},
                "property_state": {"type": ["string", "null"]},
                "property_country": {"type": ["string", "null"]},
                "parcel_number": {"type": ["string", "null"]},
            },
            "required": [
                "property_address",
                "property_legal_description",
                "property_city",
                "property_state",
                "property_country",
                "parcel_number",
            ],
        },
        "financial_terms": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "purchase_price": {"type": ["string", "number", "null"]},
                "earnest_money_amount": {"type": ["string", "number", "null"]},
                "currency": {"type": ["string", "null"]},
                "escrow_deposit_amount": {"type": ["string", "number", "null"]},
                "payment_scheme_summary": {"type": ["string", "null"]},
                "payment_milestones": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "label": {"type": ["string", "null"]},
                            "amount": {"type": ["string", "number", "null"]},
                            "currency": {"type": ["string", "null"]},
                            "due_date": {"type": ["string", "null"]},
                            "due_event": {"type": ["string", "null"]},
                            "payer": {"type": ["string", "null"]},
                            "payee": {"type": ["string", "null"]},
                            "notes": {"type": ["string", "null"]},
                        },
                        "required": [
                            "label",
                            "amount",
                            "currency",
                            "due_date",
                            "due_event",
                            "payer",
                            "payee",
                            "notes",
                        ],
                    },
                },
            },
            "required": [
                "purchase_price",
                "earnest_money_amount",
                "currency",
                "escrow_deposit_amount",
                "payment_scheme_summary",
                "payment_milestones",
            ],
        },
        "dates": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "agreement_date": {"type": ["string", "null"]},
                "executed_date": {"type": ["string", "null"]},
                "closing_date": {"type": ["string", "null"]},
                "inspection_deadline": {"type": ["string", "null"]},
                "financing_deadline": {"type": ["string", "null"]},
                "deposit_due_date": {"type": ["string", "null"]},
            },
            "required": [
                "agreement_date",
                "executed_date",
                "closing_date",
                "inspection_deadline",
                "financing_deadline",
                "deposit_due_date",
            ],
        },
        "conditions": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "contingencies": {"type": "array", "items": {"type": "string"}},
                "special_conditions": {"type": "array", "items": {"type": "string"}},
                "closing_conditions": {"type": "array", "items": {"type": "string"}},
                "disbursement_conditions": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "contingencies",
                "special_conditions",
                "closing_conditions",
                "disbursement_conditions",
            ],
        },
        "disbursement_instructions": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "payees": {"type": "array", "items": {"type": "string"}},
                "amounts": {"type": "array", "items": {"type": ["string", "number"]}},
                "purposes": {"type": "array", "items": {"type": "string"}},
                "wire_information": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "payee": {"type": ["string", "null"]},
                            "bank": {"type": ["string", "null"]},
                            "account_number": {"type": ["string", "null"]},
                            "clabe": {"type": ["string", "null"]},
                            "routing_number": {"type": ["string", "null"]},
                            "swift": {"type": ["string", "null"]},
                            "notes": {"type": ["string", "null"]},
                        },
                        "required": [
                            "payee",
                            "bank",
                            "account_number",
                            "clabe",
                            "routing_number",
                            "swift",
                            "notes",
                        ],
                    },
                },
            },
            "required": ["payees", "amounts", "purposes", "wire_information"],
        },
        "signatures": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "has_signature_section": {"type": "boolean"},
                "seller_signature_required": {"type": "boolean"},
                "buyer_signature_required": {"type": "boolean"},
                "escrow_agent_signature_required": {"type": "boolean"},
            },
            "required": [
                "has_signature_section",
                "seller_signature_required",
                "buyer_signature_required",
                "escrow_agent_signature_required",
            ],
        },
        "source_quality": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "language": {"type": ["string", "null"]},
                "is_scanned_or_image_based": {"type": "boolean"},
                "text_quality": {"type": ["string", "null"]},
                "pages_reviewed": {"type": ["integer", "null"]},
            },
            "required": [
                "language",
                "is_scanned_or_image_based",
                "text_quality",
                "pages_reviewed",
            ],
        },
    },
    "required": [
        "is_valid_purchase_agreement",
        "confidence",
        "missing_required_fields",
        "extraction_notes",
        "parties",
        "property",
        "financial_terms",
        "dates",
        "conditions",
        "disbursement_instructions",
        "signatures",
        "source_quality",
    ],
}


def _normalize_json_schema(schema):
    if isinstance(schema, dict):
        normalized = {}
        for key, value in schema.items():
            if key == "type" and isinstance(value, list):
                normalized["anyOf"] = [{"type": type_name} for type_name in value]
                continue
            normalized[key] = _normalize_json_schema(value)
        return normalized
    if isinstance(schema, list):
        return [_normalize_json_schema(item) for item in schema]
    return schema


PURCHASE_AGREEMENT_EXTRACTION_SCHEMA = _normalize_json_schema(PURCHASE_AGREEMENT_EXTRACTION_SCHEMA)


PURCHASE_AGREEMENT_REVIEW_PROMPT = """
You are reviewing a real estate purchase agreement uploaded by a broker.

Your task:
1. Verify whether the document is a valid real estate purchase agreement.
2. Extract the transaction fields needed to generate an escrow agreement.
3. Return only data supported by the document.

Use null when a field is not found.
Use [] for missing list values.
Do not invent values.
If a value is inferred, explain the inference in extraction_notes.

Required fields for validity:
- parties.seller_names
- parties.buyer_names
- property.property_address or property.property_legal_description
- financial_terms.purchase_price
- financial_terms.earnest_money_amount or financial_terms.escrow_deposit_amount
- financial_terms.currency
- dates.closing_date
- signatures.has_signature_section

If any required field is missing, add its JSON path to missing_required_fields.
Example: "financial_terms.purchase_price".
"""


def get_openai_client() -> OpenAI:
    api_key = getattr(settings, "OPENAI_PURCHASE_AGREEMENT_API_KEY", None) or getattr(
        settings,
        "OPENAI_API_KEY",
        None,
    )
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY or OPENAI_PURCHASE_AGREEMENT_API_KEY must be configured.")
    return OpenAI(api_key=api_key)


def upload_file_to_openai(file_path: str, *, client=None) -> str:
    client = client or get_openai_client()
    with open(file_path, "rb") as file:
        uploaded = client.files.create(
            file=file,
            purpose="user_data",
        )
    return uploaded.id


def extract_purchase_agreement_fields(openai_file_id: str, *, client=None) -> dict:
    client = client or get_openai_client()
    response = client.responses.create(
        model=getattr(settings, "OPENAI_PURCHASE_AGREEMENT_MODEL", "gpt-4o-mini"),
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": openai_file_id,
                    },
                    {
                        "type": "input_text",
                        "text": PURCHASE_AGREEMENT_REVIEW_PROMPT,
                    },
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "purchase_agreement_extraction",
                "strict": True,
                "schema": PURCHASE_AGREEMENT_EXTRACTION_SCHEMA,
            }
        },
    )

    parsed_output = getattr(response, "output_parsed", None)
    if parsed_output is not None:
        return parsed_output
    return json.loads(response.output_text)
