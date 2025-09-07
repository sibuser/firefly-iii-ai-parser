import os
import json
import base64
from pathlib import Path
from openai import OpenAI
from app.log import get_logger
from dotenv import load_dotenv
from app.firefly import get_categories, get_accounts

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

log = get_logger(__name__)

PROMPT = """
You are given an image of a retail receipt. Read the receipt text and return only the following JSON object:
{
  "fire_webhooks": true,
  "group_title": "string",
  "transactions": [
    {
      "type": "withdrawal",
      "amount": "0.00",
      "date": "YYYY-MM-DD",
      "description": "string",
      "currency_id": "10",
      "category_name": "string",
      "currency_code": "SEK",
      "source_name": "Extra",
      "destination_name": "string",
      "tags": "Firefly Assistant",
      "notes": ""
    }
  ]
}
Extraction rules
	1.	date
    •	Find the transaction date near the totals or cashier info.
    •	Accept formats like YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY, YY MM DD, etc.
    •	Normalize to ISO YYYY-MM-DD. For 2-digit years, assume 2000-2099 (20 08 25 → 2020-08-25).
	2.	items → transactions
    •	Create one transaction per purchasable line-item (not totals, VAT/Moms, payment lines, or headers).
    •	Description: the item name on the line.
    •	Final price per line:
    •	If the line shows qty x unit_price, multiply and use the line total.
    •	If both unit and line totals appear, choose the line total.
    •	If a discount applies to that item line, subtract it to get the final line price.
    •.  If Rabbat (discount) appears on a separate line, apply it to previous item.
  	•	Ignore non-item lines such as TOTAL, Moms, Brutto, payment method, change, loyalty IDs, and return policies.
	3.	amount normalization
    •   Use Total in SEK not subtotal
    •	Keep two decimals as a string (Firefly format), decimal dot; convert comma decimals (e.g., 543,20 → "543.20").
    •	Remove thousands separators and currency symbols/text.
	4.	currency
    •	If the receipt shows SEK/kr, set "currency_code": "SEK" and "currency_id": "10".
    •	If currency is unknown, still set "currency_code": "SEK" and "currency_id": "10" (default for Swedish receipts).
	5.	destination_name (merchant)
    •.  First check if a store/merchant name exists in the given list below. If it does, use that exact name.
    •   If not, use the store/merchant name exactly as printed (e.g., BAUHAUS or Bauhaus Askim).
	6.	group_title
    •	Use a concise category inferred from the merchant when obvious (e.g., Groceries, Hardware & DIY, Pharmacy).
    •	If uncertain, use the merchant name.
	7.	tags
  	•	Always set to "Firefly Assistant".
	8.	Output constraints
    •	Return only valid JSON exactly matching the structure above.
    •	Do not include reasoning, comments, or extra fields.
    9.    source_name
    •	DO NOT MODIFY source_name
    10.  Notes
    •   Keep notes field empty unless there is specific additional info to add.
    11. category_name
    •   Choose the most specific category possible from the given list below.
    •   If unsure, leave empty.


Worked example (for internal reasoning, do not include in output)
	•	Merchant: BAUHAUS (destination_name)
	•	Date found like 20 08 25 08:43 → 2020-08-25
	•	Items:
	•	BORR SDS-P 10X310MM 89,95 → amount "89.95"
	•	KABEL UTP CAT 5E 453,25 → amount "453.25"
	•	Payment line: Bankkort online (no digits) → source_name "Extra"
	•	group_title: Hardware & DIY


Do not include any markdown formatting.
NEVER ADD ```json ``` into the response
RETURN ALL ITEMS FROM THE RECEIPT
DO NOT ADD ITEMS WITH ZERO AMOUNT
"""

def image_to_data_url(path: Path) -> str:
    try:
        with open(path, "rb") as f:
            img_bytes = f.read()
        mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        log.info("image_encoded", path=str(path), mime=mime, size=len(img_bytes))
        return f"data:{mime};base64,{b64}"
    except Exception as e:
        log.error("image_encoding_failed", path=str(path), error=str(e), exc_info=True)
        raise


def extract_firefly_payload(image_path: Path) -> dict:
    try:
        log.info("starting_extraction", path=str(image_path))
        image_data_url = image_to_data_url(image_path)
        categories = get_categories()
        destination_accounts = get_accounts(account_type="expense")

        PROMPT_MOD = PROMPT + f"""
        Existing expense categories: {categories}
        Existing store/merchant names: {destination_accounts}
        """
        response = client.chat.completions.create(
            model="gpt-5-mini",
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT_MOD},
                        {"type": "image_url", "image_url": {"url": image_data_url, "detail": "auto"}}
                    ]
                }
            ]
        )

        result = json.loads(response.choices[0].message.content)
        log.info("extraction_successful", transactions=len(result.get("transactions", [])))
        return result

    except Exception as e:
        log.error("openai_extraction_failed", path=str(image_path), error=str(e), exc_info=True)
        raise