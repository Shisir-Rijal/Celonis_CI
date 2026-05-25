import finnhub


def _get_symbol(client: finnhub.Client, domain: str) -> str | None:
    company_name = domain.replace(".com", "").replace(".io", "")
    results = client.symbol_search(company_name)
    for r in results.get("result", []):
        if r.get("type") == "Common Stock":
            return r["symbol"]
    return None