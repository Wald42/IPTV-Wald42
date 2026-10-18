#!/usr/bin/env python3
"""Refresh stream URLs for existing channels only; never add or reorder entries."""
from __future__ import annotations
import re
import urllib.request
from collections import defaultdict
from pathlib import Path

PLAYLIST = Path(__file__).with_name('IPTV.m3u')
SOURCES = [
    'https://ngrch.github.io/iptv/ru.m3u',
    'https://iptv-org.github.io/iptv/countries/kz.m3u',
    'https://raw.githubusercontent.com/substanc1/iptv-russia/main/streams/ru.m3u',
]
BLOCKED_HOSTS = ('cinerama.uz', 'wink.ru', 'ngenix.net')


def parse(text):
    lines = text.lstrip('\ufeff').splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith('#EXTINF')]
    if not starts:
        return lines, []
    return lines[:starts[0]], [lines[a:(starts[i+1] if i+1 < len(starts) else len(lines))] for i, a in enumerate(starts)]


def meta(block):
    line = block[0].strip()
    id_match = re.search(r'\btvg-id="([^"]+)"', line)
    name = line.split(',', 1)[-1].strip() if ',' in line else ''
    return (id_match.group(1).casefold() if id_match else '', name.casefold())


def url_index(block):
    for i in range(len(block) - 1, 0, -1):
        s = block[i].strip()
        if s.startswith(('https://', 'http://')):
            return i
    return None


def eligible(url):
    return url.startswith(('http://', 'https://')) and not any(host in url.casefold() for host in BLOCKED_HOSTS)


def main():
    header, blocks = parse(PLAYLIST.read_text(encoding='utf-8-sig'))
    by_id = defaultdict(list)
    by_name = defaultdict(list)
    for source in SOURCES:
        try:
            req = urllib.request.Request(source, headers={'User-Agent': 'IPTV-Wald42-Updater/1.0'})
            with urllib.request.urlopen(req, timeout=25) as response:
                content = response.read().decode('utf-8-sig', errors='replace')
            _, candidates = parse(content)
            for candidate in candidates:
                idx = url_index(candidate)
                if idx is None:
                    continue
                url = candidate[idx].strip()
                if not eligible(url):
                    continue
                channel_id, name = meta(candidate)
                if channel_id:
                    by_id[channel_id].append((name, url))
                if name:
                    by_name[name].append(url)
            print(f'Loaded {source}: {len(candidates)} streams')
        except Exception as exc:
            print(f'Source unavailable ({source}): {exc}')

    changed = 0
    for block in blocks:
        idx = url_index(block)
        if idx is None:
            continue
        old = block[idx].strip()
        channel_id, name = meta(block)
        choices = []
        # Prefer exact channel name and ID; only accept a unique new URL.
        if channel_id:
            choices = [url for candidate_name, url in by_id[channel_id] if candidate_name == name]
        if not choices and name:
            choices = by_name[name]
        unique = list(dict.fromkeys(choices))
        # Do not overwrite a known URL unless it disappears from matching sources
        # and exactly one alternative is available. This is not a live stream test.
        if old in unique or len(unique) != 1:
            continue
        new = unique[0]
        if new != old:
            block[idx] = new + ('\n' if block[idx].endswith('\n') else '')
            changed += 1
    if changed:
        PLAYLIST.write_text(''.join(header) + ''.join(''.join(b) for b in blocks), encoding='utf-8')
    print(f'Updated {changed} URL(s); kept {len(blocks)} channels in original order.')


if __name__ == '__main__':
    main()
