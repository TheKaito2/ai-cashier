"""The owner's dashboard: a read-mostly web view on the till's database.

Version 4 also served a second, browser-based till that pushed camera frames
over a websocket, and kept its own in-memory cart that the Qt till talked to
over HTTP.  The architecture review (docs/research/09, D1-D3) removed both: the
till owns the camera, the scale and the cart and writes SQLite directly; this
server exists so the shopkeeper can open inventory and takings on a phone.

Runs on a thread inside the till process (app.py).  Bound to the loopback
interface unless `--lan` is given, in which case every write needs the
dashboard PIN from the shop settings.
"""

from __future__ import annotations

import logging
from datetime import datetime
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

import paths
from server.services import checkout, receipt
from server.services.checkout import CheckoutError
from server.services.database import Database
from server.services.restrictions import customer_visible

# the static pages ship with the code (paths.py): the checkout in development,
# the bundle directory in an installed build
STATIC = paths.STATIC

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

db = Database()

app = FastAPI(title="AI Cashier dashboard", version=paths.version())
#: set by app.py --lan.  Off the loopback interface, writes need the PIN.
app.state.lan = False


def require_pin(request: Request) -> None:
    """Writes from the LAN must carry the shop's dashboard PIN.

    On the loopback interface (the default) nothing is required: only the till
    itself can reach the server.  With `--lan` and no PIN configured every
    write is refused, which is the safe direction to fail in.
    """
    if not app.state.lan:
        return
    pin = db.get_settings().get("dashboard_pin") or ""
    if not pin or request.headers.get("X-Dashboard-Pin") != pin:
        raise HTTPException(status_code=401, detail="dashboard PIN required")


def _refused(e: CheckoutError) -> JSONResponse:
    return JSONResponse(status_code=e.status, content=e.payload)


# --------------------------------------------------------------------- money

@app.post("/api/checkout")
async def api_checkout(body: dict, _=Depends(require_pin)):
    """`{"items": [{"product_id", "quantity"}], "staff_confirmed": bool}` -> pending payment."""
    try:
        return checkout.create_payment(db, body.get("items") or [], bool(body.get("staff_confirmed")))
    except CheckoutError as e:
        return _refused(e)


@app.post("/api/confirm-payment/{payment_id}")
async def api_confirm_payment(payment_id: str, body: dict = None, _=Depends(require_pin)):
    try:
        return checkout.confirm_payment(db, payment_id, (body or {}).get("slip"))
    except CheckoutError as e:
        return _refused(e)


@app.get("/api/receipt/{sale_id}")
async def get_receipt(sale_id: str):
    sale = db.get_sale(sale_id)
    if not sale:
        return JSONResponse(status_code=404, content={"error": "Sale not found"})
    return PlainTextResponse(receipt.render(sale, db.get_settings()))


# ------------------------------------------------------------------ products

@app.get("/api/products")
async def get_products(staff: bool = True):
    """`staff=false` is the customer-facing list: tobacco may not be displayed."""
    products = db.get_products()
    return products if staff else [p for p in products if customer_visible(p.get("restricted"))]


@app.patch("/api/products/{product_id}/restriction")
async def set_restriction(product_id: str, body: dict, _=Depends(require_pin)):
    try:
        ok = db.set_restriction(product_id, body.get("restricted", "none"))
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    if not ok:
        return JSONResponse(status_code=404, content={"error": "Product not found"})
    return db.get_product(product_id)


@app.post("/api/restock/{product_id}")
async def restock_product(product_id: str, quantity: int, _=Depends(require_pin)):
    if db.update_stock(product_id, quantity, operation="add"):
        return {"message": "Product restocked successfully"}
    return JSONResponse(status_code=400, content={"error": "Failed to restock"})


# ------------------------------------------------------------------- records

@app.get("/api/events")
async def get_events(kind: str = None, limit: int = 200):
    """The deployment log: enrolments, abstentions, overrides, basket checks."""
    return db.get_events(kind, limit)


@app.post("/api/events")
async def post_event(body: dict, _=Depends(require_pin)):
    try:
        return {"id": db.log_event(body.get("kind", ""), body.get("payload") or {})}
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})


@app.get("/api/sales")
async def get_sales(limit: int = 50):
    return db.get_sales(limit)


@app.get("/api/analytics")
async def get_analytics():
    return db.get_analytics()


@app.get("/api/theme")
async def get_theme():
    return {"theme": db.get_theme()}


@app.post("/api/theme")
async def set_theme(theme_data: dict):
    theme = theme_data.get("theme", "light")
    if theme in ("light", "dark"):
        db.set_theme(theme)
        return {"theme": theme}
    return JSONResponse(status_code=400, content={"error": "Invalid theme"})


@app.get("/api/system-status")
async def system_status():
    return {"status": "online", "timestamp": datetime.now().isoformat(),
            "lan": app.state.lan, "products": len(db.get_products())}


# --------------------------------------------------------------------- pages

PAGES = {
    "/": "index.html",
    "/inventory": "inventory.html",
    "/admin": "admin.html",
    "/monitor": "monitor.html",
}


def _page(name: str):
    async def handler():
        return FileResponse(STATIC / name)
    return handler


for _path, _file in PAGES.items():
    app.get(_path, include_in_schema=False)(_page(_file))

app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")
# the /models mount is gone: it published the trained .pt weights over HTTP
