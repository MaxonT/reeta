"""Browser smoke test of the full loop: Lecture -> Notebook -> Exam -> Red pen (+clip) -> Office hours -> retake -> Report.

Needs the backend (SPEECH_PROVIDER=browser) on :8000 and `npm run dev` on :5173.
    pip install playwright && python scripts/e2e_smoke.py [out_dir]
Uses session "demo" and resets it first.
"""
import json, math, struct, sys, tempfile, wave
from pathlib import Path
from playwright.sync_api import sync_playwright

SP = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
B = 'http://localhost:5173'

# 4 second tone as stand in Lecture audio
with wave.open(f'{SP}/lec.wav', 'w') as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000)
    w.writeframes(b''.join(struct.pack('<h', int(8000 * math.sin(2 * math.pi * 440 * i / 16000))) for i in range(64000)))

with sync_playwright() as p:
    br = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required'])
    pg = br.new_page(viewport={'width': 1400, 'height': 1000})
    errors = []
    pg.on('console', lambda m: m.type == 'error' and errors.append(m.text))
    pg.on('pageerror', lambda e: errors.append(str(e)))
    pg.goto(B); pg.wait_for_timeout(800)
    pg.click('button.reset'); pg.wait_for_timeout(500)

    # Lecture 1 "spoken": real audio + browser transcript with timestamps (via API, as the recorder would send)
    r = pg.request.post(B + '/api/lectures/audio', headers={'X-Session-Id': 'demo'}, multipart={
        'audio': {'name': 'lecture.wav', 'mimeType': 'audio/wav', 'buffer': open(f'{SP}/lec.wav', 'rb').read()},
        'kind': 'lecture',
        'transcript': json.dumps([
            {'text': 'A recursive function is a function that calls itself.', 'start_ms': 0, 'end_ms': 1000},
            {'text': 'Recursion stops by itself when it is done.', 'start_ms': 1000, 'end_ms': 2000},
            {'text': 'All the calls share the same variables.', 'start_ms': 2000, 'end_ms': 3000},
            {'text': 'Let us take a short break.', 'start_ms': 3000, 'end_ms': 4000}])})
    lec = r.json(); print('proposed', [(e['concept_id'], e['status']) for e in lec['proposed_entries']])

    # Lecture 2 through the UI: typed fallback + confirm screen
    pg.click('text=Type instead')
    pg.fill('textarea', 'Each call works on a smaller problem, like n minus 1.')
    pg.click('text=Teach this'); pg.wait_for_selector('text=Write it in the Notebook')
    pg.screenshot(path=f'{SP}/1_confirm.png')
    pg.click('text=Write it in the Notebook'); pg.wait_for_timeout(600)
    pg.request.post(B + f"/api/lectures/{lec['lecture']['id']}/confirm", headers={'X-Session-Id': 'demo'},
                    data={'entry_ids': [e['id'] for e in lec['proposed_entries']]})
    pg.screenshot(path=f'{SP}/2_lecture.png')

    pg.click('nav >> text=Notebook'); pg.wait_for_timeout(300); pg.click('nav >> text=Lecture hall'); pg.wait_for_timeout(200)
    pg.click('text=Peek at my Notebook'); pg.wait_for_timeout(900)
    pg.reload(); pg.wait_for_timeout(800); pg.click('nav >> text=Notebook'); pg.wait_for_timeout(900)
    pg.screenshot(path=f'{SP}/3_notebook.png')

    pg.click('text=Give the Exam'); pg.click('text=Hand out the Exam'); pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{SP}/4_exam_mid.png')
    pg.wait_for_selector('text=Grade it with the red pen', timeout=20000)
    pg.screenshot(path=f'{SP}/5_exam_done.png')
    pg.click('text=Grade it with the red pen'); pg.wait_for_timeout(600)
    # q2 is a misconception -> click it, expect highlighted sentence + clip playing
    pg.click('.q.clickable >> nth=1'); pg.wait_for_timeout(400)
    print('hl sentences:', pg.locator('.sent.hl').all_inner_texts())
    print('hl nodes:', pg.locator('.cnode.hl .cnode-label').all_inner_texts())
    print('playing:', pg.locator('.sent.playing').count())
    pg.screenshot(path=f'{SP}/6_grading.png')
    pg.click('.q.clickable >> nth=7'); pg.wait_for_timeout(400)
    print('q8 note:', pg.locator('.red-note').inner_text())

    pg.click('text=Go to Office hours'); pg.wait_for_timeout(800)
    pg.screenshot(path=f'{SP}/7_office.png')
    pg.click('text=Type instead')
    pg.fill('textarea', 'Correction: recursion does not stop by itself, it needs a base case. '
            'Each call has its own stack frame with its own local variables. '
            'The return value passes back up to the caller.')
    pg.click('text=Teach this'); pg.wait_for_selector('text=Write it in the Notebook')
    pg.click('text=Write it in the Notebook'); pg.wait_for_timeout(900)
    pg.screenshot(path=f'{SP}/8_office_fixed.png')
    pg.click('button:has-text("Retake the Exam")'); pg.wait_for_selector('text=Grade it with the red pen', timeout=20000)
    pg.screenshot(path=f'{SP}/9_retake.png')
    pg.click('text=Grade it with the red pen'); pg.wait_for_timeout(500)
    print('score:', pg.locator('.score').inner_text())
    pg.click('text=See the Report card'); pg.wait_for_timeout(1500)
    pg.screenshot(path=f'{SP}/10_report.png', full_page=True)
    print('errors:', errors)
    assert pg.locator('.grade').count() == 5 and not errors
    print('screenshots in', SP)
    br.close()
