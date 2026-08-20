"""tests/test_news_collector.py"""
from collector.news_collector import classify_news_impact


def test_classify_news_high_impact_nfp():
    impact, currencies = classify_news_impact("US Non-Farm Payrolls (NFP) surge past expectations", "Labor market remains tight.")
    assert impact == "high"
    assert "USD" in currencies


def test_classify_news_high_impact_ecb():
    impact, currencies = classify_news_impact("ECB interest rate decision announced by Lagarde", "Rates held steady.")
    assert impact == "high"
    assert "EUR" in currencies


def test_classify_news_crypto_sec():
    impact, currencies = classify_news_impact("SEC lawsuit against crypto exchange affects Bitcoin ETF inflows", "Market reaction negative.")
    assert impact == "high"
    assert "BTC" in currencies


def test_classify_news_gold_yields():
    impact, currencies = classify_news_impact("Gold rallies as war concerns push yields down", "Bullion demand increases.")
    assert impact == "high"
    assert "XAU" in currencies


def test_classify_news_low_impact():
    impact, currencies = classify_news_impact("Local boutique coffee shop opens in downtown Seattle", "Owners excited for launch.")
    assert impact == "low"
    assert "USD" in currencies
