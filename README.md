# Panjur

Web control for two roller shutters, running on a Raspberry Pi Zero 2 W.
Each shutter's wall switch has momentary UP/DOWN buttons that must be held
~20 s; this project holds them electronically via relays wired in parallel
with the switch contacts.

**Current status: TEST BUILD.** Relays are mocked (console prints), so the
full web UI and timing logic run with no hardware attached.

## Run (test mode)

```bash
python3 -m venv ~/panjur-env
~/panjur-env/bin/pip install flask
~/panjur-env/bin/python3 app.py
```

Open `http://erenpi.local:8000`. Short hold for demos:
`HOLD_SECONDS=3 ~/panjur-env/bin/python3 app.py`

## Config

Top of `app.py`:

- `SHUTTERS` — names and the BCM GPIO pins for each shutter's UP/DOWN relay
- `HOLD_OPEN` / `HOLD_CLOSE` — button-hold time in seconds (env-overridable)

## Going to real hardware

1. Verify the wall switch is **low-voltage control**, not direct mains
   switching (multimeter across the button terminals). If it's mains,
   stop and get a mains-rated relay + proper enclosure, or an electrician.
2. Wire each relay's NO/COM contacts in parallel with the matching button.
3. In `app.py`, `make_relay()`: delete the `MockRelay` line, uncomment the
   `gpiozero.OutputDevice` lines. That is the only code change.
4. `~/panjur-env/bin/pip install gpiozero`

## Auto-start on boot

```bash
sudo cp panjur.service /etc/systemd/system/
sudo systemctl enable --now panjur
```

Logs: `journalctl -u panjur -f`

## Notes / limitations

- **No position feedback.** If someone uses the wall button, the server's
  open/closed state drifts; the ⇅ button on each card re-syncs it without
  moving anything.
- **No authentication yet.** LAN use only. Do not expose via Cloudflare
  Tunnel or port forwarding until auth is added.

## Roadmap

- [ ] Real relay wiring (after switch-voltage check)
- [ ] Auth (password + session) before any internet exposure
- [ ] Cloudflare Tunnel for access away from home
- [ ] Optional: schedule (open at sunrise)
