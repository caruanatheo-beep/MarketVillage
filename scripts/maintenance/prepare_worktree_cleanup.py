"""Back up unique changes before proposing inactive Git worktrees for removal."""
import sys,os,json,subprocess,re,zipfile,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root),str(root/'.venv/Lib/site-packages')]
from dotenv import load_dotenv
load_dotenv(root/'.env')
from internships_project.state_store import USER_DB_PATH
import sqlite3
area=root/'.city-worktrees';report=root/'artifacts/storage-cleanup';backups=report/'recovery';backups.mkdir(parents=True,exist_ok=True)
def run(cwd,*args):
    result=subprocess.run(['git','-c','core.longpaths=true','-c','core.hooksPath=NUL',*args],cwd=cwd,capture_output=True,timeout=90)
    if result.returncode:raise RuntimeError('Git check failed')
    return result.stdout
with sqlite3.connect(USER_DB_PATH.resolve().as_uri()+'?mode=ro',uri=True) as db:
    tasks={row[0]:row[1] for row in db.execute('SELECT id,status FROM city_tasks')}
active={identity for identity,status in tasks.items() if status in {'queued','running','waiting_approval'}}
listing=run(root,'worktree','list','--porcelain').decode('utf-8').strip().split('\n\n')
worktrees=[]
for block in listing:
    fields=dict(line.split(' ',1) for line in block.splitlines() if ' ' in line)
    path=Path(fields.get('worktree','')).resolve()
    if path.parent!=area.resolve() or not re.fullmatch('[a-f0-9]{32}',path.name):continue
    if path.name in active:continue
    if tasks.get(path.name) not in {'completed','failed','cancelled'}:continue
    if any((path/name).exists() for name in ('.env','.env.local','.env.production')):continue
    worktrees.append((path,fields))
def backup(item):
    path,fields=item
    try:
        assert path.resolve().parent==area.resolve() and path.is_dir() and not path.is_symlink() and not path.is_junction()
        assert (path/'.git').is_file(), 'Missing worktree Git pointer'
        assert run(path,'rev-parse','HEAD').decode().strip()==fields.get('HEAD'), 'Changed worktree HEAD'
        modified=[p.decode('utf-8') for p in run(path,'diff','--name-only','-z','--diff-filter=AMRT','HEAD').split(b'\0') if p]
        deleted=[p.decode('utf-8') for p in run(path,'diff','--name-only','-z','--diff-filter=D','HEAD').split(b'\0') if p]
        added=[p.decode('utf-8') for p in run(path,'ls-files','--others','--exclude-standard','-z').split(b'\0') if p]
        patch=run(path,'diff','--binary','--no-ext-diff','--no-textconv','HEAD','--',*modified) if modified else b''
        archive=backups/(path.name+'.zip')
        temporary=archive.with_suffix('.tmp')
        manifest={'task_id':path.name,'status':tasks[path.name],'branch':fields.get('branch'),
                  'head':fields.get('HEAD'),'modified':modified,'deleted':deleted,'untracked':[]}
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
            zipped.writestr('working-tree.patch',patch)
            for name in added:
                item=path/name
                if not item.resolve().is_relative_to(path.resolve()) or item.is_symlink() or item.is_junction():
                    raise RuntimeError('Unsafe backup path')
                if item.is_file():
                    zipped.write(item,'untracked/'+name);manifest['untracked'].append(name)
            baseline=path.with_suffix('.baseline.json')
            if baseline.is_file():zipped.write(baseline,'metadata/baseline.json')
            zipped.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
        with zipfile.ZipFile(temporary) as check:
            assert check.testzip() is None
        temporary.replace(archive)
        return {'path':str(path),'task_id':path.name,'backup':str(archive),'head':fields.get('HEAD'),
                'branch':fields.get('branch'),'status':tasks[path.name],'backup_bytes':archive.stat().st_size,'files_preserved':len(modified)+len(manifest['untracked'])}
    except (OSError,RuntimeError,subprocess.SubprocessError,AssertionError) as exc:
        return {'task_id':path.name,'skip':type(exc).__name__}
results=list(ThreadPoolExecutor(max_workers=3).map(backup,worktrees))
plan={'root':str(root.resolve()),'database':str(USER_DB_PATH.resolve()),'protected_active':sorted(active),
      'worktrees':[row for row in results if 'path' in row],'skipped':[row for row in results if 'skip' in row]}
(report/'worktree-cleanup-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'backed_up':len(plan['worktrees']),'skipped':len(plan['skipped']),
 'protected_active_tasks':len(active),'backup_mib':round(sum(row['backup_bytes'] for row in plan['worktrees'])/2**20,2),
 'unique_changed_files_preserved':sum(row['files_preserved'] for row in plan['worktrees'])}),flush=True)
