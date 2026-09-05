package io.github.yphyphyph.gogauge.data.db

import kotlinx.coroutines.sync.Mutex

/**
 * settings payload 整包 JSON 读-改-写的全局互斥 — desktop db._payload_lock parity.
 *
 * payload 是单行整包 JSON: SyncDao (active_account_id) 与 SettingsDao (设置项 /
 * key_names / monthly_reset) 各自读改写, 并发改不同键时无锁会互相覆盖丢键
 * (active_account_id 回退 / key_names 丢失). 所有写侧必须经此锁.
 */
internal object PayloadLock {
    val mutex = Mutex()
}
