#!/usr/bin/env python3
"""
Cartwell Shop API (mock server)
===============================

A small mock e-commerce API for data engineering training.
Standard library only. No pip install. Python 3.9+.

    python cartwell_api.py
    python cartwell_api.py --port 9000
    python cartwell_api.py --token my_secret_token
    python cartwell_api.py --as-of 2026-11-15     # pretend today is this date

Every response is deterministic: the same request returns the same bytes
on every machine and every run.

Endpoints (all GET, all need "Authorization: Bearer <token>" except /health):
    /health                         -> JSON
    /v1/products                    -> JSON   (full catalog, no date)
    /v1/customers?date=YYYY-MM-DD   -> JSON   (customers who signed up that day)
    /v1/orders?date=YYYY-MM-DD      -> CSV    (one row per order line)
    /v1/transactions?date=YYYY-MM-DD-> NDJSON (one JSON object per line)
"""

import argparse
import csv
import hashlib
import hmac
import io
import json
import re
import traceback
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

START_DATE = date(2026, 10, 1)          # the shop opened on this day
DEFAULT_TOKEN = "cw_live_7f3a9c2e5b1d4086"
CURRENCY = "INR"
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

# Set from --as-of at startup. None means use the real UTC date.
AS_OF = None


# ---------------------------------------------------------------- helpers

def h(*parts):
    """Stable hash of the parts, as a non-negative int. Same on every machine."""
    raw = "|".join(str(p) for p in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")


def pick(seq, *parts):
    return seq[h(*parts) % len(seq)]


def ts_on(d, seconds):
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(seconds=seconds)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def money(paise):
    return round(paise / 100, 2)


def today_utc():
    return AS_OF if AS_OF is not None else datetime.now(timezone.utc).date()


def latest_available():
    """A day's data is published once that UTC day is over."""
    return today_utc() - timedelta(days=1)


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


# ---------------------------------------------------------------- reference data

PRODUCTS = [
    ("P001", "Cotton Crew T-Shirt", "Apparel", 49900),
    ("P002", "Slim Fit Jeans", "Apparel", 149900),
    ("P003", "Running Shoes", "Footwear", 289900),
    ("P004", "Leather Sandals", "Footwear", 119900),
    ("P005", "Steel Water Bottle 1L", "Home & Kitchen", 59900),
    ("P006", "Non-Stick Frying Pan", "Home & Kitchen", 89900),
    ("P007", "Ceramic Coffee Mug Set", "Home & Kitchen", 69900),
    ("P008", "Wireless Earbuds", "Electronics", 199900),
    ("P009", "USB-C Charger 30W", "Electronics", 129900),
    ("P010", "Bluetooth Speaker", "Electronics", 249900),
    ("P011", "Basmati Rice 5kg", "Grocery", 64900),
    ("P012", "Assam Tea 500g", "Grocery", 27900),
    ("P013", "Almonds 1kg", "Grocery", 89900),
    ("P014", "Notebook Pack of 5", "Stationery", 24900),
    ("P015", "Gel Pen Set", "Stationery", 14900),
    ("P016", "Yoga Mat", "Sports", 79900),
    ("P017", "Cricket Bat", "Sports", 219900),
    ("P018", "Backpack 30L", "Bags", 159900),
    ("P019", "Face Wash 100ml", "Beauty", 19900),
    ("P020", "Sunscreen SPF 50", "Beauty", 34900),
]

FIRST_NAMES = ["Aarav", "Vivaan", "Aditya", "Ishaan", "Rohan", "Kabir", "Arjun",
               "Sai", "Rahul", "Nikhil", "Ananya", "Diya", "Priya", "Sneha",
               "Kavya", "Meera", "Riya", "Pooja", "Neha", "Tanvi"]
LAST_NAMES = ["Sharma", "Patil", "Deshpande", "Kulkarni", "Iyer", "Reddy", "Nair",
              "Gupta", "Joshi", "Mehta", "Shah", "Rao", "Verma", "Pawar", "Chavan",
              "Bose", "Das", "Singh", "Khan", "Fernandes"]
CITIES = [("Pune", "Maharashtra", "411"), ("Mumbai", "Maharashtra", "400"),
          ("Nagpur", "Maharashtra", "440"), ("Bengaluru", "Karnataka", "560"),
          ("Hyderabad", "Telangana", "500"), ("Chennai", "Tamil Nadu", "600"),
          ("New Delhi", "Delhi", "110"), ("Ahmedabad", "Gujarat", "380"),
          ("Kolkata", "West Bengal", "700"), ("Jaipur", "Rajasthan", "302")]
STREETS = ["MG Road", "Station Road", "FC Road", "Park Street", "Link Road",
           "Main Road", "Church Street", "Ring Road"]
METHODS = ["UPI", "UPI", "UPI", "CARD", "CARD", "NETBANKING", "WALLET"]
FAILURE_REASONS = ["INSUFFICIENT_FUNDS", "BANK_TIMEOUT", "CARD_DECLINED"]


# ---------------------------------------------------------------- data generation

def customers_on(d):
    return 0 if d < START_DATE else 3 + h("cust_n", d) % 6          # 3 to 8 per day


@lru_cache(maxsize=None)
def customers_before(d):
    """How many customers signed up strictly before day d."""
    total, cur = 0, START_DATE
    while cur < d:
        total += customers_on(cur)
        cur += timedelta(days=1)
    return total


def build_customers(d):
    first_num = customers_before(d) + 1
    n = customers_on(d)
    secs = sorted(h("cust_t", d, i) % 86400 for i in range(n))
    out = []
    for i in range(n):
        num = first_num + i
        fn = pick(FIRST_NAMES, "fn", num)
        ln = pick(LAST_NAMES, "ln", num)
        city, state, pin3 = pick(CITIES, "city", num)
        out.append({
            "customer_id": "C%05d" % num,
            "first_name": fn,
            "last_name": ln,
            "email": ("%s.%s%d@example.com" % (fn, ln, num)).lower(),
            "phone": "+91 9%09d" % (h("phone", num) % 10**9),
            "signup_at": iso(ts_on(d, secs[i])),
            "address": {
                "line1": "%d, %s" % (1 + h("house", num) % 250, pick(STREETS, "street", num)),
                "city": city,
                "state": state,
                "pincode": pin3 + "%03d" % (h("pin", num) % 1000),
            },
            "marketing_opt_in": h("optin", num) % 3 != 0,
        })
    return out


def build_orders(d):
    # Orders only come from customers who signed up before this day,
    # so an order never predates its customer. Day one has no orders.
    pool = customers_before(d)
    if pool == 0:
        return []
    n = 5 + h("ord_n", d) % 11                                        # 5 to 15 per day
    secs = sorted(h("ord_t", d, i) % (22 * 3600) for i in range(n))  # before 22:00 UTC
    orders = []
    for i in range(n):
        oid = "O%s-%03d" % (d.strftime("%Y%m%d"), i + 1)
        lines, used = [], set()
        for ln in range(1 + h("ord_lines", oid) % 4):                 # 1 to 4 lines
            k = 0
            p = pick(PRODUCTS, "ord_p", oid, ln, k)
            while p[0] in used:
                k += 1
                p = pick(PRODUCTS, "ord_p", oid, ln, k)
            used.add(p[0])
            qty = 1 + h("ord_q", oid, ln) % 3
            lines.append({"line_number": ln + 1, "product_id": p[0], "quantity": qty,
                          "unit_paise": p[3], "line_paise": p[3] * qty})
        orders.append({
            "order_id": oid,
            "order_ts": ts_on(d, secs[i]),
            "customer_id": "C%05d" % (1 + h("ord_c", oid) % pool),
            "status": "CANCELLED" if h("ord_s", oid) % 12 == 0 else "PLACED",
            "lines": lines,
            "total_paise": sum(l["line_paise"] for l in lines),
        })
    return orders


def build_transactions(d):
    out = []
    for o in build_orders(d):
        oid = o["order_id"]
        method = pick(METHODS, "tx_m", oid)
        t = o["order_ts"] + timedelta(seconds=30 + h("tx_d", oid) % 600)
        seq = 0

        def txn(kind, status, when, reason=None):
            return {
                "transaction_id": "T%012X" % (h("tx_id", oid, seq) % 16**12),
                "order_id": oid,
                "txn_ts": iso(when),
                "type": kind,
                "method": method,
                "amount": money(o["total_paise"]),
                "currency": CURRENCY,
                "status": status,
                "failure_reason": reason,
            }

        if h("tx_fail", oid) % 8 == 0:                     # first attempt fails, retry succeeds
            out.append(txn("PAYMENT", "FAILED", t, pick(FAILURE_REASONS, "tx_r", oid)))
            seq += 1
            t += timedelta(seconds=60 + h("tx_retry", oid) % 600)
        out.append(txn("PAYMENT", "SUCCESS", t))
        seq += 1
        if o["status"] == "CANCELLED":                     # cancelled orders get refunded
            t += timedelta(seconds=1800 + h("tx_ref", oid) % 1800)
            out.append(txn("REFUND", "SUCCESS", t))
    out.sort(key=lambda x: (x["txn_ts"], x["transaction_id"]))
    return out


# ---------------------------------------------------------------- request parsing

def parse_date(q):
    vals = q.get("date")
    if not vals or not vals[0]:
        raise ApiError(400, "missing_parameter",
                       "Query parameter 'date' is required, format YYYY-MM-DD.")
    if len(vals) > 1:
        raise ApiError(400, "invalid_parameter", "Pass 'date' only once.")
    raw = vals[0]
    if not DATE_RE.fullmatch(raw):
        raise ApiError(400, "invalid_parameter",
                       "date '%s' is not in YYYY-MM-DD format." % raw)
    try:
        d = date.fromisoformat(raw)
    except ValueError:
        raise ApiError(400, "invalid_parameter", "date '%s' is not a real date." % raw)
    latest = latest_available()
    if d > latest:
        raise ApiError(400, "date_not_available",
                       "Data for %s is not available yet. Latest available date is %s. "
                       "A day is published after it ends at 00:00 UTC." % (d, latest))
    return d


# ---------------------------------------------------------------- routes

def route_products(q):
    items = [{"product_id": p[0], "name": p[1], "category": p[2],
              "price": money(p[3]), "currency": CURRENCY} for p in PRODUCTS]
    return 200, "json", {"count": len(items), "products": items}


def route_customers(q):
    d = parse_date(q)
    items = build_customers(d)
    return 200, "json", {"date": d.isoformat(), "count": len(items), "customers": items}


def route_orders(q):
    d = parse_date(q)
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["order_id", "order_ts", "customer_id", "order_status", "line_number",
                "product_id", "quantity", "unit_price", "line_total", "currency"])
    for o in build_orders(d):
        for l in o["lines"]:
            w.writerow([o["order_id"], iso(o["order_ts"]), o["customer_id"], o["status"],
                        l["line_number"], l["product_id"], l["quantity"],
                        "%.2f" % money(l["unit_paise"]), "%.2f" % money(l["line_paise"]),
                        CURRENCY])
    return 200, "csv", buf.getvalue()


def route_transactions(q):
    d = parse_date(q)
    body = "".join(json.dumps(t) + "\n" for t in build_transactions(d))
    return 200, "ndjson", body


ROUTES = {
    "/v1/products": route_products,
    "/v1/customers": route_customers,
    "/v1/orders": route_orders,
    "/v1/transactions": route_transactions,
}

CONTENT_TYPES = {
    "json": "application/json; charset=utf-8",
    "csv": "text/csv; charset=utf-8",
    "ndjson": "application/x-ndjson; charset=utf-8",
}


# ---------------------------------------------------------------- HTTP plumbing

class Handler(BaseHTTPRequestHandler):
    server_version = "CartwellAPI/1.0"
    sys_version = ""

    def log_message(self, fmt, *args):
        print("%s - %s" % (self.address_string(), fmt % args), flush=True)

    def _send(self, status, kind, payload, extra=None):
        if kind == "json":
            body = (json.dumps(payload, indent=2) + "\n").encode("utf-8")
        else:
            body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", CONTENT_TYPES[kind])
        self.send_header("Content-Length", str(len(body)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, code, message, extra=None):
        self._send(status, "json", {"error": code, "message": message}, extra)

    def _authorized(self):
        scheme, _, token = self.headers.get("Authorization", "").partition(" ")
        return (scheme.lower() == "bearer"
                and hmac.compare_digest(token.strip().encode(), self.server.token.encode()))

    def do_GET(self):
        try:
            u = urlparse(self.path)
            path = u.path.rstrip("/") or "/"
            if path == "/health":
                return self._send(200, "json", {"status": "ok"})
            if path not in ROUTES:
                return self._error(404, "not_found", "No endpoint at %s" % u.path)
            if not self._authorized():
                return self._error(401, "unauthorized",
                                   "Missing or invalid token. Send header: "
                                   "Authorization: Bearer <token>",
                                   {"WWW-Authenticate": 'Bearer realm="cartwell"'})
            status, kind, payload = ROUTES[path](parse_qs(u.query, keep_blank_values=True))
            return self._send(status, kind, payload)
        except ApiError as e:
            return self._error(e.status, e.code, e.message)
        except BrokenPipeError:
            return
        except Exception:
            print(traceback.format_exc(), flush=True)
            return self._error(500, "server_error", "Unexpected server error.")

    def _not_allowed(self):
        self._error(405, "method_not_allowed", "Only GET is supported.", {"Allow": "GET"})

    do_POST = do_PUT = do_PATCH = do_DELETE = _not_allowed


def main():
    global AS_OF
    ap = argparse.ArgumentParser(description="Cartwell Shop mock API")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--token", default=DEFAULT_TOKEN, help="bearer token clients must send")
    ap.add_argument("--as-of", help="pretend today (UTC) is this date, YYYY-MM-DD")
    args = ap.parse_args()

    if args.as_of:
        if not DATE_RE.fullmatch(args.as_of):
            ap.error("--as-of must be YYYY-MM-DD")
        AS_OF = date.fromisoformat(args.as_of)

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    srv.token = args.token
    print("=" * 60, flush=True)
    print(" Cartwell Shop API (mock)", flush=True)
    print(" URL   : http://%s:%d" % (args.host, args.port), flush=True)
    print(" Token : %s" % args.token, flush=True)
    print(" Data  : %s to %s (UTC)" % (START_DATE, latest_available()), flush=True)
    print(" Stop  : Ctrl-C", flush=True)
    print("=" * 60, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down", flush=True)
        srv.shutdown()


if __name__ == "__main__":
    main()
