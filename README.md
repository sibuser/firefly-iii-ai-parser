A Telegram Bot for parsing receipts and uploading purchased items to Firefly III.

This is just a prototype and a proof of concept. Use at your own risk.

## Requirements

Open AI API key.

A running instance of Firefly III with API access enabled.

A Telegram bot token.

Python 3.13

```bash
export OPENAI_API_KEY=
export FIREFLY_BASE_URL=http://app:8080
export FIREFLY_TOKEN=
export BOT_TOKEN=
```

# How to run

```bash
python main.py receipt.jpg --firefly

Licensed under the MIT License.
```
