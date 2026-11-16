"""Run the public BNP browser on a private Windows desktop, never the input desktop."""
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from uuid import uuid4


class _StartupInfo(ctypes.Structure):
    _fields_ = [('cb', wintypes.DWORD), ('lpReserved', wintypes.LPWSTR),
                ('lpDesktop', wintypes.LPWSTR), ('lpTitle', wintypes.LPWSTR),
                *[(key, wintypes.DWORD) for key in ('dwX','dwY','dwXSize','dwYSize',
                   'dwXCountChars','dwYCountChars','dwFillAttribute','dwFlags')],
                ('wShowWindow', wintypes.WORD), ('cbReserved2', wintypes.WORD),
                ('lpReserved2', ctypes.c_void_p), ('hStdInput', wintypes.HANDLE),
                ('hStdOutput', wintypes.HANDLE), ('hStdError', wintypes.HANDLE)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [('hProcess', wintypes.HANDLE), ('hThread', wintypes.HANDLE),
                ('dwProcessId', wintypes.DWORD), ('dwThreadId', wintypes.DWORD)]


def collect_bnp(company: str, listing_url: str) -> list[dict]:
    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    user32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p]
    user32.CreateDesktopW.restype = wintypes.HANDLE
    user32.CloseDesktop.argtypes = [wintypes.HANDLE]
    kernel32.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
        ctypes.c_void_p, wintypes.BOOL, wintypes.DWORD, ctypes.c_void_p, wintypes.LPCWSTR,
        ctypes.POINTER(_StartupInfo), ctypes.POINTER(_ProcessInfo)]
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    name = 'MarketDesk-collect-' + uuid4().hex
    desktop = user32.CreateDesktopW(name, None, None, 0, 0x01FF, None)
    if not desktop:
        raise ValueError('Bureau de collecte invisible indisponible ; aucune fenêtre ouverte.')
    process = _ProcessInfo()
    try:
        with tempfile.TemporaryDirectory(prefix='marketdesk-bnp-') as temporary:
            exchange = Path(temporary) / 'result.json'
            exchange.write_text(json.dumps({'company': company, 'url': listing_url,
                'paths': sys.path, 'desktop': name}), encoding='utf-8')
            startup = _StartupInfo(cb=ctypes.sizeof(_StartupInfo), lpDesktop=name)
            command = ctypes.create_unicode_buffer(subprocess.list2cmdline(
                [sys.executable, str(Path(__file__).resolve()), str(exchange)]))
            # subprocess.STARTUPINFO does not expose lpDesktop; set it explicitly at process creation.
            if not kernel32.CreateProcessW(sys.executable, command, None, None, False,
                    0x08000000, None, str(Path(__file__).resolve().parents[1]),
                    ctypes.byref(startup), ctypes.byref(process)):
                raise ValueError('Navigateur de collecte invisible indisponible ; aucune fenêtre ouverte.')
            if kernel32.WaitForSingleObject(process.hProcess, 300_000) != 0:
                subprocess.run(['taskkill', '/PID', str(process.dwProcessId), '/T', '/F'],
                    capture_output=True, timeout=15, creationflags=0x08000000)
                kernel32.WaitForSingleObject(process.hProcess, 5000)
                raise ValueError('Collecte BNP interrompue après cinq minutes ; offres précédentes conservées.')
            result = json.loads(exchange.read_text(encoding='utf-8'))
            if 'jobs' not in result:
                raise ValueError(result.get('error') or 'Collecte BNP interrompue ; aucune fenêtre ouverte.')
            return result['jobs']
    finally:
        if process.hThread:
            kernel32.CloseHandle(process.hThread)
        if process.hProcess:
            kernel32.CloseHandle(process.hProcess)
        user32.CloseDesktop(desktop)


def _main():
    exchange = Path(sys.argv[1])
    payload = json.loads(exchange.read_text(encoding='utf-8'))
    try:
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
        user32.GetThreadDesktop.argtypes = [wintypes.DWORD]
        user32.GetThreadDesktop.restype = wintypes.HANDLE
        user32.GetUserObjectInformationW.argtypes = [wintypes.HANDLE, ctypes.c_int,
            ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
        handle = user32.GetThreadDesktop(kernel32.GetCurrentThreadId())
        name, needed = ctypes.create_unicode_buffer(256), wintypes.DWORD()
        if (not user32.GetUserObjectInformationW(handle, 2, name, ctypes.sizeof(name), ctypes.byref(needed))
                or name.value != payload['desktop'] or not name.value.startswith('MarketDesk-collect-')):
            raise ValueError('Collecte refusée sur le bureau interactif.')
        sys.path[:] = payload['paths']
        from dataclasses import asdict
        from internships_project.internships import _bnp_group_jobs_browser
        result = {'jobs': [asdict(job) for job in _bnp_group_jobs_browser(
            payload['company'], payload['url'], headless=False)]}
    except Exception as exc:
        result = {'error': str(exc) if isinstance(exc, ValueError) else f'Collecte BNP indisponible ({type(exc).__name__}).'}
    exchange.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')


if __name__ == '__main__':
    _main()
