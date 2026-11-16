"""Fail closed if a candidate became active or changed after its verified backup."""
import sys,json,sqlite3,subprocess,zipfile,hashlib,os,zlib
from pathlib import Path
root=Path(__file__).resolve().parents[2]
def report_error(kind,value,traceback):
    print(json.dumps({'safe':False,'reason':str(value) if isinstance(value,AssertionError) else kind.__name__}))
sys.excepthook=report_error
plan=json.loads((root/'artifacts/storage-cleanup/worktree-cleanup-plan.json').read_text(encoding='utf-8'))
identity=sys.argv[1]
row=next(item for item in plan['worktrees'] if item['task_id']==identity)
path=Path(row['path']).resolve()
assert (root/'.city-worktrees').resolve().parent==root.resolve(),'Worktree area redirects outside workspace'
assert path.parent==(root/'.city-worktrees').resolve() and path.name==identity
backup_path=Path(row['backup']).resolve()
assert backup_path.parent==(root/'artifacts/storage-cleanup/recovery').resolve() and backup_path.name==identity+'.zip','Unsafe backup path'
with os.scandir(path) as access_check:next(access_check,None)
with sqlite3.connect(Path(plan['database']).as_uri()+'?mode=ro',uri=True,timeout=3) as db:
    status=db.execute('SELECT status FROM city_tasks WHERE id=?',(identity,)).fetchone()
assert status and status[0] in ('completed','failed','cancelled'),'Task is active'
def run(*args):
    result=subprocess.run(['git','-c','core.longpaths=true','-c','core.hooksPath=NUL','-c','core.fsmonitor=false','-c','safe.directory='+str(path),*args],cwd=path,capture_output=True,timeout=45)
    assert result.returncode==0,'Git validation failed'
    return result.stdout
orphan=not (path/'.git').is_file()
assert not any((path/name).exists() for name in ('.env','.env.local','.env.production')),'Private configuration present'
if not orphan:assert run('rev-parse','HEAD').decode().strip()==row['head'],'Branch changed'
else:assert '--allow-orphan' in sys.argv,'Orphan needs a remaining-files backup'
preserved=subprocess.run(['git','-c','core.hooksPath=NUL','-c','core.fsmonitor=false','-c','safe.directory='+str(root),'-C',str(root),'update-ref','refs/marketdesk/cleanup/'+identity,row['head']],capture_output=True)
assert preserved.returncode==0,'Cannot preserve Git revision'
with zipfile.ZipFile(backup_path) as backup:
    manifest=json.loads(backup.read('manifest.json'))
    assert manifest['task_id']==identity and manifest['head']==row['head']
    for name,arguments in ([] if orphan else [('modified',('diff','--name-only','-z','--diff-filter=AMRT','HEAD')),
                           ('deleted',('diff','--name-only','-z','--diff-filter=D','HEAD')),
                           ('untracked',('ls-files','--others','--exclude-standard','-z'))]):
        names=[value.decode() for value in run(*arguments).split(b'\0') if value]
        assert set(names)==set(manifest[name]),'Working files changed'
    patch=run('diff','--binary','--no-ext-diff','--no-textconv','HEAD','--',*manifest['modified']) if manifest['modified'] and not orphan else b''
    if not orphan:assert hashlib.sha256(patch).digest()==hashlib.sha256(backup.read('working-tree.patch')).digest()
    for name in ([] if orphan else manifest['untracked']):
        checksum=0
        with (path/name).open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):checksum=zlib.crc32(chunk,checksum)
        assert checksum==backup.getinfo('untracked/'+name).CRC,'Untracked file changed'
tracked=set();head_time=0
if orphan:
    tree=subprocess.run(['git','-C',str(root),'ls-tree','-r','--name-only','-z',row['head']],capture_output=True,check=True).stdout
    tracked={value.decode() for value in tree.split(b'\0') if value}
    head_time=int(subprocess.run(['git','-C',str(root),'show','-s','--format=%ct',row['head']],capture_output=True,check=True).stdout)
native='--native-delete' in sys.argv
links=[];stack=([path] if orphan or not native else []);size=0;files=0;remaining=[]
while stack:
    current=stack.pop()
    with os.scandir(current) as entries:
        for entry in entries:
            if entry.is_symlink():links.append(entry.path);continue
            if entry.is_dir(follow_symlinks=False):
                if os.path.isjunction(entry.path):links.append(entry.path)
                elif not native or entry.name not in {'node_modules','.venv','__pycache__','.pytest_cache','.git','artifacts','.collection-cache'}:
                    stack.append(Path(entry.path))
            elif entry.is_file(follow_symlinks=False):
                size+=entry.stat(follow_symlinks=False).st_size;files+=1
                if orphan:
                    item=Path(entry.path);relative=item.relative_to(path)
                    generated={'node_modules','.venv','__pycache__','.pytest_cache','.git','artifacts','.collection-cache'}
                    # Committed files are retained by the recovery ref. Only save
                    # additional files or edits newer than that exact commit.
                    if not any(part in generated for part in relative.parts):
                        if relative.as_posix() not in tracked or item.stat().st_mtime>head_time+2:
                            remaining.append(item)
if orphan:
    # Git may have detached the worktree before Windows failed on a long filename.
    # Preserve remaining unique files; committed dependency copies need no archive.
    import time
    prefix='remaining-files-'+str(time.time_ns())+'/'
    with zipfile.ZipFile(backup_path,'a',compression=zipfile.ZIP_DEFLATED) as backup:
        for item in remaining:backup.write(item,prefix+item.relative_to(path).as_posix())
    with zipfile.ZipFile(backup_path) as backup:assert backup.testzip() is None
print(json.dumps({'safe':True,'path':str(path),'links':links,'logical_bytes':size,'files':files}))
