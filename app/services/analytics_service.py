from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import analytics_repository
from app.schemas.analytics_schema import AnalyticsQuery


async def patients(s: AsyncSession, q: AnalyticsQuery) -> dict:
    """Hospital-wide patient volume. Aggregate counts only, safe for every signed-in user."""
    series = await analytics_repository.patient_series(s, q.from_, q.to, q.group_by)
    total = await analytics_repository.total_patients(s)
    return {
        "groupBy": q.group_by,
        "series": series,
        "totals": {
            "totalPatients": total,
            "newPatients": sum(x["newPatients"] for x in series),
            "appointments": sum(x["requested"] + x["approved"] + x["checked"] + x["cancelled"] for x in series),
            "checked": sum(x["checked"] for x in series),
            "pending": sum(x["requested"] + x["approved"] for x in series),
        },
    }


def _num(x: float) -> int | float:
    """JSON numbers like JS: 120.0 -> 120."""
    return int(x) if float(x).is_integer() else x


async def revenue(s: AsyncSession, q: AnalyticsQuery) -> dict:
    """Revenue from checked visits, split into collected (paid via Stripe) and pending."""
    rows = await analytics_repository.revenue_series(s, q.from_, q.to, q.group_by)
    by_specialty = await analytics_repository.revenue_by_specialty(s, q.from_, q.to)
    series = []
    for r in rows:
        collected, pending = float(r["collected"]), float(r["pending"])
        series.append(
            {
                "bucket": r["bucket"],
                "collected": _num(collected),
                "pending": _num(pending),
                "revenue": _num(collected + pending),
                "visits": r["visits"],
            }
        )
    collected = sum(float(r["collected"]) for r in rows)
    pending = sum(float(r["pending"]) for r in rows)
    billed = collected + pending
    visits = sum(r["visits"] for r in rows)
    return {
        "groupBy": q.group_by,
        "series": series,
        "bySpecialty": [
            {"specialty": x["specialty"], "revenue": _num(float(x["revenue"])), "visits": x["visits"]} for x in by_specialty
        ],
        "totals": {
            "collected": _num(collected),
            "pending": _num(pending),
            "revenue": _num(billed),
            "visits": visits,
            "averagePerVisit": _num(billed / visits) if visits else 0,
            "collectionRate": _num(collected / billed) if billed else 0,
        },
    }


async def doctors(s: AsyncSession, q: AnalyticsQuery) -> dict:
    """Checked vs still-to-see patients for every doctor."""
    rows = await analytics_repository.doctor_workload(s, q.from_, q.to)
    return {
        "doctors": rows,
        "totals": {"checked": sum(d["checked"] for d in rows), "unchecked": sum(d["unchecked"] for d in rows)},
    }
