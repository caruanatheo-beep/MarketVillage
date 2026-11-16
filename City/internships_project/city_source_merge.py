"""Merge verified source deltas; combine only independent registry additions."""
import re
import ast
import subprocess
import tempfile
from pathlib import Path
from .city_specialists import git
from .marketdesk_city import CityError


def merge_source_bytes(base: bytes, mission: bytes, current: bytes) -> bytes:
    if current==base:return mission
    if mission==base or current==mission:return current
    if b'\0' in base+mission+current:raise CityError('Conflit sur un fichier binaire ; branche conservée.')
    base,mission,current=(data.replace(b'\r\n',b'\n') for data in (base,mission,current))
    with tempfile.TemporaryDirectory(prefix='source-merge-') as temp:
        paths=[Path(temp)/name for name in ('current','base','mission')]
        for path,data in zip(paths,(current,base,mission)):path.write_bytes(data)
        result=subprocess.run(['git','merge-file','--diff3','--stdout','-L','current','-L','base','-L','mission',
                               *map(str,paths)],capture_output=True,timeout=15)
    if result.returncode==0:return result.stdout
    # merge-file returns the number of conflicts, capped at 127.
    if not 1<=result.returncode<=127:raise CityError('Fusion de source impossible ; branche conservée.')
    text=result.stdout.decode('utf-8')
    conflict=re.compile(r'^<<<<<<< current\r?\n(.*?)^\|\|\|\|\|\|\| base\r?\n(.*?)^=======\r?\n(.*?)^>>>>>>> mission\r?\n',re.M|re.S)
    entry=re.compile(r'''^\s*(['"])([^'"]+)\1\s*(?::.+)?,\s*$''')
    def combine(match):
        ours,ancestor,theirs=match.groups()
        if ancestor.strip():
            # Category registries are string sets: preserve only additive changes.
            try:
                nodes=[ast.parse(value).body for value in (ancestor,ours,theirs)]
                assert all(len(body)==1 and isinstance(body[0],ast.Assign) and len(body[0].targets)==1
                           and isinstance(body[0].targets[0],ast.Name) and isinstance(body[0].value,ast.Set) for body in nodes)
                names=[body[0].targets[0].id for body in nodes]
                assert len(set(names))==1 and names[0] in {'TRADING','ASSET_MANAGERS','CLIENT_SOLUTIONS','OTHER'}
                previous,left,right=[ast.literal_eval(body[0].value) for body in nodes]
                assert all(isinstance(v,str) for values in (previous,left,right) for v in values)
                assert previous<=left and previous<=right
                return names[0]+' = {'+', '.join(repr(v) for v in sorted(left|right))+'}\n'
            except (SyntaxError,ValueError,TypeError,AssertionError):
                raise CityError('Conflit sur du code existant ; branche conservée.')
        keys=[]
        for line in (ours+theirs).splitlines():
            found=entry.fullmatch(line)
            if not found:raise CityError('Conflit hors des ajouts de registre ; branche conservée.')
            keys.append(found[2])
        if len(keys)!=len(set(keys)):raise CityError('Conflit sur une même entreprise ; branche conservée.')
        return ours+theirs
    merged=conflict.sub(combine,text)
    if re.search(r'^(<<<<<<<|\|\|\|\|\|\|\||=======|>>>>>>>)',merged,re.M):
        raise CityError('Conflit non résolu ; branche conservée.')
    return merged.encode('utf-8')


def apply_source_delta(repository: Path, base: str, head: str, target: Path, names: list[str],
                       *, target_names: dict[str, str] | None = None) -> None:
    """Prepare every file first, then write the isolated candidate only."""
    changes=[]
    for name in names:
        path=target/(target_names.get(name,name) if target_names else name)
        if not path.resolve().is_relative_to(target.resolve()) or path.is_symlink():
            raise CityError('Chemin de source invalide.')
        old=git(repository,'ls-tree','--name-only',base,'--',name)
        new=git(repository,'ls-tree','--name-only',head,'--',name)
        if not new:raise CityError('Suppression de source interdite ; branche conservée.')
        def blob(revision):
            result=subprocess.run(['git','show',revision+':'+name],cwd=repository,capture_output=True,timeout=15)
            if result.returncode:raise CityError('Version de source introuvable ; branche conservée.')
            return result.stdout
        mission=blob(head)
        if not old:
            if path.exists() and path.read_bytes()!=mission:raise CityError('Ajouts de source incompatibles ; branche conservée.')
            data=mission
        elif not path.exists():
            raise CityError('Fichier de base absent du candidat ; branche conservée.')
        else:data=merge_source_bytes(blob(base),mission,path.read_bytes())
        changes.append((path,data))
    for path,data in changes:
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)
