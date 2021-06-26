from os.path import dirname
import unittest
import asyncio
import os
import tempfile
import shutil
import pathlib
import watchdog.events
from loguru import logger

from pilot import watch


def mk_tmp_dir():
    dir_path = tempfile.mktemp()
    os.mkdir(dir_path)
    return dir_path


def touch(path):
    pathlib.Path(path).touch()


class WatchTestUtil(unittest.IsolatedAsyncioTestCase):
    async def start_test_with_timeout(self, test_step, stop_func, test_time,
                                      *tasks):
        test_finish = False

        async def stop_observer():
            await asyncio.sleep(test_time)
            stop_func()
            nonlocal test_finish
            self.assertTrue(test_finish)

        async def test_step_wrap():
            await test_step()
            nonlocal test_finish
            test_finish = True

        await asyncio.gather(stop_observer(), test_step_wrap(), *tasks)


class TestWatch(WatchTestUtil):
    def setUp(self):
        self._dir_path = tempfile.mktemp()
        os.mkdir(self._dir_path)

    def tearDown(self):
        shutil.rmtree(self._dir_path, ignore_errors=True)

    async def start_test(self, handler, test_step, timeout):
        observer = watch.Observer()

        async def prepare():
            watcher = observer.new_watcher(handler)
            observer.add_watcher(self._dir_path, watcher)
            await observer.start(0.1)

        def stop():
            observer.stop_non_immediately()

        async def test_step_wrap():
            await test_step()
            stop()

        await self.start_test_with_timeout(test_step_wrap, stop, timeout,
                                           prepare())

    async def test_create_file(self):
        test_path = os.path.join(self._dir_path, 'test.txt')

        def handler(events):
            self.assertSetEqual(
                set(events),
                set([
                    watchdog.events.FileCreatedEvent(test_path),
                    watchdog.events.DirModifiedEvent(self._dir_path)
                ]))

        async def test_step():
            logger.debug('test path: %s', test_path)
            await asyncio.sleep(0.05)
            touch(test_path)

        await self.start_test(handler, test_step, 0.2)

    async def test_delete_file(self):
        test_path = os.path.join(self._dir_path, 'test.txt')

        touch(test_path)

        def handler(events):
            self.assertSetEqual(
                set(events),
                set([
                    watchdog.events.FileDeletedEvent(test_path),
                    watchdog.events.DirModifiedEvent(self._dir_path)
                ]))

        async def test_step():
            logger.debug('test path: %s', test_path)
            await asyncio.sleep(0.05)
            os.remove(test_path)

        await self.start_test(handler, test_step, 0.2)

    async def test_rename_file(self):
        test_path1 = os.path.join(self._dir_path, 'test1.txt')
        test_path2 = os.path.join(self._dir_path, 'test2.txt')

        pathlib.Path(test_path1).touch()

        def handler(events):
            self.assertSetEqual(
                set(events),
                set([
                    watchdog.events.FileMovedEvent(test_path1, test_path2),
                    watchdog.events.DirModifiedEvent(self._dir_path)
                ]))

        async def test_step():
            logger.debug('test path: %s', test_path1)
            await asyncio.sleep(0.05)
            os.rename(test_path1, test_path2)

        await self.start_test(handler, test_step, 0.2)

    async def test_rename_dir(self):
        test_dir1 = os.path.join(self._dir_path, 'test_dir1')
        test_dir2 = os.path.join(self._dir_path, 'test_dir2')
        test_sub_dir = 'test_sub_dir'
        test_path1 = os.path.join(test_dir1, test_sub_dir, 'test.txt')
        test_path2 = os.path.join(test_dir2, test_sub_dir, 'test.txt')

        def handler(events):
            print(events)
            self.assertIn(watchdog.events.DirCreatedEvent(test_dir2), events)
            self.assertIn(watchdog.events.DirMovedEvent(test_dir1, test_dir2),
                          events)
            self.assertIn(
                watchdog.events.DirMovedEvent(os.path.dirname(test_path1),
                                              os.path.dirname(test_path2)),
                events)
            self.assertIn(
                watchdog.events.FileMovedEvent(test_path1, test_path2), events)

        async def test_step():
            await asyncio.sleep(0.05)
            os.makedirs(os.path.join(test_dir1, test_sub_dir))
            pathlib.Path(test_path1).touch()
            os.rename(test_dir1, test_dir2)

        await self.start_test(handler, test_step, 0.4)

    async def test_create_rename_delete(self):
        test_dir1 = os.path.join(self._dir_path, 'test_dir1')
        test_dir2 = os.path.join(self._dir_path, 'test_dir2')
        test_sub_dir = 'test_sub_dir'
        test_path1 = os.path.join(test_dir1, test_sub_dir, 'test.txt')
        test_path2 = os.path.join(test_dir2, test_sub_dir, 'test.txt')

        def handler(events):
            self.assertNotIn(watchdog.events.DirCreatedEvent(test_path1),
                             events)
            self.assertNotIn(watchdog.events.DirCreatedEvent(test_path2),
                             events)
            self.assertNotIn(watchdog.events.DirDeletedEvent(test_path2),
                             events)

        async def test_step():
            await asyncio.sleep(0.05)
            os.makedirs(os.path.join(test_dir1, test_sub_dir))
            pathlib.Path(test_path1).touch()
            # TODO: sometimes missing event on new creating folder
            # because observer was created after event happended
            await asyncio.sleep(0.1)
            os.rename(test_dir1, test_dir2)
            os.remove(test_path2)

        await self.start_test(handler, test_step, 0.5)


def _touch_and_return_path_task_pair(*paths):
    def task(root):
        path = os.path.join(root, *paths)
        touch(path)
        logger.debug('Test touch %s', path)
        return path

    return task, False


def _mkdir_and_return_path_task_pair(*paths):
    def task(root):
        path = os.path.join(root, *paths)
        os.mkdir(path)
        logger.debug('Test mkdir %s', path)
        return path

    return task, True


def _rm_and_return_path_task_pair(*paths, is_dir=True):
    def task(root):
        path = os.path.join(root, *paths)
        shutil.rmtree(path)
        return path

    return task, is_dir


def _move_and_return_path_task_pair(src_paths, dest_paths, is_dir):
    def task(root):
        src_path = os.path.join(root, *src_paths)
        dest_path = os.path.join(root, *dest_paths)
        logger.debug('Test %s %s', src_path, dest_path)
        os.rename(src_path, dest_path)
        return dest_path

    return task, is_dir


class TestCheckLossDiff(WatchTestUtil):
    maxDiff = None

    def setUp(self):
        self._src_dir = mk_tmp_dir()
        self._dest_dir = mk_tmp_dir()
        logger.debug('src_dir=%s, dest_dir=%s', self._src_dir, self._dest_dir)

    def tearDown(self):
        shutil.rmtree(self._src_dir, ignore_errors=True)
        shutil.rmtree(self._dest_dir, ignore_errors=True)

    def test_equal(self):
        for task, _ in self.create_dir_file_tasks:
            task(self._src_dir)
            task(self._dest_dir)

        diff_dirs, diff_files = watch.get_loss_diff(self._src_dir,
                                                    self._dest_dir)
        self.assertListEqual(diff_dirs, [])
        self.assertListEqual(diff_files, [])

    def test_not_equal(self):
        for task, is_dir in self.create_dir_file_tasks:
            path = task(self._src_dir)
            sub_path = os.path.relpath(path, self._src_dir)
            with self.subTest(path=path):
                diff_dirs, diff_files = watch.get_loss_diff(
                    self._src_dir, self._dest_dir)
                self.assertListEqual(diff_dirs, [sub_path] if is_dir else [])
                self.assertListEqual(diff_files, [] if is_dir else [sub_path])

            task(self._dest_dir)

    async def test_create_folder_and_file_step(self):
        await self.check_folder_mirror_by_step(self.create_dir_file_tasks, 1)

    async def test_move_folder_step(self):
        await self.check_folder_mirror_by_step(self.create_move_dir_tasks, 1)

    async def test_remove_folder_step(self):
        await self.check_folder_mirror_by_step(self.create_move_dir_tasks, 1)

    async def test_create_folder_and_file_total(self):
        await self.check_folder_mirror_total(self.create_dir_file_tasks)

    async def test_move_folder_total(self):
        await self.check_folder_mirror_total(self.create_move_dir_tasks)

    async def test_remove_folder_total(self):
        await self.check_folder_mirror_total(self.create_move_dir_tasks)

    async def check_folder_mirror_by_step(self, tasks, task_sleep=1):
        monitor = watch.FolderMirrorMonitor()
        monitor.add_mirror_pair(self._src_dir, [self._dest_dir])

        def stop():
            monitor.stop_non_immediately()

        async def test_step():
            await asyncio.sleep(0.1)
            for task, _ in tasks:
                path = task(self._src_dir)
                await asyncio.sleep(task_sleep)
                with self.subTest(path=path):
                    diff_dirs, diff_files = watch.get_loss_diff(
                        self._src_dir, self._dest_dir, check_inode=True)
                    self.assertListEqual(diff_dirs, [])
                    self.assertListEqual(diff_files, [])
            stop()

        await self.start_test_with_timeout(test_step, stop, 10,
                                           monitor.start(0.1))

    async def check_folder_mirror_total(self, tasks):
        monter = watch.FolderMirrorMonitor()
        monter.add_mirror_pair(self._src_dir, [self._dest_dir])

        def stop():
            monter.stop_non_immediately()

        async def test_step():
            await asyncio.sleep(0.1)
            for task, _ in tasks:
                task(self._src_dir)

            await asyncio.sleep(1)
            diff_dirs, diff_files = watch.get_loss_diff(self._src_dir,
                                                        self._dest_dir,
                                                        check_inode=True)
            self.assertListEqual(diff_dirs, [])
            self.assertListEqual(diff_files, [])
            stop()

        await self.start_test_with_timeout(test_step, stop, 10,
                                           monter.start(0.1))

    @property
    def create_dir_file_tasks(self):
        dir1 = 'test1'
        dir2 = 'test2'
        return [
            _touch_and_return_path_task_pair('test_file'),
            _mkdir_and_return_path_task_pair(dir1),
            _touch_and_return_path_task_pair(dir1, 'test_file'),
            _mkdir_and_return_path_task_pair(dir1, dir2),
            _touch_and_return_path_task_pair(dir1, dir2, 'test_file'),
        ]

    @property
    def create_move_dir_tasks(self):
        before_dir = 'dir1'
        after_dir = 'dir2'
        return [
            _mkdir_and_return_path_task_pair(before_dir),
            _touch_and_return_path_task_pair(before_dir, 'test_file'),
            _move_and_return_path_task_pair([before_dir], [after_dir], True),
        ]

    @property
    def create_move_dir_tasks(self):
        dir_path = 'dir1'
        return [
            _mkdir_and_return_path_task_pair(dir_path),
            _touch_and_return_path_task_pair(dir_path, 'test_file'),
            _rm_and_return_path_task_pair(dir_path, is_dir=True),
        ]