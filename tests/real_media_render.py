"""Bounded local Remotion proof using synthetic inputs; never calls providers.

Run explicitly in CI; ordinary unit discovery does not launch a browser.
This proves render/audio/signature/cache behavior, not production publication.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run(output: Path) -> dict:
    output = output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    os.environ['KESHER_STATE_DIR'] = str(output)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import kesher_daily_pipeline as core, kesher_short_pipeline_v4 as short
    from scripts.kesher_e2e_delivery_guard import _signature_verified
    source = core.source_metadata({'id': 'synthetic-render-proof', 'date': '2026-09-17',
        'title': 'בדיקה מקומית של חתימה וקול', 'category': 'זוגיות',
        'excerpt': 'מקור סינתטי מקומי לבדיקת שמירת משך וחתימה.',
        'content': '<p>זוהי בדיקה מקומית בלבד של תצוגת וידאו ואודיו.</p>'})
    result = {'environment': 'synthetic', 'scope': 'render contract only; no provider or public delivery proof', 'renders': []}
    for kind, dimensions, duration, engine in [('overview', '640x360', 4, core), ('short', '360x640', 2, short)]:
        raw = output / f'synthetic-{kind}.mp4'
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'lavfi', '-i',
            f'testsrc2=size={dimensions}:rate=30', '-f', 'lavfi', '-i',
            'aevalsrc=0.2*sin(2*PI*(220*t+80*t*t)):s=48000', '-t', str(duration),
            '-c:v', 'libx264', '-c:a', 'aac', str(raw)], check=True, timeout=60)
        item = engine.new_item(source)
        item.update(id=f'synthetic-{kind}', raw_mp4=raw.name, raw_sha256=core.sha256_file(raw),
                    source_id=f'synthetic-{kind}-source', task_id=f'synthetic-{kind}-task',
                    artifact_id=f'synthetic-{kind}-artifact', fresh_generation_attempt=1)
        final = engine.render_remotion_video(raw, item)
        if not _signature_verified(item) or abs(core.ffprobe(final)['duration'] - duration) > 0.15:
            raise RuntimeError('Synthetic render changed duration or failed signature proof')
        if kind == 'overview':
            cached = core.remotion_cache_is_reusable(item, final)
        else:
            cached = short._short_render_cache_reusable(raw, final, item, item['signature_sha256'])
            if short.short_technical_failures(item['media'], item=item):
                raise RuntimeError('Shorter native timeline failed its technical contract')
        if not cached:
            raise RuntimeError('Current complete render cannot be reused with exact provenance')
        def pcm(path):
            return subprocess.run(['ffmpeg', '-v', 'error', '-i', str(path), '-vn', '-ac', '1', '-ar', '16000',
                '-f', 's16le', '-'], capture_output=True, check=True, timeout=60).stdout
        if pcm(raw) != pcm(final):
            raise RuntimeError('Complete decoded source audio changed during rendering')
        evidence = {'kind': kind, 'duration': item['media']['duration'],
                    'signature_duration': item['signature_duration_seconds'], 'final_sha256': item['final_sha256'],
                    'signature_verified': True, 'cache_verified': True, 'decoded_audio_identical': True,
                    'audio_packet_sha256': item['audio_provenance']['raw_audio_sha256']}
        result['renders'].append(evidence)
        (output / f'{kind}-evidence.json').write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding='utf-8')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-ss', str(duration - .25),
            '-i', str(final), '-frames:v', '1', str(output / f'{kind}-last-frame.png')], check=True, timeout=60)
        print(json.dumps(evidence), flush=True)
    (output / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)
