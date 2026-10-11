#!/usr/bin/env python3
"""Upgrade Linux window state without changing the window material.

Usage: patch-window-state.py <resources/app directory>
"""
from pathlib import Path
import re
import sys

STATE_JS = r'''
	// dsh-window-state:v1
	// Geometry is ambiguous (ordinary maximized windows can fill the screen).
	// Enable only for a compositor/backend whose native state reporting is broken.
	const tilingFullscreenFallback = process.env.DSH_TILING_FULLSCREEN_FALLBACK === "1";
	let nativeFullscreen = false;
	let nativeMaximized = false;
	let stateRevision = 0;
	const syncTilingFullscreen = () => {
		const root = document.documentElement;
		if (root === null) return;
		const inferred = tilingFullscreenFallback && !nativeMaximized
			&& window.innerWidth >= window.screen.availWidth - 2
			&& window.innerHeight >= window.screen.availHeight - 2;
		root.dataset.dshWindowFullscreen = String(nativeFullscreen);
		root.dataset.dshWindowMaximized = String(nativeMaximized);
		root.dataset.dshTilingFullscreen = String(inferred);
		if (nativeFullscreen || inferred) root.dataset.fullscreen = "true";
		else delete root.dataset.fullscreen;
	};
	const acceptWindowState = (state) => {
		if (!state || typeof state.fullscreen !== "boolean" || typeof state.maximized !== "boolean") return;
		nativeFullscreen = state.fullscreen;
		nativeMaximized = state.maximized;
		syncTilingFullscreen();
	};
	electron.ipcRenderer.on("dsh-desktop:linux-window-state", (_event, state) => {
		stateRevision++;
		acceptWindowState(state);
	});
	// Initial state for windows loaded after a transition; ignore a stale reply
	// if a newer transition arrives while this request is in flight.
	const initialRevision = stateRevision;
	electron.ipcRenderer.invoke(CHANNEL, "state").then((state) => {
		if (stateRevision === initialRevision) acceptWindowState(state);
	}).catch(() => {});
	syncTilingFullscreen();
	window.addEventListener("resize", syncTilingFullscreen);
	document.addEventListener("DOMContentLoaded", syncTilingFullscreen);
'''


def transform_preload(src):
    if '// dsh-window-state:v1' in src:
        return src
    pattern = r'\t/\*\*\n\t \* Tiling compositors.*?\tconst syncTilingFullscreen = \(\) => \{.*?\n\t\};'
    src, count = re.subn(pattern, lambda _: STATE_JS, src, count=1, flags=re.S)
    if count != 1:
        raise ValueError('Cannot locate the existing tiling fullscreen detector')
    # The old initialization lives after syncChromeStyle, not next to its declaration.
    old = '\tsyncTilingFullscreen();\n\twindow.addEventListener("resize", syncTilingFullscreen);'
    # Remove the last occurrence: the first belongs to STATE_JS.
    pos = src.rfind(old)
    if pos < 0:
        raise ValueError('Cannot locate the tiling detector initialization')
    return src[:pos] + src[pos:].replace(old, '', 1)


def transform_main(src):
    old = 'window.isFullScreen() || (process.platform === "linux" && window.isMaximized())'
    if old in src:
        src = src.replace(old, 'window.isFullScreen()')
    src = src.replace('if (window.isMaximized() || fills)',
                      'if (window.isMaximized() || (process.env.DSH_TILING_FULLSCREEN_FALLBACK === "1" && fills))')
    anchor = '\t\t\twindow.webContents.send(DESKTOP_IPC.windowFullscreen, fullscreen);'
    state_send = '''\n\t\t\tif (process.platform === "linux") window.webContents.send("dsh-desktop:linux-window-state", {
\t\t\t\tfullscreen, maximized: window.isMaximized()
\t\t\t});'''
    if 'window.webContents.send("dsh-desktop:linux-window-state"' not in src:
        if src.count(anchor) != 1:
            raise ValueError('Cannot locate the fullscreen state sender')
        src = src.replace(anchor, anchor + state_send, 1)
    src = src.replace('''\t// which only this channel sets. Tiling compositors treat a "fullscreen" window
\t// as merely maximised, so maximised also counts as fullscreen on Linux.''',
                      '''\t// Maximum size is not fullscreen: send the native states separately.''')
    return src


def main(app_dir):
    root = Path(app_dir) / 'lib'
    try:
        pending = {root/'main.js': transform_main((root/'main.js').read_text())}
        for name in ['preload-app.cjs', 'preload-welcome.cjs']:
            p = root/name
            pending[p] = transform_preload(p.read_text())
    except (OSError, ValueError) as e:
        print(f'Window state patch failed: {e}', file=sys.stderr)
        return 1
    for p, text in pending.items():
        if p.read_text() != text:
            p.write_text(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1]))
