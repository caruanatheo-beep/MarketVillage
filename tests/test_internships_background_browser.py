"""BNP collection must never fall back to the user's visible desktop."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import pytest
from internships_project import background_desktop as hidden, internships as jobs


class Function:
    def __init__(self, fn): self.fn = fn
    def __call__(self, *args): return self.fn(*args)


@pytest.mark.parametrize('failure', ['', 'desktop', 'spawn', 'timeout', 'source'])
def test_isolated_process_results_failures_and_cleanup(monkeypatch, failure):
    closed, killed, arguments = [], [], []
    def spawn(executable, command, sa, ta, inherit, flags, env, cwd, startup, process):
        assert startup._obj.lpDesktop.startswith('MarketDesk-collect-')
        assert flags == 0x08000000 and not inherit
        if failure == 'spawn': return 0
        process._obj.hProcess, process._obj.hThread, process._obj.dwProcessId = 20, 21, 22
        result = {'error': 'HTTP 403'} if failure == 'source' else {'jobs': []}
        Path(arguments[-1]).write_text(json.dumps(result), encoding='utf-8')
        return 1
    user = SimpleNamespace(CreateDesktopW=Function(lambda *a: 0 if failure == 'desktop' else 10),
                           CloseDesktop=Function(lambda h: closed.append(h)))
    kernel = SimpleNamespace(CreateProcessW=Function(spawn),
        WaitForSingleObject=Function(lambda *a: 258 if failure == 'timeout' else 0),
        CloseHandle=Function(lambda h: closed.append(h)))
    monkeypatch.setattr(hidden.ctypes, 'WinDLL', lambda name, **kw: user if name == 'user32' else kernel, raising=False)
    def command(args):
        arguments.extend(args)
        return 'synthetic command'
    monkeypatch.setattr(hidden.subprocess, 'list2cmdline', command)
    monkeypatch.setattr(hidden.subprocess, 'run', lambda args, **kw: killed.append(args))
    if failure:
        with pytest.raises(ValueError): hidden.collect_bnp('BNP Paribas', 'https://group.bnpparibas/listing')
    else:
        assert hidden.collect_bnp('BNP Paribas', 'https://group.bnpparibas/listing') == []
    assert closed == ([] if failure == 'desktop' else [10] if failure == 'spawn' else [21,20,10])
    assert bool(killed) == (failure == 'timeout')
    if arguments: assert not Path(arguments[-1]).exists()


@pytest.mark.skipif(os.name != 'nt', reason='Windows dispatch')
def test_all_bnp_connectors_use_isolated_collection_and_keep_metadata(monkeypatch):
    job = jobs.Opportunity('Sales', 'BNP Paribas', 'Paris', 'Stage', 'https://group.bnpparibas/job', '', 80,
                           start_period='janvier 2027', description='Marchés')
    monkeypatch.setattr(hidden, 'collect_bnp', lambda *args: [asdict(job)])
    monkeypatch.setattr(jobs, '_bnp_group_jobs_browser', lambda *a, **kw: pytest.fail('Visible fallback forbidden'))
    for company in ('BNP Paribas','BNP Paribas Asset Management'):
        assert jobs._bnp_group_jobs(company,'https://group.bnpparibas/listing') == [job]
    def fail(*args): raise ValueError('Isolation impossible')
    monkeypatch.setattr(hidden, 'collect_bnp', fail)
    with pytest.raises(ValueError, match='Isolation impossible'):
        jobs._bnp_group_jobs('BNP Paribas','https://group.bnpparibas/listing')


@pytest.mark.skipif(os.name != 'nt', reason='Windows desktop guard')
def test_worker_refuses_to_launch_on_wrong_desktop(tmp_path, monkeypatch):
    path = tmp_path / 'exchange.json'
    path.write_text(json.dumps({'desktop':'MarketDesk-collect-does-not-exist'}),encoding='utf-8')
    monkeypatch.setattr(hidden.sys,'argv',['background_desktop.py',str(path)])
    hidden._main()
    assert json.loads(path.read_text(encoding='utf-8')) == {'error':'Collecte refusée sur le bureau interactif.'}
