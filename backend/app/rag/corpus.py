from __future__ import annotations

CORPUS: list[dict] = [
    {
        "id": "ril-q1fy27-earnings",
        "symbol": "RELIANCE",
        "title": "RIL Q1 FY27 earnings transcript — Jio & retail commentary",
        "as_of": "2026-07-19",
        "kind": "earnings_transcript",
        "text": (
            "Reliance Industries reported consolidated revenue growth of 8% YoY. "
            "Jio average revenue per user rose 6% after the tariff hike. Retail EBITDA "
            "margin expanded 40 bps. Management guided that oil-to-chemicals volatility "
            "remains the swing factor. Capex for new energy is unchanged. No change in "
            "promoter pledge. Board declared an interim dividend. Audit opinion is unmodified."
        ),
    },
    {
        "id": "ril-sebi-shareholding",
        "symbol": "RELIANCE",
        "title": "SEBI shareholding pattern — RIL Jun 2026 quarter",
        "as_of": "2026-07-21",
        "kind": "sebi_filing",
        "text": (
            "Promoter holding stable at 50.1%. FII holding increased 42 bps quarter on quarter "
            "to 22.4%. Mutual fund holding was broadly unchanged. No substantial acquisition "
            "of shares or voting rights (SAST) trigger. Related-party transactions disclosed "
            "are in the ordinary course at arm's length as per audit committee note."
        ),
    },
    {
        "id": "infy-q1fy27-earnings",
        "symbol": "INFY",
        "title": "Infosys Q1 FY27 earnings — deal TCV and guidance",
        "as_of": "2026-07-17",
        "kind": "earnings_transcript",
        "text": (
            "Large deal TCV was $3.1 billion. Guidance for FY27 constant-currency growth "
            "was retained at 1% to 3%. Utilization excluding trainees was 85%. Attrition "
            "declined 80 bps. Management flagged delayed decision cycles in BFSI Europe. "
            "No material contingent liability added this quarter."
        ),
    },
    {
        "id": "hdfc-sebi-basel",
        "symbol": "HDFCBANK",
        "title": "HDFC Bank — Basel III pillar 3 and GNPA disclosure",
        "as_of": "2026-07-20",
        "kind": "sebi_filing",
        "text": (
            "Gross NPA at 1.24%, net NPA 0.33%. CET1 ratio 16.8%. Deposit growth 14% YoY, "
            "advances 11%. Slippage ratio stable. Management reiterated that merger-related "
            "LDR normalisation is on track. No RBI penalty in the reporting window."
        ),
    },
    {
        "id": "zomato-q1-unit-economics",
        "symbol": "ZOMATO",
        "title": "Eternal Ltd Q1 FY27 — food delivery unit economics",
        "as_of": "2026-07-22",
        "kind": "earnings_transcript",
        "text": (
            "Food delivery GOV grew 28% but contribution margin compressed 90 bps due to "
            "higher delivery-partner incentives in tier-2 cities. Blinkit store additions "
            "accelerated; quick-commerce remains EBITDA negative at the store cohort level "
            "for months 1-6. Management did not raise FY27 EBITDA guidance. Related-party "
            "ESOP charge increased. Going-concern note is clean but cash burn in new stores "
            "is disclosed as a key risk."
        ),
    },
    {
        "id": "zomato-sebi-promoter",
        "symbol": "ZOMATO",
        "title": "SEBI SAST / promoter sale intimation — Eternal Ltd",
        "as_of": "2026-08-11",
        "kind": "sebi_filing",
        "text": (
            "Promoter group filed an intimation of proposed open-market sale of up to 1.8% "
            "over 90 days for personal liquidity. This is not a pledged-share invocation. "
            "The filing is material for float and near-term supply overhang. No change in "
            "control is proposed."
        ),
    },
    {
        "id": "paytm-fy25-audit-emphasis",
        "symbol": "PAYTM",
        "title": "One97 Communications — FY25 auditor emphasis of matter (historical)",
        "as_of": "2025-05-08",
        "kind": "sebi_filing",
        "text": (
            "Statutory auditor included an emphasis of matter regarding payment-aggregation "
            "license conditions and related-party merchant entities. Management states "
            "remediation is ongoing. This document is the last complete annual filing in "
            "the local corpus. Q1 FY27 results have not been ingested."
        ),
    },
    {
        "id": "fii-nse-provisional",
        "symbol": "MACRO",
        "title": "NSE / NSDL provisional FII cash market flows — 01 Sep 2026",
        "as_of": "2026-09-01",
        "kind": "fii_disclosure",
        "text": (
            "Provisional FII cash was a net buy of ₹2,140 Cr. Sectoral extras: energy and "
            "private banks saw inflows; consumer internet saw profit-taking despite a broad "
            "midcap bid. DII were net buyers of ₹890 Cr. USDINR was stable. This is a "
            "provisional print and may revise after T+1."
        ),
    },
    {
        "id": "sebi-fno-retail-risk",
        "symbol": "MACRO",
        "title": "SEBI 2024 study — retail F&O participant outcomes",
        "as_of": "2024-09-30",
        "kind": "regulator_research",
        "text": (
            "SEBI analysis found that 89% of individual F&O traders incurred net losses. "
            "The study is cited here as a suitability constraint, not as a stock-specific "
            "signal. Recommendations that imply leveraged derivatives for inexperienced "
            "accounts should be blocked or heavily caveated."
        ),
    },
]
