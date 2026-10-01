package io.github.yphyphyph.gogauge.auth

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * 登录自愈判定的纯函数单测 — 用例与桌面回归 (tests/test_windows_login.py +
 * tests/test_auth_login.py) 一一对应, 保证两端语义一致.
 */
class LoginTest {

    // ------------------------------------------------------------------
    // 登录入口偏离 (commandcode 被残留会话带离 /signin)
    // ------------------------------------------------------------------

    @Test
    fun `entry lost flags only commandcode pages off signin`() {
        assertEquals(false, Login.isOffLoginEntry("https://commandcode.ai/signin", "commandcode"))
        assertEquals(false, Login.isOffLoginEntry("https://commandcode.ai/signin?next=%2F", "commandcode"))
        assertEquals(true, Login.isOffLoginEntry("https://commandcode.ai/", "commandcode"))
        assertEquals(true, Login.isOffLoginEntry("https://commandcode.ai/dashboard", "commandcode"))
        // 授权流程在别的域
        assertEquals(false, Login.isOffLoginEntry("https://github.com/login?client_id=x", "commandcode"))
        // OAuth 成功回调 (带 code=): 服务端正要据此种会话, 不得判偏离清会话
        assertEquals(
            false,
            Login.isOffLoginEntry("https://commandcode.ai/api/auth/callback/github?code=abc&state=st", "commandcode"),
        )
        // 失败回调 (error= 不带 code=): 清会话拉回登录页正是期望行为
        assertEquals(true, Login.isOffLoginEntry("https://commandcode.ai/auth/github?error=access_denied", "commandcode"))
        assertEquals(false, Login.isOffLoginEntry("about:blank", "commandcode"))
        assertEquals(false, Login.isOffLoginEntry("", "commandcode"))
    }

    @Test
    fun `entry lost ignores other providers`() {
        // opencode 的 OAuth 会合法地跨域跨路径, 不做判定
        assertFalse(Login.isOffLoginEntry("https://opencode.ai/workspace/wrk_1", "opencode"))
        assertFalse(Login.isOffLoginEntry("https://opencode.ai/console", null))
    }

    // ------------------------------------------------------------------
    // GitHub 页面分类
    // ------------------------------------------------------------------

    @Test
    fun `classify github entry flow and stuck`() {
        assertEquals("entry", Login.classifyGithubUrl("https://github.com/login?client_id=Ov23li&return_to=%2F"))
        assertEquals("entry", Login.classifyGithubUrl("https://github.com/login/oauth/authorize?client_id=abc&state=s"))
        assertEquals("flow", Login.classifyGithubUrl("https://github.com/login"))
        assertEquals("flow", Login.classifyGithubUrl("https://github.com/login?return_to=x"))
        assertEquals("flow", Login.classifyGithubUrl("https://github.com/sessions/two-factor"))
        assertEquals("stuck", Login.classifyGithubUrl("https://github.com/settings/security"))
        assertEquals("stuck", Login.classifyGithubUrl("https://github.com/"))
        assertNull(Login.classifyGithubUrl("https://github.com.evil.example/login?client_id=x"))
        assertNull(Login.classifyGithubUrl("https://example.com/"))
        assertNull(Login.classifyGithubUrl(""))
    }

    // ------------------------------------------------------------------
    // authorize URL 提取与规范化
    // ------------------------------------------------------------------

    @Test
    fun `authorize url from mixed decoded return_to`() {
        // 复刻打包版实测失败场景: return_to 路径已解码, 但 redirect_uri 双重编码
        val entry = "https://github.com/login?client_id=Ov23lilNxFR08yhwthpz" +
            "&return_to=/login/oauth/authorize?client_id=Ov23lilNxFR08yhwthpz" +
            "&code_challenge=CAmwEOrlEO2NgvdoKmAuDeFLxAxfLXaSQfv99-D2tXQ" +
            "&code_challenge_method=S256&prompt=select_account" +
            "&redirect_uri=https%253A%252F%252Fopencode.ai%252Fconsole%252Fauth%252Fsocial%252Fgithub%252Fcallback" +
            "&response_type=code&scope=read%3Auser+user%3Aemail&state=st_flow"
        val url = Login.authorizeUrlFromEntry(entry)
        requireNotNull(url)
        // redirect_uri 必须被解回真实回调地址 (单层编码), GitHub 才能匹配注册回调
        assertTrue(url.contains("redirect_uri=https%3A%2F%2Fopencode.ai%2Fconsole%2Fauth%2Fsocial%2Fgithub%2Fcallback"))
        assertFalse(url.contains("https%253A"))  // 不允许残留双重编码
        assertFalse(url.contains("prompt=select_account"))
        assertTrue(url.contains("client_id=Ov23lilNxFR08yhwthpz"))
        assertTrue(url.contains("code_challenge=CAmwEOrlEO2NgvdoKmAuDeFLxAxfLXaSQfv99-D2tXQ"))
        assertTrue(url.contains("state=st_flow"))
    }

    @Test
    fun `double encoded return_to is fully unwrapped`() {
        val entry = "https://github.com/login?client_id=Ov23lilNxFR08yhwthpz" +
            "&return_to=%2Flogin%2Foauth%2Fauthorize%3Fclient_id%3DOv23lilNxFR08yhwthpz" +
            "%26code_challenge%3D2r5S_XcVYr8tvyeVjxwDjBBJ65GB6U4xi9v3eObkeUY" +
            "%26code_challenge_method%3DS256%26prompt%3Dselect_account" +
            "%26redirect_uri%3Dhttps%253A%252F%252Fopencode.ai%252Fauth%252Fsocial%252Fgithub%252Fcallback" +
            "%26state%3Dst_xxx"
        val url = Login.authorizeUrlFromEntry(entry)
        requireNotNull(url)
        assertTrue(url.startsWith("https://github.com/login/oauth/authorize?"))
        assertTrue(url.contains("client_id=Ov23lilNxFR08yhwthpz"))
        assertTrue(url.contains("code_challenge=2r5S_XcVYr8tvyeVjxwDjBBJ65GB6U4xi9v3eObkeUY"))
        assertTrue(url.contains("code_challenge_method=S256"))
        assertTrue(url.contains("redirect_uri=https%3A%2F%2Fopencode.ai%2Fauth%2Fsocial%2Fgithub%2Fcallback"))
        assertTrue(url.contains("state=st_xxx"))
        assertFalse(url.contains("prompt=select_account"))
    }

    @Test
    fun `normalize keeps already single-encoded values`() {
        // 普通已编码值保持原样, 不会多解一层 (加号/冒号语义不变)
        val url = Login.normalizeAuthorizeTarget(
            "/login/oauth/authorize?client_id=abc" +
                "&redirect_uri=https%3A%2F%2Fopencode.ai%2Fcb&scope=read%3Auser+user%3Aemail"
        )
        requireNotNull(url)
        assertTrue(url.contains("redirect_uri=https%3A%2F%2Fopencode.ai%2Fcb"))
        assertTrue(url.contains("scope=read%3Auser+user%3Aemail"))
    }

    @Test
    fun `authorize url from raw return_to and direct passthrough`() {
        val raw = "https://github.com/login?client_id=abc" +
            "&return_to=/login/oauth/authorize?client_id=abc&code_challenge=xy&state=st"
        assertEquals(
            "https://github.com/login/oauth/authorize?client_id=abc&code_challenge=xy&state=st",
            Login.authorizeUrlFromEntry(raw),
        )
        val direct = "https://github.com/login/oauth/authorize?client_id=abc&state=st"
        assertEquals(direct, Login.authorizeUrlFromEntry(direct))
    }

    @Test
    fun `authorize url missing entry or client id returns null`() {
        assertNull(Login.authorizeUrlFromEntry(""))
        assertNull(Login.authorizeUrlFromEntry(null))
        assertNull(Login.authorizeUrlFromEntry("https://github.com/settings/security"))
        // 缺 client_id 的 authorize 目标不可续跑 (GitHub 会拒绝)
        assertNull(Login.normalizeAuthorizeTarget("/login/oauth/authorize?state=st"))
    }

    // ------------------------------------------------------------------
    // commandcode 登录 URL / cookie 提取 (回归: 既有语义不受本次改动影响)
    // ------------------------------------------------------------------

    @Test
    fun `commandcode login url is the signin entry`() {
        assertEquals("https://commandcode.ai/signin", Login.buildLoginUrl("commandcode"))
    }
}
