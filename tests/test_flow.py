"""End-to-end smoke test against a real Postgres (DATABASE_URL). Run on a scratch database:

    python -m app.db.migrate && pytest -q
"""

import asyncio
import uuid
from datetime import date, timedelta

import httpx
import pyotp

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal
from app.repositories import user_repository
from app.utils.password_util import hash_password
from app.app import app

PW = "Str0ng!Passw0rd"
TODAY = date.today()
RUN = uuid.uuid4().hex[:8]


async def reset_database() -> None:
    """Wipes every table and re-creates the super admin, so the test is re-runnable and its totals are exact.
    Refuses to run unless the database name ends in _test."""
    assert settings.async_database_url.rsplit("/", 1)[-1].endswith("_test"), "point DATABASE_URL at a *_test database"
    async with SessionLocal() as s:
        await s.execute(text("truncate users cascade"))
        await user_repository.create(s, email="superadmin@hospital.local", full_name="Super Admin", password_hash=await hash_password("ChangeMe@12345"), role="super_admin")
        await s.commit()


async def flow() -> None:
    await reset_database()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t/api") as c:

        def hdr(token):
            return {"Authorization": f"Bearer {token}"}

        async def call(method, path, token=None, status=None, **kw):
            kw.setdefault("headers", hdr(token) if token else None)
            r = await c.request(method, path, **kw)
            if status is not None:
                assert r.status_code == status, f"{method} {path} -> {r.status_code} {r.text}"
            return r

        async def staff_login(email, password=PW):
            r = (await call("POST", "/auth/login", json={"email": email, "password": password}, status=200)).json()
            if r["status"] == "mfa_setup_required":
                setup = (await call("POST", "/auth/mfa/setup", r["setupToken"], 200)).json()
                assert setup["qrCodeDataUrl"].startswith("data:image/png;base64,")
                enabled = (await call("POST", "/auth/mfa/enable", r["setupToken"], 200, json={"code": pyotp.TOTP(setup["secret"]).now()})).json()
                assert len(enabled["recoveryCodes"]) == 8
                return enabled["token"], setup["secret"], enabled["recoveryCodes"]
            raise AssertionError(r)

        # ── super admin: forced MFA enrolment, then 2-step login ─────────────
        sa, secret, recovery = await staff_login("superadmin@hospital.local", "ChangeMe@12345")
        r = (await call("POST", "/auth/login", json={"email": "superadmin@hospital.local", "password": "ChangeMe@12345"}, status=200)).json()
        assert r["status"] == "mfa_required"
        await call("POST", "/auth/mfa/verify-login", r["mfaToken"], 401, json={"code": "000000"})
        r2 = (await call("POST", "/auth/mfa/verify-login", r["mfaToken"], 200, json={"recoveryCode": recovery[0]})).json()
        assert r2["user"]["capabilities"]["deletePatients"] is True
        await call("POST", "/auth/mfa/verify-login", r["mfaToken"], 401, json={"recoveryCode": recovery[0]})  # single use
        await call("POST", "/auth/mfa/verify-login", r["mfaToken"], 400, json={})  # exactly one of code/recoveryCode
        me = (await call("GET", "/auth/me", sa, 200)).json()["user"]
        assert me["role"] == "super_admin"
        await call("GET", "/auth/me", None, 401)
        await call("GET", "/auth/me", "garbage", 401)

        # ── create staff + patient ───────────────────────────────────────────
        def mk(role, **extra):
            return dict(email=f"{role}-{RUN}@example.com", password=PW, fullName=f"{role.title()} {RUN}", role=role, **extra)

        bad = await call("POST", "/users", sa, 400, json={**mk("doctor")})  # missing specialty/license
        assert "specialty" in bad.json()["details"]
        await call("POST", "/users", sa, 400, json={**mk("receptionist"), "password": "weak"})
        doc = (await call("POST", "/users", sa, 201, json=mk("doctor", specialty="cardiologist", licenseNo=f"LIC-{RUN}", consultationFee=500))).json()["user"]
        await call("POST", "/users", sa, 409, json=mk("doctor", specialty="cardiologist", licenseNo=f"LIC-{RUN}x"))  # duplicate email
        rec = (await call("POST", "/users", sa, 201, json=mk("receptionist"))).json()["user"]
        acc = (await call("POST", "/users", sa, 201, json=mk("accounts"))).json()["user"]
        reg = (await call("POST", "/auth/register", status=201, json={"email": f"pat-{RUN}@example.com", "password": PW, "fullName": "Pat Ient", "gender": "female", "bloodGroup": "O+", "dateOfBirth": "1990-05-01"})).json()["user"]
        assert reg["role"] == "patient"
        await call("POST", "/auth/register", status=400, json={"email": "x", "password": PW, "fullName": "A"})
        doc_t, _, _ = await staff_login(doc["email"])
        rec_t, _, _ = await staff_login(rec["email"])
        acc_t, _, _ = await staff_login(acc["email"])
        pat_login = (await call("POST", "/auth/login", status=200, json={"email": f"PAT-{RUN}@example.com", "password": PW})).json()
        assert pat_login["status"] == "authenticated"
        pat_t = pat_login["token"]
        await call("POST", "/auth/login", status=401, json={"email": reg["email"], "password": "nope"})

        # ── permissions ──────────────────────────────────────────────────────
        await call("GET", "/users", pat_t, 403)
        await call("GET", "/admins", rec_t, 403)
        await call("GET", "/patients", pat_t, 403)
        await call("GET", "/users/doctors?specialty=cardiologist", pat_t, 200)
        docs = (await call("GET", "/users/doctors", pat_t, 200)).json()["doctors"]
        assert docs[0]["consultationFee"] == "500.00" and docs[0]["fullName"]

        # ── appointment lifecycle ────────────────────────────────────────────
        await call("POST", "/appointments", pat_t, 400, json={"specialty": "cardiologist", "date": "2020-01-01"})
        await call("POST", "/appointments", pat_t, 400, json={"specialty": "cardiologist", "date": "2026-02-30"})
        appt = (await call("POST", "/appointments", pat_t, 201, json={"specialty": "cardiologist", "date": TODAY.isoformat(), "reason": "chest pain", "preferredDoctorId": doc["id"]})).json()["appointment"]
        assert appt["status"] == "requested" and appt["appointmentDate"] == TODAY.isoformat()
        mine = (await call("GET", "/appointments/mine", pat_t, 200)).json()["appointments"]
        assert mine[0]["patientName"] == "Pat Ient" and mine[0]["prescriptions"] == []
        avail = (await call("GET", f"/appointments/availability?specialty=cardiologist&date={TODAY}", rec_t, 200)).json()["doctors"]
        assert avail[0]["available"] is True and avail[0]["appointmentsThatDay"] == 0
        lst = (await call("GET", "/appointments?status=requested&search=pat", rec_t, 200)).json()
        assert lst["total"] >= 1 and lst["items"][0]["requestedDoctorName"]
        await call("GET", "/appointments?pageSize=500", rec_t, 400)

        # doctor on leave tomorrow -> unavailable then
        tomorrow = TODAY + timedelta(days=1)
        await call("PATCH", f"/appointments/{appt['id']}/approve", rec_t, 400, json={"doctorId": rec["id"]})
        ap = (await call("PATCH", f"/appointments/{appt['id']}/approve", rec_t, 200, json={"doctorId": doc["id"], "note": "ok"})).json()["appointment"]
        assert ap["status"] == "approved" and ap["doctorId"] == doc["id"]
        await call("PATCH", f"/appointments/{appt['id']}/reject", rec_t, 409, json={})

        # ── doctor consultation ──────────────────────────────────────────────
        dp = (await call("GET", "/doctor/patients", doc_t, 200)).json()
        assert dp["total"] == 1 and dp["items"][0]["consultationFee"] == "500.00"
        await call("GET", "/doctor/patients", rec_t, 403)
        d = (await call("GET", f"/doctor/appointments/{appt['id']}", doc_t, 200)).json()
        assert d["patient"]["bloodGroup"] == "O+" and d["patient"]["dateOfBirth"] == "1990-05-01"
        pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
        base = f"/doctor/appointments/{appt['id']}/prescriptions"
        await call("POST", base, doc_t, 415, content=pdf, headers={**hdr(doc_t), "Content-Type": "text/plain"})
        await call("POST", base, doc_t, 400, content=b"not a pdf at all", headers={**hdr(doc_t), "Content-Type": "application/pdf"})
        rx = (await call("POST", base, doc_t, 201, content=pdf, headers={**hdr(doc_t), "Content-Type": "application/pdf", "X-File-Name": "My%20Rx"})).json()["prescription"]
        assert rx["fileName"] == "My Rx.pdf" and "storedName" not in rx
        f = await call("GET", f"/prescriptions/{rx['id']}/file", pat_t, 200)
        assert f.content == pdf and f.headers["content-type"] == "application/pdf"
        await call("GET", f"/prescriptions/{rx['id']}/file", acc_t, 403)
        await call("GET", f"/prescriptions/{rx['id']}/file", rec_t, 200)
        await call("PATCH", f"/doctor/appointments/{appt['id']}/check", doc_t, 200)
        await call("PATCH", f"/doctor/appointments/{appt['id']}/check", doc_t, 409)

        # ── shared checked list, payments, analytics ─────────────────────────
        ch = (await call("GET", "/visits/checked", acc_t, 200)).json()
        assert ch["items"][0]["prescriptionCount"] == 1 and ch["items"][0]["prescriptions"] == []
        ch = (await call("GET", "/visits/checked", rec_t, 200)).json()
        assert len(ch["items"][0]["prescriptions"]) == 1
        await call("GET", "/visits/checked", pat_t, 403)
        rcv = (await call("GET", "/payments/receivables", acc_t, 200)).json()
        assert rcv["items"][0]["paymentStatus"] == "unpaid" and rcv["items"][0]["payment"] is None
        s = (await call("GET", "/payments/summary", acc_t, 200)).json()
        assert s["outstanding"] == "500.00" and s["unpaidCount"] == 1 and s["currency"] == "inr"
        await call("POST", "/payments/checkout", acc_t, 503, json={"appointmentId": appt["id"]})
        await call("POST", "/payments/webhook", None, 503, content=b"{}")
        await call("GET", "/payments/summary", rec_t, 403)

        rng = f"from={TODAY - timedelta(days=2)}&to={TODAY + timedelta(days=2)}"
        pa = (await call("GET", f"/analytics/patients?{rng}", pat_t, 200)).json()
        assert len(pa["series"]) == 5 and pa["totals"]["checked"] >= 1 and pa["totals"]["newPatients"] >= 1
        rv = (await call("GET", f"/analytics/revenue?{rng}&groupBy=month", rec_t, 200)).json()
        assert rv["totals"]["pending"] == 500 and rv["bySpecialty"][0]["specialty"] == "cardiologist"
        dw = (await call("GET", f"/analytics/doctors?{rng}", doc_t, 200)).json()
        assert dw["totals"]["checked"] == 1
        await call("GET", f"/analytics/doctors?{rng}", pat_t, 403)
        await call("GET", "/analytics/patients?from=2024-01-02&to=2024-01-01", pat_t, 400)

        # ── admins, assignments, department ──────────────────────────────────
        adm = (await call("POST", "/admins", sa, 201, json={**{k: v for k, v in mk("admin").items() if k != "role"}, "baseRole": "receptionist", "assignments": [{"area": "reception_management"}, {"area": "patient_management"}]})).json()
        assert adm["user"]["role"] == "admin"
        adm2 = (await call("POST", "/admins", sa, 201, json={"email": f"adm2-{RUN}@example.com", "password": PW, "fullName": "Second Admin", "baseRole": "doctor", "assignments": [{"area": "reception_management"}]})).json()
        assert adm2["reassigned"][0]["area"] == "reception_management"  # taken over from the first admin
        adm_t, _, _ = await staff_login(adm["user"]["email"])
        ov = (await call("GET", "/department/overview", adm_t, 200)).json()
        assert [x["area"] for x in ov["departments"]] == ["patient_management"]
        ov = (await call("GET", "/department/overview", sa, 200)).json()
        assert len(ov["departments"]) == 5
        promo = (await call("POST", f"/admins/{acc['id']}/promote", sa, 200, json={"assignments": [{"area": "accounts_management"}]})).json()
        assert promo["user"]["baseRole"] == "accounts"
        assert (await call("GET", f"/admins/{acc['id']}/assignments", sa, 200)).json()["assignments"][0]["area"] == "accounts_management"
        dem = (await call("POST", f"/admins/{acc['id']}/demote", sa, 200, json={"role": "accounts"})).json()["user"]
        assert dem["role"] == "accounts" and dem["baseRole"] is None

        # ── duty / attendance / leave ────────────────────────────────────────
        duty = (await call("PUT", f"/staff/{doc['id']}/duty", sa, 200, json={"startTime": "09:00", "endTime": "17:30", "workDays": [5, 1, 2, 3, 4]})).json()["duty"]
        assert duty["startTime"] == "09:00" and duty["workDays"] == [1, 2, 3, 4, 5]
        await call("PUT", f"/staff/{doc['id']}/duty", sa, 400, json={"startTime": "09:00", "endTime": "09:00", "workDays": [1]})
        assert (await call("GET", f"/staff/{doc['id']}/duty", sa, 200)).json()["duty"]["endTime"] == "17:30"
        mk_att = (await call("POST", "/attendance", sa, 201, json={"userId": doc["id"], "date": TODAY.isoformat(), "status": "present", "notes": "on time"})).json()["attendance"]
        assert mk_att["status"] == "present"
        await call("POST", "/attendance", sa, 201, json={"userId": doc["id"], "date": TODAY.isoformat(), "status": "late"})
        sheet = (await call("GET", f"/attendance?date={TODAY}", sa, 200)).json()
        assert any(e["attendance"] and e["attendance"]["status"] == "late" for e in sheet["entries"])
        await call("POST", "/attendance", sa, 400, json={"userId": doc["id"], "date": (TODAY + timedelta(days=30)).isoformat(), "status": "present"})

        lv = (await call("POST", "/leaves/request", doc_t, 201, json={"leaveType": "sick", "startDate": tomorrow.isoformat(), "endDate": (tomorrow + timedelta(days=1)).isoformat()})).json()["leave"]
        assert lv["status"] == "pending"
        await call("POST", "/leaves/request", pat_t, 403, json={"leaveType": "sick", "startDate": tomorrow.isoformat(), "endDate": tomorrow.isoformat()})
        await call("POST", "/leaves/request", doc_t, 400, json={"leaveType": "sick", "startDate": tomorrow.isoformat(), "endDate": TODAY.isoformat()})
        await call("PATCH", f"/leaves/{lv['id']}/review", sa, 200, json={"status": "approved"})
        await call("PATCH", f"/leaves/{lv['id']}/review", sa, 409, json={"status": "approved"})
        assert len((await call("GET", "/leaves/mine", doc_t, 200)).json()["leaves"]) == 1
        assert (await call("GET", f"/leaves?userId={doc['id']}&status=approved", sa, 200)).json()["leaves"][0]["userName"]
        av = (await call("GET", f"/appointments/availability?specialty=cardiologist&date={tomorrow}", rec_t, 200)).json()["doctors"]
        assert av[0]["available"] is False and av[0]["reason"] == "on_leave"
        cal = (await call("GET", f"/analytics/attendance-calendar?month={TODAY:%Y-%m}", doc_t, 200)).json()
        assert cal["summary"]["late"] == 1 and len(cal["days"]) >= 28 and cal["duty"]["startTime"] == "09:00"
        await call("GET", f"/analytics/attendance-calendar?month={TODAY:%Y-%m}&userId={doc["id"]}", pat_t, 403)
        await call("GET", "/analytics/attendance-calendar?month=2024-13", doc_t, 400)
        await call("DELETE", f"/leaves/{lv['id']}", sa, 204)

        # ── patients: edit / delete ──────────────────────────────────────────
        pl = (await call("GET", "/patients?search=pat%20i&sortBy=joined&order=desc", rec_t, 200)).json()
        assert pl["total"] == 1
        upd = (await call("PATCH", f"/patients/{reg['id']}", rec_t, 200, json={"fullName": "Pat Updated", "address": "1 Main St", "phone": None})).json()["patient"]
        assert upd["fullName"] == "Pat Updated" and upd["address"] == "1 Main St" and upd["bloodGroup"] == "O+"
        await call("PATCH", f"/patients/{reg['id']}", rec_t, 400, json={})
        got = (await call("GET", f"/patients/{reg['id']}", rec_t, 200)).json()
        assert got["appointments"][0]["status"] == "checked"
        await call("DELETE", f"/patients/{reg['id']}", rec_t, 403)
        await call("DELETE", f"/patients/{reg['id']}", sa, 204)
        await call("GET", f"/patients/{reg['id']}", rec_t, 404)
        await call("GET", f"/prescriptions/{rx['id']}/file", rec_t, 404)  # cascaded away

        # ── user management ──────────────────────────────────────────────────
        await call("PATCH", f"/users/{rec['id']}/active", sa, 200, json={"isActive": False})
        await call("GET", "/auth/me", rec_t, 401)  # deactivated
        await call("DELETE", f"/users/{me['id']}", sa, 400)
        await call("DELETE", f"/users/{rec['id']}", sa, 204)
        assert (await call("GET", "/nope", None, 404)).json() == {"error": "Not found"}
        assert (await c.get("http://t/health")).json() == {"status": "ok"}
        # a patient may switch MFA on and off again
        pt = (await call("POST", "/auth/register", status=201, json={"email": f"p2-{RUN}@example.com", "password": PW, "fullName": "Pat Two"})).json()["user"]
        pt_t = (await call("POST", "/auth/login", status=200, json={"email": pt["email"], "password": PW})).json()["token"]
        st = (await call("POST", "/auth/mfa/setup", pt_t, 200)).json()
        en = (await call("POST", "/auth/mfa/enable", pt_t, 200, json={"code": pyotp.TOTP(st["secret"]).now()})).json()
        rv = (await call("POST", "/auth/mfa/secret", en["token"], 200, json={"password": PW, "code": pyotp.TOTP(st["secret"]).now()})).json()
        assert rv["secret"] == st["secret"]
        await call("POST", "/auth/mfa/disable", en["token"], 204, json={"password": PW, "code": pyotp.TOTP(st["secret"]).now()})
        await call("POST", "/auth/mfa/disable", en["token"], 400, json={"password": PW, "code": "123456"})


def test_full_flow():
    asyncio.run(flow())
