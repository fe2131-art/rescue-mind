"""Fail-closed process supervision for the Gazebo demonstration (not safety certified).

No network/API/ROS call is made by this module; process management is isolated
for deterministic unit tests.  On abnormal exit or interruption, stop child
process groups and preserve individual logs.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import signal
import subprocess
import time
from typing import Callable


@dataclass(frozen=True)
class ManagedCommand:
    name: str
    argv: tuple[str, ...]


class StackFailure(RuntimeError):
    pass


class Supervisor:
    def __init__(self, log_dir: Path, *, spawn: Callable = subprocess.Popen,
                 monotonic: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], None] = time.sleep):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.spawn = spawn
        self.monotonic = monotonic
        self.sleep = sleep
        self.services: list[tuple[str, object, object]] = []

    def start_service(self, spec: ManagedCommand):
        if not spec.argv or not all(isinstance(x, str) and x for x in spec.argv):
            raise ValueError('Invalid command')
        path = self.log_dir / f'{spec.name}.log'
        output = path.open('ab')
        try:
            proc = self.spawn(list(spec.argv), stdout=output,
                              stderr=subprocess.STDOUT, start_new_session=True)
        except BaseException:
            output.close()
            raise
        self.services.append((spec.name, proc, output))
        return proc

    def ensure_alive(self):
        for name, proc, _ in self.services:
            status = proc.poll()
            if status is not None:
                raise StackFailure(f'{name} exited early (exit={status}); inspect {name}.log')

    def wait_readiness(self, probe: Callable[[], bool], timeout_s: float, interval_s: float = 1.):
        if timeout_s <= 0 or interval_s <= 0:
            raise ValueError('invalid readiness timeouts')
        deadline = self.monotonic() + timeout_s
        while self.monotonic() <= deadline:
            self.ensure_alive()
            ready = probe()
            if self.monotonic() > deadline:
                raise StackFailure('ROS/Gazebo readiness exceeded deadline')
            if ready:
                return
            self.sleep(interval_s)
        raise StackFailure('ROS/Gazebo readiness timeout; no motion permitted')

    def run_mission(self, spec: ManagedCommand, timeout_s: float):
        if timeout_s <= 0:
            raise ValueError('mission timeout must be positive')
        self.ensure_alive()
        output = (self.log_dir / f'{spec.name}.log').open('ab')
        proc = None
        try:
            proc = self.spawn(list(spec.argv), stdout=output,
                              stderr=subprocess.STDOUT, start_new_session=True)
            deadline = self.monotonic() + timeout_s
            while proc.poll() is None:
                self.ensure_alive()
                if self.monotonic() >= deadline:
                    self._terminate(proc)
                    raise StackFailure('mission exceeded timeout; command to stop and tear down stack')
                self.sleep(.1)
            if proc.returncode != 0:
                raise StackFailure(f'mission failed (exit={proc.returncode}); see {spec.name}.log')
            return proc.returncode
        finally:
            if proc is not None:
                self._terminate(proc)  # Mission must NOT remain active if a guard/bridge crashes.
            output.close()

    @staticmethod
    def _terminate(proc, *, initial_signal=signal.SIGINT, wait_seconds=5):
        """Tear down a whole process group: graceful signal, then SIGTERM, then SIGKILL.

        v3.3 live finding: ROS 2 Python nodes ignore-by-dying on SIGTERM, i.e. they
        exit without destroying their DDS participant, and a killed supervisor left
        entire stacks (guard included) running.  SIGINT lets rclpy / ros2 launch /
        rosbag2 / gz shut down cleanly; escalation keeps the stop fail-closed.
        """
        def signal_group(sig):
            try:
                os.killpg(proc.pid, sig)
            except ProcessLookupError:
                pass
            except PermissionError:
                if proc.poll() is None:
                    proc.send_signal(sig)
        # The service leader may have exited while children in its process group
        # remain alive.  Therefore tear down the whole session even then.
        chain = [(initial_signal, wait_seconds)]
        if initial_signal != signal.SIGKILL:
            if initial_signal != signal.SIGTERM:
                chain.append((signal.SIGTERM, 3))
            chain.append((signal.SIGKILL, 2))
        for sig, wait in chain:
            signal_group(sig)
            try:
                proc.wait(timeout=wait)
                break
            except subprocess.TimeoutExpired:
                continue
        # Leader is gone; sweep any straggler left in its process group.
        time.sleep(0.3)
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def stop_service(self, name: str, *, wait_seconds: float = 15.) -> dict:
        """Finalize a running recorder before auditing on-disk evidence.

        SIGINT is delivered to its process group and we wait for completion;
        a forced kill is *never* reported as a clean recording. Removing this
        service prevents the next ensure_alive() from treating its intentional
        exit as a crash. Other services remain supervised until context exit.
        """
        matches = [(i, entry) for i, entry in enumerate(self.services) if entry[0] == name]
        if len(matches) != 1 or name != 'rosbag_recorder':
            raise StackFailure('only one running rosbag_recorder can be finalized')
        i, (_, proc, output) = matches[0]
        if proc.poll() is not None:
            self.services.pop(i)
            output.close()
            raise StackFailure('rosbag_recorder exited before finalization')
        try:
            try:
                os.killpg(proc.pid, signal.SIGINT)
            except ProcessLookupError as exc:
                raise StackFailure('rosbag_recorder process group disappeared') from exc
            except PermissionError:
                proc.send_signal(signal.SIGINT)
            try:
                code = proc.wait(timeout=wait_seconds)
            except subprocess.TimeoutExpired as exc:
                self._terminate(proc, initial_signal=signal.SIGKILL)
                raise StackFailure('rosbag_recorder SIGINT finalization timed out; evidence invalid') from exc
            if code not in (0, -signal.SIGINT, 128+signal.SIGINT):
                raise StackFailure(f'rosbag_recorder finalization failed (exit={code})')
            return {'service': name, 'signal': 'SIGINT', 'exit_code': code,
                    'process_finished_before_metadata_audit': True}
        finally:
            self.services.pop(i)
            output.close()

    def shutdown(self):
        for name, proc, _ in reversed(self.services):
            # Every service gets SIGINT first (rosbag2 needs it to finalize its
            # database; ROS nodes need it to remove their DDS participants), then
            # escalates to SIGTERM / SIGKILL.
            self._terminate(proc, initial_signal=signal.SIGINT,
                            wait_seconds=10 if name == 'rosbag_recorder' else 5)
        for _, _, output in reversed(self.services):
            output.close()
        self.services.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.shutdown()
