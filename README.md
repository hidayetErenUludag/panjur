# Panjur

Web control for two roller shutters, running on a Raspberry Pi Zero 2 W.
Each shutter's wall switch (VIKO jaluzi) has momentary UP/DOWN buttons that
must be held ~20 s; this project holds them electronically.

**Current status: TEST BUILD.** Outputs are mocked (console prints), so the
full web UI, auth, and timing logic run with no hardware attached.

## Setup

```bash
python3 -m venv ~/panjur-env
~/panjur-env/bin/pip install -r requirements.txt

# generate password + session secret (writes ~/.panjur.env, mode 600)
~/panjur-env/bin/python3 gen_secrets.py

sudo cp panjur.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now panjur
```

Open `http://erenpi.local:8000` and log in with the password you set.

Logs: `journalctl -u panjur -f`

## Authentication

- Single shared password, scrypt-hashed. The plaintext is never stored.
- Session cookie: HttpOnly, SameSite=Lax, 30-day lifetime.
- Every route is protected by default (`@app.before_request` gate), so a
  new endpoint cannot be accidentally left open.
- 5 wrong passwords from one IP = 5-minute lockout.
- Secrets live in `~/.panjur.env`, outside the repo and gitignored.
  The app refuses to start if they are missing.

Change the password: re-run `gen_secrets.py`, then
`sudo systemctl restart panjur`. All existing sessions are invalidated.

## Config

Top of `app.py`:

- `SHUTTERS` — names and the GPIO pins for each shutter's UP/DOWN output
- `HOLD_OPEN` / `HOLD_CLOSE` — button-hold time in seconds (env-overridable)
- `MAX_ATTEMPTS` / `LOCKOUT_SECONDS` / `SESSION_DAYS` — auth tuning

In `~/.panjur.env`:

- `PANJUR_HTTPS` — set to `1` only once the app is reachable exclusively
  over HTTPS (i.e. behind the Cloudflare Tunnel). Setting it to 1 while
  still on plain-HTTP LAN will make login silently fail, because the
  browser will refuse to send a Secure cookie over HTTP.

## Going to real hardware

The wall switch is mains-voltage (VIKO Karre jaluzi, 250V~), so the plan is
servos physically pressing the buttons — no contact with mains wiring.

In `app.py`, `make_output()` is the only function that changes:

1. `~/panjur-env/bin/pip install adafruit-circuitpython-servokit`
2. Wire PCA9685 to the Pi (SDA/SCL/3V3/GND), servos to channels 0-3,
   separate 5V supply for the servo rail, grounds common.
3. Replace `MockOutput` with a class whose `on()` sets the press angle and
   `off()` returns to the rest angle, then delete the `return MockOutput(...)`.

Calibrate press/rest angles per servo before mounting the bracket.

## Notes / limitations

- **No position feedback.** If someone uses the wall button, the server's
  open/closed state drifts; the ⇅ button on each card re-syncs it without
  moving anything.
- **One gunicorn worker on purpose.** Shutter state and the login rate
  limiter live in process memory; multiple workers would each hold their
  own copy.

## Roadmap

- [x] Auth (password + session)
- [ ] Servo hardware + bracket
- [ ] Cloudflare Tunnel for access away from home (then set `PANJUR_HTTPS=1`)
- [ ] Optional: schedule (open at sunrise)
