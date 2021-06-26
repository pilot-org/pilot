import logging
import abc
import os
import threading
import asyncio
import asyncclick as click
import watchdog.observers
import watchdog.events

from typing import Mapping, List

logger = logging.getLogger(__name__)
logger_modify = logging.getLogger(f'{__name__}.modify')
logger_event = logging.getLogger(f'{__name__}.event')
logger_merge = logging.getLogger(f'{__name__}.merge')
logger_mirror = logging.getLogger(f'{__name__}.mirror')
logger_diff = logging.getLogger(f'{__name__}.diff')


class _DirDiff:
    def __init__(self):
        self._event_queue = []

    def get_events(self):
        return self._event_queue

    def add_event(self, event):
        def get_after_path_key(event):
            return 'dest_path' if event.event_type == watchdog.events.EVENT_TYPE_MOVED else 'src_path'

        def replace(i, new_e):
            old_e = self._event_queue[i]
            logger_modify.debug('Detect and change event %s to %s', old_e,
                                new_e)
            self._event_queue[i] = new_e

        def pop(i):
            old_e = self._event_queue[i]
            logger_modify.debug('Detect and remove %s', old_e)
            self._event_queue.pop(i)

        if event.event_type == watchdog.events.EVENT_TYPE_MOVED and event.is_directory is True:
            for i, e in enumerate(self._event_queue):
                name = get_after_path_key(e)
                after_path = getattr(e, name)
                if after_path.startswith(event.src_path):
                    kwargs = {
                        name:
                        event.dest_path + after_path[len(event.src_path):]
                    }
                    replace(i, self._modify_event(e, **kwargs))
        elif event.event_type == watchdog.events.EVENT_TYPE_DELETED:
            for i, e in enumerate(self._event_queue):
                name = get_after_path_key(e)
                if not event.is_directory:
                    if getattr(e, name) == event.src_path:
                        pop(i)
                else:
                    if getattr(e, name).startswith(event.src_path):
                        pop(i)
        self._event_queue.append(event)

    @staticmethod
    def _modify_event(event, src_path=None, dest_path=None):
        from watchdog.events import (DirMovedEvent, FileMovedEvent,
                                     DirDeletedEvent, FileDeletedEvent,
                                     DirCreatedEvent, FileCreatedEvent,
                                     DirModifiedEvent, FileModifiedEvent,
                                     EVENT_TYPE_MOVED, EVENT_TYPE_DELETED,
                                     EVENT_TYPE_CREATED, EVENT_TYPE_MODIFIED)
        is_dir = event.is_directory
        get_src_path = lambda: event.src_path if src_path is None else src_path
        get_dest_path = lambda: event.dest_path if dest_path is None else dest_path
        cls_map = {
            EVENT_TYPE_MOVED: DirMovedEvent if is_dir else FileMovedEvent,
            EVENT_TYPE_DELETED:
            DirDeletedEvent if is_dir else FileDeletedEvent,
            EVENT_TYPE_CREATED:
            DirCreatedEvent if is_dir else FileCreatedEvent,
            EVENT_TYPE_MODIFIED:
            DirModifiedEvent if is_dir else FileModifiedEvent,
        }
        args = [
            get_src_path(), get_dest_path()
        ] if event.event_type == EVENT_TYPE_MOVED else [get_src_path()]
        res = cls_map[event.event_type](*args)
        logger_modify.debug('New event: %s', res)
        return res


class HandleQueue(abc.ABC):
    def __init__(self):
        self._count = 0
        self._lock = threading.Lock()
        self._tree = self._get_new_diff_tree()

    @staticmethod
    def _get_new_diff_tree():
        return _DirDiff()

    async def handle_events(self, handle_checker=None):
        tree = None
        with self._lock:
            pop_all = True if handle_checker is None else handle_checker(
                count=self._count)
            if pop_all:
                tree = self._tree
                self._tree = self._get_new_diff_tree()
        if pop_all and tree is not None:
            await self.handle_all_events(tree.get_events())

    @abc.abstractmethod
    def handle_all_events(self, events):
        pass

    def push_event(self, event):
        with self._lock:
            self._tree.add_event(event)
            self._count += 1


class _JustAFuncHandleQueue(HandleQueue):
    def __init__(self, handle_events_func):
        super().__init__()
        self._handle_func = handle_events_func

    async def handle_all_events(self, *args, **kwargs):
        res = self._handle_func(*args, **kwargs)
        if asyncio.iscoroutinefunction(self._handle_func):
            await res


class _Handler(watchdog.events.PatternMatchingEventHandler):
    def __init__(self, handle_queue):
        super().__init__(ignore_patterns=['*/.git*'])
        self._handle_queue = handle_queue

    def on_any_event(self, event):
        logger_event.info('Detect event %s', event)
        self._handle_queue.push_event(event)


class _RepeatedEqualityChecker:
    def __init__(self, repeat_threshold):
        self._repeat_threshold = repeat_threshold
        self._last_count = None
        self._equal_time = 0

    def __call__(self, count):
        result = False
        equal = False
        if self._last_count is not None:
            equal = bool(count == self._last_count)
        self._last_count = count
        if equal:
            self._equal_time += 1
            if self._equal_time == self._repeat_threshold:
                result = True
        else:
            self._equal_time = 0
        logger_merge.debug(
            'count: %d, last_count: %s, equal_time: %d, repeat_threshold: %d, result: %s',
            count, self._last_count, self._equal_time, self._repeat_threshold,
            result)
        return result


class Observer:
    def __init__(self):
        self._observer = watchdog.observers.Observer()
        self._stop = True
        self._handle_queues = []

    @staticmethod
    def new_watcher(handle_events_func):
        return _JustAFuncHandleQueue(handle_events_func)

    def add_watcher(self,
                    watch_path,
                    handle_queue,
                    recursive=False,
                    handler_cls=_Handler):
        if self._stop is False:
            raise RuntimeError('Cannot add watcher when observer is start')

        handler = handler_cls(handle_queue)
        self._observer.schedule(handler, path=watch_path, recursive=recursive)
        self._handle_queues.append(handle_queue)

    async def start(self, handle_interval, sleep_interval=0.1):
        repeat_threshold = handle_interval // sleep_interval
        handle_items = [(item, _RepeatedEqualityChecker(repeat_threshold))
                        for item in self._handle_queues]
        self._observer.start()
        self._stop = False
        try:
            while self._stop is False:
                await asyncio.sleep(sleep_interval)
                for handle_queue, checker in handle_items:
                    await handle_queue.handle_events(handle_checker=checker)
        except KeyboardInterrupt:
            click.secho('user interrupt', fg='yellow')
        finally:
            self._stop = True
            self._observer.stop()
            self._observer.join()
            click.secho('watch close', fg='yellow')

    def stop_non_immediately(self):
        self._stop = True


class FolderMirrorMonitor:
    def __init__(self):
        self._observer = Observer()

    def add_mirror_pair(self, source_dir, mirror_dest_dirs: List[str]):
        '''source and mirror_targets must be realpath'''
        if not isinstance(mirror_dest_dirs, list):
            raise TypeError(f'{mirror_dest_dirs} must be string list')

        async def copy(events):
            def check_parent_is_hanedled(event):
                handled_dirs = handled_dirs_map[event.event_type]
                for handled_dir in handled_dirs:
                    if os.path.commonpath([event.src_path,
                                           handled_dir]) == handled_dir:
                        return True
                return False

            tasks = []
            handled_dirs_map: Mapping[str, List] = {
                watchdog.events.EVENT_TYPE_CREATED: [],
                watchdog.events.EVENT_TYPE_MOVED: [],
                watchdog.events.EVENT_TYPE_DELETED: [],
            }

            def create_subprocess_exec(*cmds, **kwargs):
                async def task():
                    logger_mirror.debug('Command: %s', cmds)
                    res = await asyncio.create_subprocess_exec(
                        *cmds,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        **kwargs)
                    if (res.returncode != 0):
                        logger_mirror.warning(
                            'Failed to exec %s\nstdout: %s\nstderr: %s',
                            ' '.join(cmds), await res.stdout.read(), await
                            res.stderr.read())

                nonlocal tasks
                tasks += [task()]

            for event in events:
                logger_mirror.debug('Handle event: %s', event)
                if event.event_type == watchdog.events.EVENT_TYPE_MODIFIED:
                    if not event.is_directory:
                        # TODO: check hard link of file is equal
                        pass
                    continue

                if check_parent_is_hanedled(event):
                    logger_mirror.debug('Skip event: %s', event)
                    continue

                if event.event_type == watchdog.events.EVENT_TYPE_CREATED:
                    rel_path = os.path.relpath(event.src_path, source_dir)
                    src = os.path.join(source_dir, rel_path)
                    for dest_dir in mirror_dest_dirs:
                        dest = os.path.join(dest_dir, rel_path)
                        create_subprocess_exec('/bin/cp', '-al', src, dest)
                elif event.event_type == watchdog.events.EVENT_TYPE_MOVED:
                    for dest_dir in mirror_dest_dirs:
                        rel_src = os.path.relpath(event.src_path, source_dir)
                        src = os.path.join(dest_dir, rel_src)
                        rel_dest = os.path.relpath(event.dest_path, source_dir)
                        dest = os.path.join(dest_dir, rel_dest)
                        logger_mirror.debug('test123 %s %s %s %s', rel_src,
                                            src, rel_dest, dest)
                        create_subprocess_exec('/bin/mv', src, dest)
                elif event.event_type == watchdog.events.EVENT_TYPE_DELETED:
                    for dest_dir in mirror_dest_dirs:
                        rel_path = os.path.relpath(event.src_path, source_dir)
                        src = os.path.join(dest_dir, rel_path)
                        create_subprocess_exec('/bin/rm', '-r', src)

                if event.is_directory:
                    handled_dirs_map[event.event_type].append(event.src_path)

            await asyncio.gather(*tasks)

        watcher = self._observer.new_watcher(copy)
        self._observer.add_watcher(source_dir, watcher, recursive=True)

    async def start(self, *args, **kwargs):
        await self._observer.start(*args, **kwargs)

    def stop_non_immediately(self):
        self._observer.stop_non_immediately()


def get_loss_diff(dir1, dir2, check_inode=False, ignore_names=[]):
    def is_ignore(path):
        while True:
            dirname, basename = os.path.split(path)
            if basename in ignore_names:
                return True
            elif dirname == '':
                return False
            path = dirname

    diff_dirs = []
    diff_files = []
    for root, dirs, files in os.walk(dir1):
        sub_root = os.path.relpath(root, dir1)
        if is_ignore(sub_root):
            logger.debug('Ingnore check %s', sub_root)
            continue
        if root in diff_dirs:
            continue
        for d in dirs:
            logger_diff.debug('Check root=%s, dir=%s', sub_root, d)
            sub_path = os.path.normpath(os.path.join(sub_root, d))
            path_in_dir2 = os.path.join(dir2, sub_path)
            logger_diff.debug('Check dir=%s', path_in_dir2)
            if not os.path.exists(path_in_dir2):
                logger_diff.info('Detect %s is in %s but not in %s', sub_path,
                                 dir1, dir2)
                diff_dirs.append(sub_path)
        for f in files:
            logger_diff.debug('Check root=%s, file=%s', sub_root, f)
            sub_path = os.path.normpath(os.path.join(sub_root, f))
            path_in_dir1 = os.path.join(dir1, sub_path)
            path_in_dir2 = os.path.join(dir2, sub_path)
            logger_diff.debug('Check file=%s', path_in_dir2)
            if not os.path.exists(path_in_dir2):
                logger_diff.info('Detect %s is in %s but not in %s', sub_path,
                                 dir1, dir2)
                diff_files.append(sub_path)
            elif check_inode is True and not os.path.samefile(
                    path_in_dir1, path_in_dir2):
                logger_diff.info('Detect %s and %s are different files',
                                 os.path.join(dir1, sub_path),
                                 os.path.join(dir2, sub_path))
                diff_files.append(sub_path)

    return diff_dirs, diff_files
