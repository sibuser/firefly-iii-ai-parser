import os
import json
import requests
from typing import Dict, Optional
from dotenv import load_dotenv
from app.log import get_logger

load_dotenv()

FIREFLY_BASE_URL = os.getenv("FIREFLY_BASE_URL")
FIREFLY_TOKEN = os.getenv("FIREFLY_TOKEN")

log = get_logger(__name__)

def _headers(additional: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "Authorization": f"Bearer {FIREFLY_TOKEN}",
        "Accept": "application/vnd.api+json",
    }
    if additional:
        headers.update(additional)
    return headers

def send_to_firefly(payload: Dict) -> Dict:
    r = requests.post(
        f"{FIREFLY_BASE_URL}/api/v1/transactions",
        headers=_headers({"Content-Type": "application/json"}),
        json=payload,
        timeout=60,
    )
    if r.status_code not in (200, 201):
        log.error("firefly_tx_error", status=r.status_code, body=r.text)
        raise RuntimeError(f"Firefly transaction error: {r.status_code} {r.text}")
    data = r.json()
    log.info("firefly_tx_success", transactions=len(data.get("data", [])))
    return data

def get_accounts(account_type: str) -> Dict:
    r = requests.get(
        f"{FIREFLY_BASE_URL}/api/v1/accounts?type={account_type}",
        headers=_headers(),
        timeout=30,
    )
    if r.status_code != 200:
        log.error("firefly_accounts_error", status=r.status_code, body=r.text)
        raise RuntimeError(f"Firefly accounts error: {r.status_code} {r.text}")
    data = r.json()
    accounts = [acc["attributes"]["name"] for acc in data.get("data", [])]
    log.info("expense_accounts_fetched", count=len(accounts))
    return accounts

def get_categories() -> Dict:
    r = requests.get(
        f"{FIREFLY_BASE_URL}/api/v1/categories",
        headers=_headers(),
        timeout=30,
    )
    if r.status_code != 200:
        log.error("firefly_categories_error", status=r.status_code, body=r.text)
        raise RuntimeError(f"Firefly categories error: {r.status_code} {r.text}")
    data = r.json()
    categories = [cat["attributes"]["name"] for cat in data.get("data", [])]
    log.info("categories_fetched", count=len(categories))
    return categories

def create_attachment_for_journal(
    journal_id: int,
    title: str,
    filename: str,
    notes: str = ""
) -> tuple[str, str]:
    body = {
                "attachable_id": str(journal_id),
                "attachable_type": "TransactionJournal",
                "title": title or filename,
                "filename": filename,
                "notes": notes or "",
            }
    log.debug("creating_attachment", payload_pretty=json.dumps(body, indent=2, ensure_ascii=False))
    r = requests.post(
        f"{FIREFLY_BASE_URL}/api/v1/attachments",
        headers=_headers({"Content-Type": "application/json"}),
        json=body,
        timeout=60,
    )
    if r.status_code not in (200, 201):
        log.error("firefly_attach_create_error", status=r.status_code, body=r.text)
        raise RuntimeError(f"Attachment create error: {r.status_code} {r.text}")
    attachment = r.json().get("data", {})
    attrs = attachment.get("attributes", {})
    attachment_id = attachment.get("id")
    upload_url = attrs.get("upload_url")
    log.info("attachment_created", journal_id=journal_id, attachment_id=attachment_id)
    return attachment_id, upload_url

def upload_attachment_bytes(upload_url: str, file_path: str):
    headers = _headers({"Content-Type": "application/octet-stream"})
    with open(file_path, "rb") as fh:
        r = requests.post(upload_url, headers=headers, data=fh, timeout=120)
    if r.status_code not in (200, 201, 204):
        log.error("firefly_attach_upload_error", status=r.status_code, body=r.text)
        raise RuntimeError(f"Attachment upload error: {r.status_code} {r.text}")
    log.info("attachment_uploaded", upload_url=upload_url)

def create_and_attach(
    payload: Dict,
    receipt_path: str,
    notes: str = ""
) -> Dict:
    data = send_to_firefly(payload)

    journal_ids = []
    for item in data.get("data", []):
        splits = item.get("attributes", {}).get("transactions", [])
        for s in splits:
            jid = s.get("transaction_journal_id")
            if jid:
                journal_ids.append(int(jid))
    log.info("journals_found", count=len(journal_ids), journals=journal_ids)

    filename = os.path.basename(receipt_path)
    for jid in journal_ids:
        attachment_id, upload_url = create_attachment_for_journal(jid, filename, filename, notes)
        if upload_url:
            upload_attachment_bytes(upload_url, receipt_path)
            log.info("receipt_attached", journal_id=jid, attachment_id=attachment_id)
        else:
            log.error("no_upload_url", journal_id=jid, attachment_id=attachment_id)

    return data

def create_and_attach(payload: Dict, receipt_path: str, notes: str = "") -> Dict:
    response = send_to_firefly(payload)
    log.debug(
        "process_file_complete",
        payload_pretty=json.dumps(response, indent=2, ensure_ascii=False)
    )
    journal_ids = []
    for item in response["data"]["attributes"]["transactions"]:
        jid = item.get("transaction_journal_id")
        if jid is not None:
            journal_ids.append(int(jid))
    log.info("journals_found", count=len(journal_ids), journals=journal_ids)

    filename = os.path.basename(receipt_path)
    for jid in journal_ids:
        attachment_id, upload_url = create_attachment_for_journal(
            journal_id=jid,
            title=filename,
            filename=filename,
            notes=notes
        )
        if upload_url:
            upload_attachment_bytes(upload_url, receipt_path)
            log.info("receipt_attached", journal_id=jid, attachment_id=attachment_id)
        else:
            log.error("no_upload_url", journal_id=jid, attachment_id=attachment_id)

    return response