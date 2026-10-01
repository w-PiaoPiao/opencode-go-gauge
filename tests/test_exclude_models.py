"""模型排除过滤链路测试: 统计页环形图图例点击隐藏模型后, 顶部总卡 / Token 构成 /
趋势必须按排除后的口径聚合; models 保持全量 (环形图保留被排除模型以便图例点击加回),
排行由前端按 excluded_models 过滤 (db 聚合层 + dashboard 路由透传)."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pytest

from app import db, server
from app.db import PROVIDER_COMMANDCODE


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "data_dir", lambda: str(tmp_path))
    yield tmp_path
    db.close_db()


@pytest.fixture()
def http(tmp_db):
    host, port = server.start_server("127.0.0.1", 0)
    yield f"http://{host}:{port}"
    server.stop_server()


def _get(url: str):
    with urllib.request.urlopen(url, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8")), resp.status


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _rec(usg_id: str, model: str, *, inp=100, out=10, cache_read=0, cost=0.01) -> dict:
    return {
        "usg_id": usg_id,
        "created_at": _now_iso(),
        "model": model,
        "input_tokens": inp,
        "output_tokens": out,
        "reasoning_tokens": 0,
        "cache_read_tokens": cache_read,
        "cache_write_5m_tokens": 0,
        "cache_write_1h_tokens": 0,
        "cost_raw": 0,
        "cost_usd": cost,
        "session_id": "s1",
    }


def _seed_records() -> None:
    """model-a 两条 (一条命中缓存) / model-b 一条, 均为今天."""
    db.insert_usage_records([
        _rec("u1", "model-a", inp=100, out=10, cache_read=50, cost=0.10),
        _rec("u2", "model-a", inp=200, out=20, cache_read=0, cost=0.20),
        _rec("u3", "model-b", inp=300, out=30, cache_read=30, cost=0.30),
    ])


def _seed_charts() -> None:
    """切到 commandcode 账号并写入 charts 聚合行 (统计走 charts 数据源)."""
    conn = db.get_db()
    conn.execute("UPDATE accounts SET provider = ? WHERE id = 1", (PROVIDER_COMMANDCODE,))
    conn.commit()
    db.insert_usage_charts([
        {"model": "goat-a", "provider": PROVIDER_COMMANDCODE, "time_bucket": _now_iso(),
         "requests": 2, "tokens_in": 1000, "tokens_out": 100, "cache_read_tokens": 400,
         "cache_creation_tokens": 50, "total_cost": 0.5},
        {"model": "goat-b", "provider": PROVIDER_COMMANDCODE, "time_bucket": _now_iso(),
         "requests": 1, "tokens_in": 2000, "tokens_out": 200, "cache_read_tokens": 0,
         "cache_creation_tokens": 0, "total_cost": 0.8},
    ])


class TestRecordsSource:
    def test_totals_excludes_model(self, tmp_db):
        _seed_records()
        base = db.totals("30d")
        assert base["request_count"] == 3 and base["total_cost_usd"] == pytest.approx(0.6)
        filtered = db.totals("30d", None, ["model-a"])
        assert filtered["request_count"] == 1
        assert filtered["total_cost_usd"] == pytest.approx(0.30)
        assert filtered["total_input_tokens"] == 330  # model-b: 300 未命中 + 30 缓存读
        assert filtered["uncached_input_tokens"] == 300
        assert filtered["cache_hit_tokens"] == 30
        assert filtered["total_output_tokens"] == 30

    def test_model_stats_always_full(self, tmp_db):
        # 回归防护: model_stats 不得接受排除过滤 (环形图要靠全量数据画图例删除线)
        _seed_records()
        stats = db.model_stats("30d")
        assert sorted(m["model"] for m in stats) == ["model-a", "model-b"]

    def test_daily_stats_excludes_model(self, tmp_db):
        _seed_records()
        base = next(r for r in db.daily_stats(30) if r["date"] == _today())
        assert base["request_count"] == 3
        filtered = next(r for r in db.daily_stats(30, None, ["model-a"]) if r["date"] == _today())
        assert filtered["request_count"] == 1
        assert filtered["total_cost_usd"] == pytest.approx(0.30)

    def test_totals_blank_and_duplicate_excludes_ignored(self, tmp_db):
        _seed_records()
        assert db.totals("30d", None, ["", "  ", "model-a", "model-a"]) == db.totals("30d", None, ["model-a"])

    def test_injection_string_matches_literal(self, tmp_db):
        _seed_records()
        # 排除项走参数化占位符: 注入串按字面量匹配, 不会命中任何记录 (等价于不排除)
        injected = db.totals("30d", None, ["model-a' OR '1'='1"])
        assert injected["request_count"] == 3


class TestChartsSource:
    def test_charts_totals_exclude(self, tmp_db):
        _seed_charts()
        filtered = db.totals("30d", None, ["goat-a"])
        assert filtered["request_count"] == 1
        assert filtered["total_cost_usd"] == pytest.approx(0.8)
        assert filtered["total_input_tokens"] == 2000  # charts 的 tokens_in 已含缓存读
        assert filtered["uncached_input_tokens"] == 2000
        assert filtered["cache_hit_tokens"] == 0
        assert filtered["total_output_tokens"] == 200

    def test_charts_model_stats_always_full(self, tmp_db):
        _seed_charts()
        stats = db.model_stats("30d")
        assert sorted(m["model"] for m in stats) == ["goat-a", "goat-b"]

    def test_charts_daily_stats_exclude(self, tmp_db):
        _seed_charts()
        row = next(r for r in db.daily_stats(30, None, ["goat-b"]) if r["date"] == _today())
        assert row["request_count"] == 2
        assert row["total_cost_usd"] == pytest.approx(0.5)


class TestDashboardRoute:
    def test_dashboard_applies_exclude_models(self, http):
        _seed_records()
        params = urllib.parse.urlencode({"range": "30d", "exclude_models": ["model-a"]}, doseq=True)
        data, status = _get(f"{http}/api/dashboard?{params}")
        assert status == 200
        # models 全量返回 (环形图保留被排除模型以便图例点击加回), 排行由前端过滤
        assert sorted(m["model"] for m in data["models"]) == ["model-a", "model-b"]
        assert data["totals"]["request_count"] == 1
        assert data["excluded_models"] == ["model-a"]
        row = next(r for r in data["trend"] if r["date"] == _today())
        assert row["request_count"] == 1  # 趋势同样排除

    def test_dashboard_without_exclude_keeps_all(self, http):
        _seed_records()
        data, status = _get(f"{http}/api/dashboard?range=30d")
        assert status == 200
        assert sorted(m["model"] for m in data["models"]) == ["model-a", "model-b"]
        assert data["totals"]["request_count"] == 3
        assert data["excluded_models"] == []

    def test_dashboard_cleans_invalid_exclude_entries(self, http):
        _seed_records()
        entries = ["model-a", "model-a", "  ", "x" * 300]
        params = urllib.parse.urlencode({"range": "30d", "exclude_models": entries}, doseq=True)
        data, status = _get(f"{http}/api/dashboard?{params}")
        assert status == 200
        assert data["excluded_models"] == ["model-a"]  # 去重 / 去空白 / 超长丢弃
        assert sorted(m["model"] for m in data["models"]) == ["model-a", "model-b"]  # models 始终全量
        assert data["totals"]["request_count"] == 1  # 总卡按排除后聚合
