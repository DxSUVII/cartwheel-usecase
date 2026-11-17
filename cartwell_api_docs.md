# Cartwell Shop API

Cartwell is an online shop. This API gives you its products, customers, orders and payment transactions. It is the data source for your whole project.

## Running it

```
python cartwell_api.py
```

Needs Python 3.9 or newer. Nothing to install. The server prints its URL and token when it starts. Default URL: `http://127.0.0.1:8000`

## Authentication

Every endpoint except `/health` needs a bearer token in the request header:

```
Authorization: Bearer <token>
```

A missing or wrong token returns `401`. Do not hardcode the token in your code. It belongs in Vault.

## Data availability

The shop opened on **2026-10-01**. All dates and timestamps are in **UTC**.

A day's data is published only after that day ends (00:00 UTC). So the latest date you can request is always yesterday in UTC. Asking for today returns `400 date_not_available`.

Note: India is UTC+05:30. Between 00:00 and 05:30 IST, "yesterday in UTC" is two calendar days ago for you.

## Endpoints

All endpoints are `GET`.

| Endpoint | Date param | Returns | Format |
|---|---|---|---|
| `/health` | no | Server status | JSON |
| `/v1/products` | no | Full product catalog | JSON |
| `/v1/customers` | required | Customers who signed up on that date | JSON |
| `/v1/orders` | required | Orders placed on that date, one row per order line | CSV |
| `/v1/transactions` | required | Payments and refunds on that date | NDJSON |

`date` format is strictly `YYYY-MM-DD`, for example `?date=2026-10-15`.

### GET /v1/products

The full catalog, every time. There is no date filter.

```json
{
  "count": 20,
  "products": [
    {
      "product_id": "P001",
      "name": "Cotton Crew T-Shirt",
      "category": "Apparel",
      "price": 499.0,
      "currency": "INR"
    }
  ]
}
```

### GET /v1/customers?date=YYYY-MM-DD

```json
{
  "date": "2026-10-15",
  "count": 7,
  "customers": [
    {
      "customer_id": "C00056",
      "first_name": "Arjun",
      "last_name": "Singh",
      "email": "arjun.singh56@example.com",
      "phone": "+91 9033721493",
      "signup_at": "2026-10-15T01:10:32Z",
      "address": {
        "line1": "242, MG Road",
        "city": "Mumbai",
        "state": "Maharashtra",
        "pincode": "400158"
      },
      "marketing_opt_in": false
    }
  ]
}
```

### GET /v1/orders?date=YYYY-MM-DD

CSV with a header row. An order with 3 items appears as 3 rows with the same `order_id`.

```
order_id,order_ts,customer_id,order_status,line_number,product_id,quantity,unit_price,line_total,currency
O20261015-001,2026-10-15T03:12:11Z,C00025,PLACED,1,P019,3,199.00,597.00,INR
O20261015-001,2026-10-15T03:12:11Z,C00025,PLACED,2,P016,1,799.00,799.00,INR
```

`order_status` is `PLACED` or `CANCELLED`.

### GET /v1/transactions?date=YYYY-MM-DD

NDJSON: one JSON object per line, not a JSON array.

```
{"transaction_id": "T9C6C154EA2CC", "order_id": "O20261015-002", "txn_ts": "2026-10-15T03:18:38Z", "type": "PAYMENT", "method": "UPI", "amount": 7142.0, "currency": "INR", "status": "SUCCESS", "failure_reason": null}
```

| Field | Values |
|---|---|
| `type` | `PAYMENT`, `REFUND` |
| `method` | `UPI`, `CARD`, `NETBANKING`, `WALLET` |
| `status` | `SUCCESS`, `FAILED` |
| `failure_reason` | `INSUFFICIENT_FUNDS`, `BANK_TIMEOUT`, `CARD_DECLINED`, or `null` |

`amount` is the full order total.

## Errors

Errors are always JSON:

```json
{"error": "date_not_available", "message": "..."}
```

| Status | error | When |
|---|---|---|
| 400 | `missing_parameter` | `date` not passed |
| 400 | `invalid_parameter` | Wrong format, not a real date, or passed twice |
| 400 | `date_not_available` | Date is today or in the future |
| 401 | `unauthorized` | Token missing or wrong |
| 404 | `not_found` | Unknown endpoint |
| 405 | `method_not_allowed` | Anything other than GET |

A date before 2026-10-01 is not an error. You get an empty result.
