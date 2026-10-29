"""两个 API 客户端共用的 HTTP 重试与响应体积策略（仅标准库）。

``opencode_api`` / ``commandcode_api`` 的重试骨架逐行同构，但策略细节各写一份就会
漂移（一边重试确定性 400、另一边忽略 429 的 Retry-After）。这里只收敛**纯策略**：

- 哪些状态码可重试：5xx / 408 / 425 / 429；
- ``Retry-After`` 解析（整数秒或 HTTP-date）与等待上限；
- 退避时长；
- 响应体有界读取（``read(MAX+1)`` 判截断，不只看 ``Content-Length`` —— chunked
  响应没有该头，只信它会让超限响应被静默截断后误报成「JSON 非法」）。

异常类型映射（401/403 各自语义不同）仍留在各客户端：本模块不 import 任何客户端，
避免循环依赖。
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Optional

# 第 1/2/3 次重试前的等待基数（秒）；Retry-After 优先于它
RETRY_BACKOFF = (0.5, 1.5, 3.0)
# 上游 Retry-After 常给 30/60s，按原值等会把后台同步/更新检查卡死；封顶 10s
MAX_RETRY_AFTER_SEC = 10.0
# 可以安全重试的 4xx：请求超时/过早/限流；400/404/410/422 是确定性失败，重试无意义
_RETRYABLE_CLIENT_STATUS = frozenset({408, 425, 429})


class ResponseTooLarge(Exception):
    """响应体超过客户端允许的上限（Content-Length 声明或实际读取值超限）。"""


def is_retryable_status(status: int) -> bool:
    """HTTP 状态码是否值得重试（5xx 与 408/425/429）。"""
    return status >= 500 or status in _RETRYABLE_CLIENT_STATUS


def retry_after_seconds(headers: Any) -> Optional[float]:
    """解析 ``Retry-After`` 响应头，返回 [0, MAX_RETRY_AFTER_SEC] 秒。

    支持两种合法形态：整数秒（"30"）与 HTTP-date（"Wed, 21 Oct 2026 07:28:00 GMT"）。
    缺失/非法返回 None（调用方回退指数退避）。
    """
    if headers is None:
        return None
    try:
        raw = headers.get("Retry-After")
    except AttributeError:  # 极少数自定义 headers 对象没有 get
        return None
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        seconds = float(text)
    except ValueError:
        try:
            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError):
            return None
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        seconds = (dt - datetime.now(timezone.utc)).total_seconds()
    return max(0.0, min(MAX_RETRY_AFTER_SEC, seconds))


def retry_delay(attempt: int, headers: Any = None) -> float:
    """第 ``attempt`` 次重试（0 起）前的等待秒数：Retry-After 优先，否则指数退避。"""
    after = retry_after_seconds(headers)
    if after is not None:
        return after
    return RETRY_BACKOFF[min(max(0, attempt), len(RETRY_BACKOFF) - 1)]


def read_body(resp: Any, max_bytes: int) -> bytes:
    """有界读取响应体；超限抛 :class:`ResponseTooLarge`。

    先看 ``Content-Length`` 快速失败（避免白下载），再按 ``max_bytes + 1`` 读取：
    多读一个字节即可区分「恰好等于上限」与「被截断」，因此 chunked/无长度头的
    响应也能给出「响应过大」而不是后续的 JSON 解析错误。
    """
    headers = getattr(resp, "headers", None)
    declared = (headers.get("Content-Length") if headers is not None else "") or ""
    if str(declared).isdigit() and int(declared) > max_bytes:
        raise ResponseTooLarge(
            f"响应过大 ({int(declared)} 字节, 上限 {max_bytes} 字节)")
    body = resp.read(max_bytes + 1)
    if len(body) > max_bytes:
        raise ResponseTooLarge(f"响应过大 (超过 {max_bytes} 字节)")
    return body
