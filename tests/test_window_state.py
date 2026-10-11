import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
def load(name):
 spec=importlib.util.spec_from_file_location(name,ROOT/'patches'/f'{name}.py')
 m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
state=load('patch-window-state')
chrome=load('patch-mac-chrome')
MAIN='''const sendFullscreen = () => {
\t\t\tif (window.isDestroyed()) return;
\t\t\tconst fullscreen = window.isFullScreen() || (process.platform === "linux" && window.isMaximized());
\t\t\twindow.webContents.send(DESKTOP_IPC.windowFullscreen, fullscreen);
};'''

class WindowStateTests(unittest.TestCase):
 def test_runtime_transitions(self):
  subprocess.run(['node',str(ROOT/'tests/window-state-runtime.cjs')],input=state.STATE_JS,text=True,check=True,capture_output=True)
 def test_main_sends_independent_states(self):
  code=state.transform_main(MAIN)
  harness='''const assert=require('node:assert/strict'); const DESKTOP_IPC={windowFullscreen:'legacy'};
for (const [f,m] of [[false,false],[false,true],[true,false]]) {
const sent=[];const window={isDestroyed:()=>false,isFullScreen:()=>f,isMaximized:()=>m,webContents:{send:(...args)=>sent.push(args)}};
'''+code+'''
sendFullscreen();assert.equal(sent[0][1],f);assert.deepEqual(sent[1],['dsh-desktop:linux-window-state',{fullscreen:f,maximized:m}]);}
'''
  subprocess.run(['node','-e',harness],check=True,capture_output=True)
 def test_migration_idempotency_and_generated_syntax(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lib';root.mkdir();(root/'main.js').write_text(MAIN)
   preload=chrome.PRELOAD_FN.replace('__TITLEBAR_HEIGHT__','48').replace('__EXTRA_CSS__','')
   for name in ['preload-app.cjs','preload-welcome.cjs']:(root/name).write_text(preload)
   self.assertEqual(state.main(d),0)
   once={p.name:p.read_text() for p in root.iterdir()}
   self.assertEqual(state.main(d),0)
   self.assertEqual(once,{p.name:p.read_text() for p in root.iterdir()})
   for p in root.iterdir():subprocess.run(['node','--check',str(p)],check=True,capture_output=True)
 def test_unknown_payload_leaves_files_untouched(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lib';root.mkdir();(root/'main.js').write_text(MAIN)
   for name in ['preload-app.cjs','preload-welcome.cjs']:(root/name).write_text('// unsupported payload')
   before={p.name:p.read_text() for p in root.iterdir()}
   self.assertEqual(state.main(d),1)
   self.assertEqual(before,{p.name:p.read_text() for p in root.iterdir()})

 def test_fresh_chrome_and_legacy_upgrade_entrypoints(self):
  import ast
  tree=ast.parse((ROOT/'patches/patch-mac-chrome.py').read_text())
  old=[]
  for n in ast.walk(tree):
   if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='replace_once' and len(n.args)>1 and isinstance(n.args[1],ast.Constant):
    old.append(n.args[1].value)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d)/'lib';root.mkdir()
   source=''
   for text in old:
    if text.lstrip().startswith('backgroundColor:') or text.lstrip().startswith('...'):
     source+='const options'+str(len(source))+' = {\n'+text+'\n};\n'
    else: source+=text+'\n'
   source+='function registerIpc() {\n\tipcMain.handle(DESKTOP_IPC.directoryPick, async (event) => {});\n}\n'
   (root/'main.js').write_text(source)
   (root/'preload-app.cjs').write_text(chrome.MAIN_MARK_CALL)
   (root/'preload-welcome.cjs').write_text(chrome.WELCOME_MARK_CALL)
   for entry in ['patch-mac-chrome.py','upgrade-mac-chrome.py','upgrade-mac-chrome.py']:
    r=subprocess.run(['python3',str(ROOT/'patches'/entry),d],capture_output=True,text=True)
    self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   for name in ['preload-app.cjs','preload-welcome.cjs']:
    self.assertEqual((root/name).read_text().count('// dsh-window-state:v1'),1)
   self.assertNotIn('window.isFullScreen() ||',(root/'main.js').read_text())
   for p in root.iterdir():subprocess.run(['node','--check',str(p)],check=True,capture_output=True)
