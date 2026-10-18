"""Owned Windows process tree: atomic job assignment at creation, then resume.

No CLI or arbitrary-PID operations. Limits are caller-reviewed workload inputs.
The non-inheritable, unnamed job is destroyed with its owner's last handle;
KILL_ON_JOB_CLOSE then terminates its members, including on owner death.
Microsoft contract: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
"""
import ctypes as c
from ctypes import wintypes as w
import math
import os
import subprocess


class Basic(c.Structure):
    _fields_ = [('process_time', c.c_int64), ('job_time', c.c_int64), ('flags', w.DWORD),
                ('min_working_set', c.c_size_t), ('max_working_set', c.c_size_t),
                ('active_processes', w.DWORD), ('affinity', c.c_size_t),
                ('priority', w.DWORD), ('scheduling', w.DWORD)]


class IO(c.Structure):
    _fields_ = [(name, c.c_uint64) for name in ('reads', 'writes', 'other', 'read_bytes', 'write_bytes', 'other_bytes')]


class Extended(c.Structure):
    _fields_ = [('basic', Basic), ('io', IO), ('process_memory', c.c_size_t),
                ('job_memory', c.c_size_t), ('peak_process_memory', c.c_size_t), ('peak_job_memory', c.c_size_t)]


class Startup(c.Structure):
    _fields_ = [('cb', w.DWORD), ('reserved', w.LPWSTR), ('desktop', w.LPWSTR), ('title', w.LPWSTR),
                *[(name, w.DWORD) for name in ('x', 'y', 'xsize', 'ysize', 'xchars', 'ychars', 'fill', 'flags')],
                ('show', w.WORD), ('reserved_size', w.WORD), ('reserved_ptr', c.POINTER(c.c_byte)),
                ('stdin', w.HANDLE), ('stdout', w.HANDLE), ('stderr', w.HANDLE)]


class ProcessInfo(c.Structure):
    _fields_ = [('process', w.HANDLE), ('thread', w.HANDLE), ('pid', w.DWORD), ('tid', w.DWORD)]


class StartupEx(c.Structure):
    _fields_ = [('startup', Startup), ('attributes', c.c_void_p)]


def api():
    if os.name != 'nt':
        raise RuntimeError('Windows job supervision required')
    kernel = c.WinDLL('kernel32', use_last_error=True)
    signatures = {
        'CreateJobObjectW': ([c.c_void_p, w.LPCWSTR], w.HANDLE),
        'SetInformationJobObject': ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD], w.BOOL),
        'CreateProcessW': ([w.LPCWSTR, w.LPWSTR, c.c_void_p, c.c_void_p, w.BOOL, w.DWORD,
                            c.c_void_p, w.LPCWSTR, c.POINTER(Startup), c.POINTER(ProcessInfo)], w.BOOL),
        'AssignProcessToJobObject': ([w.HANDLE, w.HANDLE], w.BOOL),
        'InitializeProcThreadAttributeList': ([c.c_void_p, w.DWORD, w.DWORD, c.POINTER(c.c_size_t)], w.BOOL),
        'UpdateProcThreadAttribute': ([c.c_void_p, w.DWORD, c.c_size_t, c.c_void_p, c.c_size_t,
                                       c.c_void_p, c.c_void_p], w.BOOL),
        'DeleteProcThreadAttributeList': ([c.c_void_p], None),
        'ResumeThread': ([w.HANDLE], w.DWORD), 'CloseHandle': ([w.HANDLE], w.BOOL),
        'TerminateJobObject': ([w.HANDLE, w.UINT], w.BOOL),
        'TerminateProcess': ([w.HANDLE, w.UINT], w.BOOL),
        'WaitForSingleObject': ([w.HANDLE, w.DWORD], w.DWORD),
        'GetExitCodeProcess': ([w.HANDLE, c.POINTER(w.DWORD)], w.BOOL)}
    signatures.update({
        'GetProcessAffinityMask': ([w.HANDLE, c.POINTER(c.c_size_t), c.POINTER(c.c_size_t)], w.BOOL),
        'GetActiveProcessorGroupCount': ([], w.WORD),
        'QueryInformationJobObject': ([w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p], w.BOOL),
        'GetCurrentProcess': ([], w.HANDLE),
        'OpenProcess': ([w.DWORD, w.BOOL, w.DWORD], w.HANDLE),
        'DuplicateHandle': ([w.HANDLE, w.HANDLE, w.HANDLE, c.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD], w.BOOL)})
    for name, (args, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes, function.restype = args, result
    return kernel


def checked(result):
    if not result:
        raise c.WinError(c.get_last_error())
    return result


class Process:
    """Popen-like wait/stop interface; never adopts a process by PID."""
    def __init__(self, argv, *, cwd, env, memory_bytes=128 * 1024**2, processes=1, single_cpu=False):
        if (not argv or not os.path.isabs(argv[0]) or type(memory_bytes) is not int or memory_bytes <= 0 or
                type(processes) is not int or not 1 <= processes <= 4 or type(single_cpu) is not bool):
            raise ValueError('Invalid owned job contract')
        self.kernel = api()
        self.job = self.handle = None
        self.returncode = None
        job = checked(self.kernel.CreateJobObjectW(None, None))  # No name/inheritable security attributes.
        info = ProcessInfo()
        attributes = None
        try:
            limits = Extended()
            limits.basic.flags = 0x2000 | 0x200 | 0x8 | 0x400
            limits.basic.active_processes = processes
            limits.job_memory = memory_bytes
            if single_cpu:
                # Refuse multi-group ambiguity. No affinity or power setting on
                # the owner/system is changed; only this new job is constrained.
                if self.kernel.GetActiveProcessorGroupCount() != 1:
                    raise RuntimeError('Single-group processor affinity required')
                allowed, system = c.c_size_t(), c.c_size_t()
                checked(self.kernel.GetProcessAffinityMask(self.kernel.GetCurrentProcess(), c.byref(allowed), c.byref(system)))
                if not allowed.value:
                    raise RuntimeError('No permitted logical processor')
                limits.basic.flags |= 0x10
                limits.basic.affinity = allowed.value & -allowed.value
            checked(self.kernel.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)))
            if single_cpu:
                observed = Extended()
                checked(self.kernel.QueryInformationJobObject(job, 9, c.byref(observed), c.sizeof(observed), None))
                if (observed.basic.flags != limits.basic.flags or observed.basic.affinity != limits.basic.affinity or
                        observed.job_memory != memory_bytes or observed.basic.active_processes != processes):
                    raise RuntimeError('Job limits did not take effect before creation')
            size = c.c_size_t()
            self.kernel.InitializeProcThreadAttributeList(None, 1, 0, c.byref(size))
            if not 0 < size.value <= 4096:
                raise RuntimeError('Windows job attribute list unsupported')
            buffer = c.create_string_buffer(size.value)
            checked(self.kernel.InitializeProcThreadAttributeList(buffer, 1, 0, c.byref(size)))
            attributes = buffer
            jobs = (w.HANDLE * 1)(job)
            # PROC_THREAD_ATTRIBUTE_JOB_LIST: creation and membership succeed
            # together. Owner death cannot leave an unassigned suspended child.
            checked(self.kernel.UpdateProcThreadAttribute(attributes, 0, 0x0002000d, jobs, c.sizeof(jobs), None, None))
            startup = StartupEx()
            startup.startup.cb = c.sizeof(startup)
            startup.attributes = c.cast(attributes, c.c_void_p)
            environment = c.create_unicode_buffer('\0'.join(k + '=' + v for k, v in sorted(env.items())) + '\0\0')
            command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
            # No child instruction runs until it belongs to the kill-on-close job.
            checked(self.kernel.CreateProcessW(argv[0], command, None, None, False,
                    0x4 | 0x400 | 0x08000000 | 0x80000, environment, str(cwd),
                    c.cast(c.byref(startup), c.POINTER(Startup)), c.byref(info)))
            if self.kernel.ResumeThread(info.thread) == 0xffffffff:
                raise c.WinError(c.get_last_error())
            self.job, self.handle, self.pid = job, info.process, info.pid
        except BaseException:
            if info.process:
                self.kernel.TerminateProcess(info.process, 125)
                self.kernel.WaitForSingleObject(info.process, 1000)
                self.kernel.CloseHandle(info.process)
            self.kernel.CloseHandle(job)
            raise
        finally:
            if info.thread:
                self.kernel.CloseHandle(info.thread)
            if attributes is not None:
                self.kernel.DeleteProcThreadAttributeList(attributes)

    def poll(self):
        if self.returncode is not None:
            return self.returncode
        status = self.kernel.WaitForSingleObject(self.handle, 0)
        if status == 258:
            return None
        if status != 0:
            raise c.WinError(c.get_last_error())
        code = w.DWORD()
        checked(self.kernel.GetExitCodeProcess(self.handle, c.byref(code)))
        self.returncode = code.value
        return self.returncode

    def wait(self, timeout):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 <= timeout <= 60:
            raise ValueError('Finite bounded wait required')
        status = self.kernel.WaitForSingleObject(self.handle, math.ceil(timeout * 1000))
        if status == 258:
            raise subprocess.TimeoutExpired('owned-windows-job', timeout)
        if status != 0:
            raise c.WinError(c.get_last_error())
        return self.poll()

    def terminate(self):
        checked(self.kernel.TerminateJobObject(self.job, 125))

    kill = terminate

    def witness_for_parent(self):
        """Duplicate only query/wait rights into this process's actual parent.

        A verifier retains exit evidence without retaining the job or a kill
        handle. It can then confirm owner-death cleanup without PID reuse.
        """
        parent = checked(self.kernel.OpenProcess(0x40, False, os.getppid()))
        try:
            duplicate = w.HANDLE()
            checked(self.kernel.DuplicateHandle(self.kernel.GetCurrentProcess(), self.handle, parent,
                    c.byref(duplicate), 0x100000 | 0x1000, False, 0))
            return duplicate.value
        finally:
            self.kernel.CloseHandle(parent)

    def close(self):
        if self.job:
            checked(self.kernel.CloseHandle(self.job))
            self.job = None
        if self.handle:
            checked(self.kernel.CloseHandle(self.handle))
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class Witness(Process):
    """Read-only process-handle witness created by the fixed rehearsal owner."""
    def __init__(self, handle):
        if type(handle) is not int or handle <= 0:
            raise ValueError('Invalid exit witness')
        self.kernel, self.handle, self.job, self.returncode = api(), handle, None, None

    def terminate(self):
        raise RuntimeError('Exit witness has no termination rights')

    kill = terminate
