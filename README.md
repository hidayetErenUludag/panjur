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

## Going to real hardware (servos)

The wall switch is mains-voltage (VIKO Karre jaluzi, 250V~), so the plan is
four SG90 servos physically pressing the UP/DOWN buttons — no contact with
mains wiring. Driven straight off Pi GPIO; no PCA9685 needed, because only
one servo ever moves at a time (the interlock guarantees it) so peak current
stays well within a 5V/3A supply.

### Wiring

- Each servo signal (orange) -> one GPIO pin: 17, 22, 27, 23 (see SHUTTERS).
- All servo power (red) -> a SEPARATE 5V/3A supply, NOT the Pi's 5V pin.
  Servo inrush dips the rail; keeping it off the Pi's rail avoids the
  brown-outs that corrupt the SD card.
- All grounds common: servo supply GND + each servo brown + a Pi GND pin.

### Software

```bash
~/panjur-env/bin/pip install gpiozero
# optional but recommended — steady jitter-free PWM:
sudo apt install pigpio && sudo systemctl enable --now pigpiod
```

Switch the driver from mock to servo by adding one line to `~/.panjur.env`:

```
PANJUR_DRIVER='servo'
```

(Leave it as `mock`, or omit it, to keep running without hardware.)

### Calibrate

Every servo + bracket needs its own press/rest angles:

```bash
sudo systemctl stop panjur          # free the pins
~/panjur-env/bin/python3 calibrate_servo.py
sudo systemctl start panjur
```

It walks through all four servos and saves `~/.panjur.servos.json`
(device-specific, gitignored). `app.py` reads it on start; servos with no
saved entry fall back to the defaults in `SERVO_DEFAULT_REST/PRESS`.

The servo detaches (stops driving) between moves, so it isn't buzzing or
drawing current while idle — the plastic arm holds the light button fine.

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
