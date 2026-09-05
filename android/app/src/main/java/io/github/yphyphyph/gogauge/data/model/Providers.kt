package io.github.yphyphyph.gogauge.data.model

/** 账号来源 (desktop db.py PROVIDER_* parity)。 */
const val PROVIDER_OPENCODE = "opencode"
const val PROVIDER_COMMANDCODE = "commandcode"

/**
 * 新账号默认显示名 — desktop db.add_account 命名规则 parity:
 * opencode 有工作区提示时以提示命名 (截断 50), commandcode 命名 GOAT N, 其余 User N。
 */
fun accountDisplayName(provider: String, hint: String, id: Int): String = when {
    hint.isNotBlank() && provider == PROVIDER_OPENCODE -> hint.trim().take(50)
    provider == PROVIDER_COMMANDCODE -> "GOAT $id"
    else -> "User $id"
}
