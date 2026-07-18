"""
Panjur control - TEST BUILD (relays are mocked, no hardware needed)
===================================================================
Web control for two roller shutters. Each shutter has TWO relays, wired
in parallel with the wall switch's UP and DOWN buttons. A command holds
the matching "button" for the configured time, then releases.

Run:            python3 app.py            -> http://erenpi.local:8000
Quick demo:     HOLD_SECONDS=3 python3 app.py

When the relay boards arrive, swap MockRelay for gpiozero in make_relay().

SECURITY NOTE: no authentication yet. Fine on your home LAN.
Do NOT expose this via Cloudflare Tunnel / port forwarding until auth
is added.
"""

import os
import threading
import time

from flask import Flask, abort, jsonify, render_template_string

# ----------------------------------------------------------------------------
# Config - edit freely
# ----------------------------------------------------------------------------
HOLD_OPEN = float(os.environ.get("HOLD_SECONDS", os.environ.get("HOLD_OPEN", 22)))
HOLD_CLOSE = float(os.environ.get("HOLD_SECONDS", os.environ.get("HOLD_CLOSE", 22)))

SHUTTERS = [
    {"id": 1, "name": "Salon", "open_pin": 17, "close_pin": 22},
    {"id": 2, "name": "Yatak Odası", "open_pin": 27, "close_pin": 23},
]

# ----------------------------------------------------------------------------
# Relay layer - the ONLY part that changes when hardware arrives
# ----------------------------------------------------------------------------
class MockRelay:
    """Pretends to be a relay. Prints to the console instead of switching."""

    def __init__(self, pin, label):
        self.pin = pin
        self.label = label

    def on(self):
        print(f"[MOCK] GPIO{self.pin} ({self.label}): relay CLOSED (button held)")

    def off(self):
        print(f"[MOCK] GPIO{self.pin} ({self.label}): relay OPEN   (button released)")


def make_relay(pin, label):
    # --- REAL HARDWARE: delete the MockRelay line, uncomment the rest -------
    return MockRelay(pin, label)
    # from gpiozero import OutputDevice
    # return OutputDevice(pin, active_high=False, initial_value=False)
    # (most cheap relay boards are active-LOW: pin low = relay energised.
    #  If yours clicks at the wrong moment, set active_high=True.)


relays = {}
for s in SHUTTERS:
    relays[(s["id"], "open")] = make_relay(s["open_pin"], f"{s['name']} UP")
    relays[(s["id"], "close")] = make_relay(s["close_pin"], f"{s['name']} DOWN")

# ----------------------------------------------------------------------------
# State machine: closed -> opening -> open -> closing -> closed
# ----------------------------------------------------------------------------
BUSY = {"opening", "closing"}
state = {s["id"]: {"status": "closed", "ends_at": None} for s in SHUTTERS}
lock = threading.Lock()

app = Flask(__name__)


def run_cycle(sid, direction):
    """Hold the UP or DOWN 'button' for the configured time, then release.

    Interlock note: a shutter only enters this function from a non-busy
    state (enforced under the lock in the API handlers), so its two
    relays can never be energised at the same time.
    """
    hold = HOLD_OPEN if direction == "open" else HOLD_CLOSE
    relay = relays[(sid, direction)]
    relay.on()
    try:
        time.sleep(hold)
    finally:
        relay.off()  # always release, even if something goes wrong
    with lock:
        state[sid]["status"] = "open" if direction == "open" else "closed"
        state[sid]["ends_at"] = None


def _start(sid, direction):
    """Try to start a move. Returns (ok, error). Caller must NOT hold lock."""
    required = "closed" if direction == "open" else "open"
    hold = HOLD_OPEN if direction == "open" else HOLD_CLOSE
    with lock:
        st = state[sid]["status"]
        if st in BUSY:
            return False, "busy"
        if st != required:
            return False, f"already {st}"
        state[sid]["status"] = "opening" if direction == "open" else "closing"
        state[sid]["ends_at"] = time.time() + hold
    threading.Thread(target=run_cycle, args=(sid, direction), daemon=True).start()
    return True, None


@app.post("/api/move/<int:sid>/<direction>")
def api_move(sid, direction):
    if sid not in state or direction not in ("open", "close"):
        abort(404)
    ok, err = _start(sid, direction)
    if not ok:
        return jsonify(ok=False, error=err), 409
    return jsonify(ok=True)


@app.post("/api/move-all/<direction>")
def api_move_all(direction):
    if direction not in ("open", "close"):
        abort(404)
    started = [s["id"] for s in SHUTTERS if _start(s["id"], direction)[0]]
    return jsonify(ok=True, started=started)


@app.post("/api/sync/<int:sid>")
def api_sync(sid):
    """Fix state drift: if someone used the wall button, the server's idea of
    open/closed can be wrong (there is no position feedback). This toggles
    the stored state without moving anything."""
    if sid not in state:
        abort(404)
    with lock:
        if state[sid]["status"] in BUSY:
            return jsonify(ok=False, error="busy"), 409
        state[sid]["status"] = "open" if state[sid]["status"] == "closed" else "closed"
    return jsonify(ok=True, status=state[sid]["status"])


@app.get("/api/status")
def api_status():
    now = time.time()
    out = []
    with lock:
        for s in SHUTTERS:
            st = state[s["id"]]
            remaining = max(0.0, (st["ends_at"] or now) - now)
            out.append(
                {
                    "id": s["id"],
                    "name": s["name"],
                    "status": st["status"],
                    "remaining": round(remaining, 1),
                }
            )
    return jsonify(hold_open=HOLD_OPEN, hold_close=HOLD_CLOSE, shutters=out)


@app.get("/")
def index():
    return render_template_string(PAGE, shutters=SHUTTERS)


# ----------------------------------------------------------------------------
# Front-end (single page, no build step)
# ----------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panjur · erenpi</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@600;700&family=IBM+Plex+Mono:wght@500&display=swap" rel="stylesheet">
<style>
  :root{
    --housing:#1B1F26;      /* page: powder-coated shutter housing */
    --panel:#232933;
    --edge:#303845;
    --slat:#C9CFD6;         /* aluminium slat face */
    --slat-shadow:#9AA3AE;
    --ink:#E9ECF0;
    --ink-dim:#8B94A1;
    --amber:#E8A13D;        /* action / dawn light */
    --steel:#6E89A8;        /* close action */
    --open-green:#7FB069;
    --offline-red:#C75146;
  }
  *{box-sizing:border-box}
  body{
    margin:0;background:var(--housing);color:var(--ink);
    font-family:Archivo,system-ui,sans-serif;
    min-height:100svh;display:flex;justify-content:center;
  }
  .wrap{width:min(430px,100%);padding:20px 16px 32px}

  header{display:flex;align-items:baseline;gap:10px;margin-bottom:6px}
  h1{font-size:1.35rem;font-weight:700;letter-spacing:.14em;margin:0}
  .host{font-family:"IBM Plex Mono",monospace;font-size:.72rem;color:var(--ink-dim)}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--offline-red);
       margin-left:auto;align-self:center;transition:background .3s}
  .dot.live{background:var(--open-green)}

  .all-row{display:flex;gap:8px;margin:12px 0 18px}
  .all-btn{
    flex:1;padding:11px;border:1px solid var(--edge);
    border-radius:10px;background:transparent;color:var(--ink);
    font:600 .82rem Archivo,sans-serif;letter-spacing:.06em;cursor:pointer;
  }
  .all-btn:not(:disabled):active{background:var(--panel)}
  .all-btn:disabled{opacity:.4;cursor:default}

  .card{
    background:var(--panel);border:1px solid var(--edge);border-radius:14px;
    padding:14px 14px 16px;margin-bottom:16px;
  }
  .card-head{display:flex;align-items:baseline;margin-bottom:10px}
  h2{font-size:1.02rem;font-weight:600;margin:0}
  .state{
    margin-left:auto;font-family:"IBM Plex Mono",monospace;
    font-size:.7rem;letter-spacing:.08em;color:var(--ink-dim);
  }
  .state.open{color:var(--open-green)}
  .state.moving{color:var(--amber)}

  /* The window: dawn sky revealed as the shutter lifts */
  .window{
    position:relative;height:150px;border-radius:9px;overflow:hidden;
    border:1px solid var(--edge);
    background:
      radial-gradient(circle at 50% 92%, #FFE3A3 0 11%, transparent 42%),
      linear-gradient(180deg,#8FB8D9 0%,#CBB795 62%,#F5C97B 100%);
  }
  .shutter{
    position:absolute;inset:0 0 auto 0;
    height:calc(var(--cover,1)*100%);
    min-height:22px;                        /* rolled stack in the housing */
    background:repeating-linear-gradient(180deg,
      var(--slat) 0 9px, var(--slat-shadow) 9px 11px);
    border-bottom:4px solid #59616C;        /* bottom rail */
    transition:height 1s linear;
  }
  .shutter::before{                          /* housing lip */
    content:"";position:absolute;top:0;left:0;right:0;height:6px;
    background:#12151A;
  }
  .count{
    position:absolute;right:8px;bottom:8px;
    font-family:"IBM Plex Mono",monospace;font-size:.78rem;
    background:rgba(18,21,26,.72);color:var(--amber);
    padding:3px 8px;border-radius:6px;opacity:0;transition:opacity .3s;
  }
  .count.show{opacity:1}

  .row{display:flex;gap:8px;margin-top:12px}
  .move-btn{
    flex:1;padding:12px;border:0;border-radius:10px;
    font:700 .9rem Archivo,sans-serif;letter-spacing:.05em;cursor:pointer;
    color:#1B1F26;
  }
  .move-btn.up{background:var(--amber)}
  .move-btn.down{background:var(--steel)}
  .move-btn:not(:disabled):active{filter:brightness(1.08)}
  .move-btn:disabled{background:#4A5260;color:#8B94A1;cursor:default}
  .sync-btn{
    padding:12px 14px;border:1px solid var(--edge);border-radius:10px;
    background:transparent;color:var(--ink-dim);cursor:pointer;font-size:.9rem;
  }
  .sync-btn:disabled{opacity:.35;cursor:default}

  footer{
    margin-top:4px;text-align:center;
    font-family:"IBM Plex Mono",monospace;font-size:.66rem;color:var(--ink-dim);
  }
  :focus-visible{outline:2px solid var(--amber);outline-offset:2px}
  @media (prefers-reduced-motion:reduce){
    .shutter{transition:none}
  }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>PANJUR</h1><span class="host">· erenpi</span>
    <span class="dot" id="dot" title="connection"></span>
  </header>

  <div class="all-row">
    <button class="all-btn" id="all-open">OPEN BOTH</button>
    <button class="all-btn" id="all-close">CLOSE BOTH</button>
  </div>

  {% for s in shutters %}
  <article class="card" data-id="{{ s.id }}">
    <div class="card-head">
      <h2>{{ s.name }}</h2>
      <span class="state" data-role="state">CLOSED</span>
    </div>
    <div class="window">
      <div class="shutter" data-role="shutter" style="--cover:1"></div>
      <span class="count" data-role="count"></span>
    </div>
    <div class="row">
      <button class="move-btn up" data-role="open">OPEN</button>
      <button class="move-btn down" data-role="close">CLOSE</button>
      <button class="sync-btn" data-role="sync"
        title="State out of sync? (wall button was used) Toggle without moving">&#8645;</button>
    </div>
  </article>
  {% endfor %}

  <footer>test mode &mdash; relays simulated</footer>
</div>

<script>
let HOLD_OPEN = 22, HOLD_CLOSE = 22;
const cards = {};
document.querySelectorAll(".card").forEach(el => {
  const id = el.dataset.id;
  cards[id] = {
    shutter: el.querySelector('[data-role="shutter"]'),
    state:   el.querySelector('[data-role="state"]'),
    count:   el.querySelector('[data-role="count"]'),
    open:    el.querySelector('[data-role="open"]'),
    close:   el.querySelector('[data-role="close"]'),
    sync:    el.querySelector('[data-role="sync"]'),
  };
  cards[id].open.addEventListener("click",  () => act("move/" + id + "/open"));
  cards[id].close.addEventListener("click", () => act("move/" + id + "/close"));
  cards[id].sync.addEventListener("click",  () => act("sync/" + id));
});
document.getElementById("all-open").addEventListener("click",  () => act("move-all/open"));
document.getElementById("all-close").addEventListener("click", () => act("move-all/close"));

async function act(path){
  try{ await fetch("/api/" + path, {method:"POST"}); }catch(e){}
  poll();
}

function render(data){
  HOLD_OPEN = data.hold_open; HOLD_CLOSE = data.hold_close;
  let anyClosed = false, anyOpen = false;
  for(const s of data.shutters){
    const c = cards[s.id];
    if(!c) continue;
    const busy = (s.status === "opening" || s.status === "closing");
    if(s.status === "opening"){
      const p = 1 - (s.remaining / HOLD_OPEN);
      c.shutter.style.setProperty("--cover", Math.max(0.12, 1 - p));
      c.state.textContent = "OPENING";
    }else if(s.status === "closing"){
      const p = 1 - (s.remaining / HOLD_CLOSE);
      c.shutter.style.setProperty("--cover", Math.max(0.12, p));
      c.state.textContent = "CLOSING";
    }else if(s.status === "open"){
      c.shutter.style.setProperty("--cover", 0.12);
      c.state.textContent = "OPEN";
      anyOpen = true;
    }else{
      c.shutter.style.setProperty("--cover", 1);
      c.state.textContent = "CLOSED";
      anyClosed = true;
    }
    c.state.className = "state " +
      (busy ? "moving" : (s.status === "open" ? "open" : ""));
    if(busy){
      c.count.textContent = Math.ceil(s.remaining) + "s";
      c.count.classList.add("show");
    }else{
      c.count.classList.remove("show");
    }
    c.open.disabled  = busy || s.status !== "closed";
    c.close.disabled = busy || s.status !== "open";
    c.sync.disabled  = busy;
  }
  document.getElementById("all-open").disabled  = !anyClosed;
  document.getElementById("all-close").disabled = !anyOpen;
}

async function poll(){
  try{
    const r = await fetch("/api/status");
    render(await r.json());
    document.getElementById("dot").classList.add("live");
  }catch(e){
    document.getElementById("dot").classList.remove("live");
  }
}
poll();
setInterval(poll, 1000);
</script>
</body>
</html>"""


if __name__ == "__main__":
    print(f"Panjur test server - hold open {HOLD_OPEN}s / close {HOLD_CLOSE}s, relays MOCKED")
    app.run(host="0.0.0.0", port=8000)
