package io.github.yphyphyph.gogauge.util

import android.content.ComponentName
import android.content.Context
import android.content.pm.PackageManager
import io.github.yphyphyph.gogauge.data.model.IconStyle

/**
 * Android 启动器图标切换 — activity-alias 互斥启停 (v2.2.2d)。
 *
 * MainActivity 不再直接挂 LAUNCHER intent-filter; AndroidManifest.xml 里声明两个
 * 指向同一 targetActivity 的 alias:
 *  - [ALIAS_BLUE]       默认启用, icon=@mipmap/ic_launcher_blue
 *  - [ALIAS_TERRACOTTA] 默认禁用, icon=@mipmap/ic_launcher_terracotta
 *
 * 切换顺序: **先启用目标 alias, 再禁用另一个**。不能反序 —— 反序若中途失败会
 * 出现两个 alias 同时被禁用, 桌面入口彻底消失 (只能从系统设置或 adb 再打开 App)。
 * 使用 [PackageManager.DONT_KILL_APP] 保证切换不杀进程。
 *
 * 桌面图标短暂消失/重现属正常现象; 部分第三方桌面刷新有延迟 (甚至需重启桌面)。
 * 设置保存后 (MainViewModel.saveSettings) 与 App 启动时 (GoGaugeApp.onCreate)
 * 都会调用 [apply] 校正状态, 防止外部状态漂移 (系统设置 / adb / 桌面缓存)。
 */
object LauncherIcon {

    /** 品牌蓝 alias — AndroidManifest.xml 中默认 android:enabled="true"。 */
    const val ALIAS_BLUE = "LauncherBlue"

    /** 陶土橙 alias — AndroidManifest.xml 中默认 android:enabled="false"。 */
    const val ALIAS_TERRACOTTA = "LauncherTerracotta"

    /**
     * 按持久化风格校正启动器图标启用状态 (幂等: 状态已正确时不产生系统调用)。
     *
     * 只处理本应用自己的组件, 无需 CHANGE_COMPONENT_ENABLED_STATE 权限。
     *
     * @param style settings 的 `icon_style` 值; 非法值按 blue 处理。
     */
    fun apply(context: Context, style: String) {
        val terracotta = IconStyle.normalize(style) == IconStyle.TERRACOTTA
        val pm = context.packageManager
        val target = component(context, if (terracotta) ALIAS_TERRACOTTA else ALIAS_BLUE)
        val other = component(context, if (terracotta) ALIAS_BLUE else ALIAS_TERRACOTTA)
        // manifest 默认值: 蓝 alias enabled=true, 陶土橙 alias enabled=false
        val targetManifestDefault = !terracotta
        val otherManifestDefault = terracotta
        try {
            // 1) 先启用目标: 保证任意时刻至少一个 LAUNCHER 入口可用
            if (!isEnabled(pm, target, targetManifestDefault)) {
                pm.setComponentEnabledSetting(
                    target,
                    PackageManager.COMPONENT_ENABLED_STATE_ENABLED,
                    PackageManager.DONT_KILL_APP,
                )
            }
            // 2) 再禁用另一个 alias
            if (isEnabled(pm, other, otherManifestDefault)) {
                pm.setComponentEnabledSetting(
                    other,
                    PackageManager.COMPONENT_ENABLED_STATE_DISABLED,
                    PackageManager.DONT_KILL_APP,
                )
            }
        } catch (e: Exception) {
            // 个别 ROM 可能拒绝组件状态变更: 切换失败不应影响设置落库/启动流程,
            // 记日志后留给下次启动校正即可。
            android.util.Log.w("GoGauge", "launcher icon switch failed (style=$style)", e)
        }
    }

    /** 读取当前 alias 的实际启用状态 (调试/排障用)。 */
    fun isAliasEnabled(context: Context, alias: String): Boolean {
        val terracotta = alias == ALIAS_TERRACOTTA
        return isEnabled(context.packageManager, component(context, alias), manifestDefault = !terracotta)
    }

    private fun component(context: Context, alias: String): ComponentName =
        ComponentName(context.packageName, "${context.packageName}.$alias")

    /**
     * 当前 alias 是否启用; COMPONENT_ENABLED_STATE_DEFAULT 表示沿用 manifest 中
     * android:enabled 的默认值 ([manifestDefault])。
     */
    private fun isEnabled(pm: PackageManager, component: ComponentName, manifestDefault: Boolean): Boolean =
        when (pm.getComponentEnabledSetting(component)) {
            PackageManager.COMPONENT_ENABLED_STATE_ENABLED -> true
            PackageManager.COMPONENT_ENABLED_STATE_DEFAULT -> manifestDefault
            // DISABLED / DISABLED_USER / DISABLED_UNTIL_USED 均视为未启用
            else -> false
        }
}
