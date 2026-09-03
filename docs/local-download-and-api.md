# Download and Use ProvSci Locally

ProvSci is a local application. A user downloads the repository, starts one
small Python server, and opens the product page in a browser. The project has
no runtime Python dependencies beyond Python 3.9 or newer.

## Download

Use **Code -> Download ZIP** on GitHub, unzip it, or clone the repository:

```bash
git clone https://github.com/Simon-byte-png/ProvSci.git
cd ProvSci
```

## Start the product

macOS/Linux:

```bash
./scripts/start_product_app.sh
```

Windows Command Prompt:

```bat
scripts\start_product_app.bat
```

Then open <http://127.0.0.1:4173/product_workspace.html>. The server only
listens on the local computer by default. Uploaded files and generated output
stay under the ignored `work/` directory.

## Connect a personal model API (optional)

The core extraction and verifier run locally and do not require a model key.
If a user wants an external model to write a short plain-language summary of
the finished results, click **API 设置** in the product page and enter:

- an OpenAI-compatible base URL, such as `https://api.openai.com/v1`,
  `https://api.deepseek.com/v1`, or a company's compatible gateway;
- the model name exposed by that service;
- the user's own API key;
- the checkbox to enable the summary for the current run.

Click **测试连接** before saving. The browser sends the key to the local
loopback server only. It is kept in the current browser session, never written
to the repository, and is not included in result JSONL files. The external
model receives a compact result summary only; it cannot change values,
evidence locations, quality status, or verifier decisions.

For unattended local runs, copy `.env.example` to `.env` and load it before
starting the server:

```bash
cp .env.example .env
set -a
. ./.env
set +a
./scripts/start_product_app.sh
```

The server reads `PROVSCI_API_ENABLED`,
`PROVSCI_API_KEY`, `PROVSCI_API_BASE_URL`, and `PROVSCI_API_MODEL` (the older
`XAI_*` names are accepted as a fallback). Do not commit `.env` or a real key.

## What is and is not sent

Without the optional setting, no external network call is made by the product
analysis endpoint. With it enabled, only the extracted result summary is sent
to the configured `/chat/completions` endpoint to produce a short explanation.
The original uploaded document remains local, and all structured values are
still produced and checked by the local ProvSci pipeline.
