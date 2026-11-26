"""Opt-in scripted update run against a local manifest; use only on a disposable extracted copy."""
import json
from pathlib import Path
import sys
import time
import traceback

from version import VERSION

POLL_MS = 200
TIMEOUT_SECONDS = 120


def schedule(app, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    results = []
    deadline = time.monotonic() + TIMEOUT_SECONDS
    progress_seen = []

    def record(name, passed, detail=''):
        results.append({'name': name, 'passed': bool(passed), 'detail': str(detail)})
        # The app closes itself once the installer starts, so keep the evidence current.
        (output / 'result.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

    def later(step):
        if time.monotonic() > deadline:
            record('timeout', False, app.update_status)
            return
        app.root.after(POLL_MS, step)

    def wait_for_offer():
        if app.update_check_job is not None:
            return later(wait_for_offer)
        offer = app.update_offer
        record('offer_found', offer is not None and offer['version'] != VERSION, app.update_status)
        if offer is None:
            return
        app.state.outfit = 'red'
        record('marker_save_written', app.save())
        app.popup()
        app.root.update()
        record('more_panel_shows_update', app.more.update_row.winfo_manager() == 'pack', app.update_text())
        record('download_started', app.start_update(), app.update_status)
        later(watch_download)

    def watch_download():
        job = app.update_install_job
        if job is not None:
            progress_seen.append(job.progress)
            if job.done and not job.error:
                record('download_verified', max(progress_seen) >= 1, max(progress_seen))
            return later(watch_download)
        record('install_handoff', False, app.update_status)

    def start():
        try:
            record('frozen_build', getattr(sys, 'frozen', False), sys.executable)
            record('updates_supported', app.updates_supported)
            record('check_started', app.request_update_check(), app.update_source)
            later(wait_for_offer)
        except Exception:
            record('exception', False, traceback.format_exc())

    app.root.after(1000, start)
