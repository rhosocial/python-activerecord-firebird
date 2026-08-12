# src/rhosocial/activerecord/testsuite/feature/basic/transaction/test_async_owner_task.py
"""Async contracts for `AsyncTransactionManager._owner_task` safety warning.

`AsyncTransactionManager.transaction()` (python-activerecord
`backend/transaction.py:879-943`) tracks which asyncio task currently
owns an active outermost transaction. When a second task enters
`transaction()` on the same backend instance while another task holds
an active outermost transaction, it MUST emit `UserWarning` with a fixed
message text (line 906-915).

The `_owner_task` lifecycle is bound to `backend.transaction_manager.transaction()`
only. `pool.transaction()` calls `begin_transaction()` / `commit_transaction()`
directly (sync_pool.py:574-576 / async_pool.py:613-615) and does NOT
participate in `_owner_task` tracking. Therefore these tests operate
directly on `backend.transaction_manager` rather than through
`pool.transaction()`.

Coverage:
- T1 single task nested transaction does not emit warning
- T2 a different task entering while an outer is active emits warning
- T3 warning message text is stable (for log-grep filters)
- T4 owner_task is cleared after outermost transaction exits cleanly
- T5 same task re-entering after clean exit re-acquires ownership
"""
import asyncio
import warnings

import pytest


@pytest.fixture
async def mgr_and_backend(async_pool_and_model):
    """Acquire a backend via pool.connection() and yield (backend, mgr).

    Mechanism note: we stub `_do_begin / _do_commit / _do_rollback /
    _do_create_savepoint / _do_release_savepoint / _do_rollback_savepoint`
    on the async transaction manager with no-ops, because the
    `_owner_task` warning branch fires *before* `_do_begin()` is awaited
    (transaction.py:905-915 runs synchronously at context-manager entry,
    only then does `await self.begin()` execute). Stubbing the I/O layer
    lets us exercise the pure state machine — including concurrent
    multi-task execution on a real asyncio event loop — without dragging
    in SQLite's thread-affinity rules, which otherwise cause spurious
    "cannot start a transaction within a transaction" when a second
    task reuses the same aiosqlite connection.
    """
    pool, _model = async_pool_and_model
    cm = pool.connection()
    backend = await cm.__aenter__()
    mgr = backend.transaction_manager

    async def _noop(*args, **kwargs):
        return None

    mgr._do_begin = _noop
    mgr._do_commit = _noop
    mgr._do_rollback = _noop
    mgr._do_create_savepoint = _noop
    mgr._do_release_savepoint = _noop
    mgr._do_rollback_savepoint = _noop

    try:
        yield backend, mgr
    finally:
        try:
            await cm.__aexit__(None, None, None)
        except Exception:
            pass


class TestAsyncOwnerTaskNoWarningSameTask:
    async def test_same_task_nested_transaction_no_warning(self, mgr_and_backend):
        _backend, mgr = mgr_and_backend
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            async with mgr.transaction():
                async with mgr.transaction():
                    pass

    async def test_same_task_reentry_after_clean_exit_no_warning(self, mgr_and_backend):
        _backend, mgr = mgr_and_backend
        async with mgr.transaction():
            pass
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            async with mgr.transaction():
                pass


class TestAsyncOwnerTaskCrossTaskWarning:
    async def test_cross_task_share_emits_user_warning(self, mgr_and_backend):
        """A different task entering transaction() during an active outer
        transaction owned by another task MUST emit UserWarning.

        Per backend/transaction.py:906-915, the branch fires when:
            self._owner_task is not None and self._owner_task is not current_task
        It does NOT raise, so the second task can still proceed - the
        system is telling the developer to fix their code.
        """
        _backend, mgr = mgr_and_backend

        outer_started = asyncio.Event()
        proceed = asyncio.Event()

        async def owner():
            async with mgr.transaction():
                outer_started.set()
                await proceed.wait()

        async def second_task(caught):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                async with mgr.transaction():
                    pass
            caught.extend(captured)

        caught = []
        owner_task = asyncio.create_task(owner())
        second_t = asyncio.create_task(second_task(caught))
        # Let owner enter its outer transaction first.
        await asyncio.wait_for(outer_started.wait(), timeout=5.0)
        # Yield once so second task enters transaction() and emits warning.
        await asyncio.sleep(0.05)
        proceed.set()
        await asyncio.gather(owner_task, second_t)

        user_warnings = [w for w in caught if issubclass(w.category, UserWarning)]
        assert user_warnings, "expected a UserWarning about shared backend"

    async def test_cross_task_warning_message_is_stable(self, mgr_and_backend):
        _backend, mgr = mgr_and_backend

        outer_started = asyncio.Event()
        proceed = asyncio.Event()

        async def owner():
            async with mgr.transaction():
                outer_started.set()
                await proceed.wait()

        async def second_task(caught):
            with warnings.catch_warnings(record=True) as captured:
                warnings.simplefilter("always")
                async with mgr.transaction():
                    pass
            caught.extend(captured)

        caught = []
        owner_task = asyncio.create_task(owner())
        second_t = asyncio.create_task(second_task(caught))
        await asyncio.wait_for(outer_started.wait(), timeout=5.0)
        await asyncio.sleep(0.05)
        proceed.set()
        await asyncio.gather(owner_task, second_t)

        msgs = [str(w.message) for w in caught if issubclass(w.category, UserWarning)]
        assert msgs, "no UserWarning captured"
        expected = (
            "Shared async backend instance detected: a different async task "
            "already holds an active transaction on this backend. Concurrent "
            "use of the same backend instance across tasks can lead to "
            "transaction state inconsistency. Use separate backend instances "
            "per task or ensure serialized access."
        )
        assert msgs[0] == expected


class TestAsyncOwnerTaskLifecycle:
    async def test_owner_task_cleared_after_outermost_exits(self, mgr_and_backend):
        """After a clean outermost commit, _owner_task MUST reset to None.

        Per backend/transaction.py:941-943:
            if not self.is_active:
                self._owner_task = None
        """
        _backend, mgr = mgr_and_backend
        async with mgr.transaction():
            assert mgr.is_active
            async with mgr.transaction():
                pass
        assert mgr._owner_task is None

    async def test_owner_task_cleared_after_outermost_rolls_back(self, mgr_and_backend):
        _backend, mgr = mgr_and_backend
        with pytest.raises(RuntimeError):
            async with mgr.transaction():
                async with mgr.transaction():
                    raise RuntimeError("force rollback")
        assert mgr._owner_task is None

    async def test_owner_task_reacquired_by_same_task_after_clean_exit(self, mgr_and_backend):
        """After clean reset, the same task re-entering does not warn and
        re-acquires ownership (line 916-917)."""
        _backend, mgr = mgr_and_backend
        async with mgr.transaction():
            async with mgr.transaction():
                pass
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            async with mgr.transaction():
                pass
