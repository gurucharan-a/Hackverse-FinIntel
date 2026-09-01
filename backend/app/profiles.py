from __future__ import annotations

from app.models import Holding, UserProfile

USERS: dict[str, UserProfile] = {
    "priya": UserProfile(
        user_id="priya",
        name="Priya Sharma",
        age=46,
        risk_tolerance="conservative",
        horizon_years=8,
        fno_allowed=False,
        max_single_name_pct=0.18,
        behavioral_flags=["loss_averse", "sold_after_3pct_drawdown"],
        watchlist=["RELIANCE", "HDFCBANK", "INFY"],
        holdings=[
            Holding(symbol="HDFCBANK", qty=40, avg_cost=1480.0),
            Holding(symbol="RELIANCE", qty=12, avg_cost=2710.0),
            Holding(symbol="INFY", qty=25, avg_cost=1790.0),
        ],
    ),
    "arjun": UserProfile(
        user_id="arjun",
        name="Arjun Mehta",
        age=24,
        risk_tolerance="aggressive",
        horizon_years=3,
        fno_allowed=True,
        max_single_name_pct=0.35,
        behavioral_flags=["fomo_chases_breakouts", "high_turnover"],
        watchlist=["ZOMATO", "PAYTM", "RELIANCE"],
        holdings=[
            Holding(symbol="ZOMATO", qty=800, avg_cost=214.0),
            Holding(symbol="PAYTM", qty=120, avg_cost=680.0),
            Holding(symbol="RELIANCE", qty=5, avg_cost=2900.0),
        ],
    ),
    "meera": UserProfile(
        user_id="meera",
        name="Meera Iyer",
        age=33,
        risk_tolerance="balanced",
        horizon_years=5,
        fno_allowed=False,
        max_single_name_pct=0.22,
        behavioral_flags=["holds_through_earnings", "rebalances_quarterly"],
        watchlist=["RELIANCE", "INFY", "ZOMATO", "HDFCBANK"],
        holdings=[
            Holding(symbol="RELIANCE", qty=8, avg_cost=2800.0),
            Holding(symbol="INFY", qty=15, avg_cost=1810.0),
            Holding(symbol="ZOMATO", qty=200, avg_cost=240.0),
        ],
    ),
}


def get_user(user_id: str) -> UserProfile:
    if user_id not in USERS:
        raise KeyError(user_id)
    return USERS[user_id]
