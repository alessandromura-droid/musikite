"""
Audio output settings and check, for Jupyter and the command line
(the main window has the same in Settings > Audio…).

    audio_settings()                              current settings + output devices
    audio_settings(device='External Headphones', period_size=128)
    audio_test()                                  a note and 4 clicks; driver, device, latency
    audio_panel()                                 same controls as widgets in a notebook

Settings are saved in ~/.musikite/users/<user>/settings.json (key 'audio'):
driver (coreaudio on macOS), device (None = system default), period_size and
periods (buffer: latency = period_size * periods / sample_rate), sample_rate, gain.
"""
from . import realtime

BUFFERS = (64, 128, 256, 512, 1024)
RATES = (44100, 48000)


def audio_devices():
    return realtime.output_devices()


def audio_settings(**changes):
    """Without arguments: current settings. With keywords: change and save them."""
    cfg = realtime.set_audio_config(**changes) if changes else realtime.audio_config()
    return dict(cfg, available_devices=audio_devices())


def audio_test(sf2=None):
    """Play a note and four clicks; returns what is active (or raises with the reason)."""
    info = realtime.test(sf2)
    print(f"driver {info['driver']}, device {info['device'] or 'default'}, "
          f"buffer {info['period_size']} x {info['periods']} at {info['sample_rate']} Hz "
          f"-> latency {info['latency_ms']} ms" + (f"  [{info['error']}]" if info["error"] else ""))
    return info


def audio_panel():
    """ipywidgets panel: driver, device, buffer, sample rate, gain, Save + Test."""
    try:
        import ipywidgets as W
        from IPython.display import display
    except ImportError:
        print("ipywidgets missing: %pip install ipywidgets (or use audio_settings / audio_test)")
        return None
    cfg = realtime.audio_config()
    devs = ["(default)"] + audio_devices()
    drivers = ["(default)"] + list(realtime.DRIVERS)
    driver = W.Dropdown(options=drivers, value=cfg["driver"] or "(default)", description="Driver")
    device = W.Dropdown(options=devs if (cfg["device"] in devs or not cfg["device"]) else devs + [cfg["device"]],
                        value=cfg["device"] or "(default)", description="Device")
    period = W.Dropdown(options=BUFFERS, value=int(cfg["period_size"]), description="Buffer")
    periods = W.BoundedIntText(value=int(cfg["periods"]), min=2, max=16, description="Periods")
    rate = W.Dropdown(options=RATES, value=int(cfg["sample_rate"]), description="Rate (Hz)")
    gain = W.FloatSlider(value=float(cfg["gain"]), min=0.05, max=2.0, step=0.05, description="Gain")
    save = W.Button(description="Save")
    test = W.Button(description="Test", button_style="info")
    out = W.Output()

    def values():
        return dict(driver=None if driver.value == "(default)" else driver.value,
                    device=None if device.value == "(default)" else device.value,
                    period_size=int(period.value), periods=int(periods.value),
                    sample_rate=int(rate.value), gain=float(gain.value))

    def on_save(_=None):
        with out:
            out.clear_output()
            realtime.set_audio_config(**values())
            print("saved:", values())

    def on_test(_):
        on_save()
        with out:
            try:
                audio_test()
            except Exception as e:
                print("audio did not start:", e)

    save.on_click(on_save)
    test.on_click(on_test)
    box = W.VBox([driver, device, period, periods, rate, gain, W.HBox([save, test]), out])
    display(box)
    return box
