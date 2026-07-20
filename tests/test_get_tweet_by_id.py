"""
get_tweet_by_id 调试测试。

目的：把 tweet_detail 的原始响应 dump 到文件，并逐个探测 Tweet 的每个属性，
定位当前"字段匹配"问题（哪些 property 因为 X 改了返回结构而 KeyError / 取不到值）。

用法：
    # 用 cookies（推荐）
    TWIKIT_COOKIES=cookies.json python tests/test_get_tweet_by_id.py <tweet_id>

    # 或用账号密码登录
    TWIKIT_USERNAME=... TWIKIT_EMAIL=... TWIKIT_PASSWORD=... \
        python tests/test_get_tweet_by_id.py <tweet_id>

    # 可选代理
    TWIKIT_PROXY=http://user:pass@host:port python tests/test_get_tweet_by_id.py <id>

不带参数时使用一个默认的公开 tweet id。
原始响应 dump 到 result/tweet_detail_<id>.json（result/ 已在 .gitignore）。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback

# 允许从仓库根目录直接 `python tests/xxx.py` 运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twikit import Client  # noqa: E402
from twikit.tweet import Tweet  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP_DIR = os.path.join(REPO_ROOT, 'result')

DEFAULT_TWEET_ID = '1519480761749016577'


def _preview(value) -> str:
    """把任意值压成一行短预览，方便打印。"""
    try:
        if isinstance(value, list):
            return f'list(len={len(value)}) -> {[type(v).__name__ for v in value[:3]]}'
        text = repr(value)
    except Exception as e:  # noqa: BLE001
        return f'<repr failed: {e!r}>'
    text = text.replace('\n', ' ')
    return text if len(text) <= 100 else text[:97] + '...'


def _tweet_property_names() -> list[str]:
    """取 Tweet 上所有 public property 名（这些正是解析响应字段的地方）。"""
    return sorted(
        name
        for name, member in vars(Tweet).items()
        if isinstance(member, property) and not name.startswith('_')
    )


def probe_fields(obj, prop_names: list[str], title: str) -> list[str]:
    """逐个读取属性，报告 OK / 失败，返回失败的字段名列表。"""
    print(f'\n===== {title} =====')
    failed: list[str] = []
    width = max(len(n) for n in prop_names)
    for name in prop_names:
        try:
            value = getattr(obj, name)
        except Exception as e:  # noqa: BLE001
            failed.append(name)
            print(f'  [FAIL] {name:<{width}} : {type(e).__name__}: {e}')
        else:
            print(f'  [ ok ] {name:<{width}} : {_preview(value)}')
    return failed


async def build_client() -> Client:
    client = Client('en-US', proxy=os.environ.get('TWIKIT_PROXY'))

    cookies = os.environ.get('TWIKIT_COOKIES', 'cookies.json')
    if cookies and os.path.exists(cookies):
        client.load_cookies(cookies)
        print(f'[auth] loaded cookies from {cookies}')
        return client

    username = os.environ.get('TWIKIT_USERNAME')
    email = os.environ.get('TWIKIT_EMAIL')
    password = os.environ.get('TWIKIT_PASSWORD')
    if username and password:
        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password,
            cookies_file=cookies or 'cookies.json',
        )
        print('[auth] logged in with credentials')
        return client

    raise SystemExit(
        'No auth available. Set TWIKIT_COOKIES=<path to cookies.json> '
        'or TWIKIT_USERNAME/TWIKIT_EMAIL/TWIKIT_PASSWORD.'
    )


async def main() -> None:
    tweet_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('TWEET_ID', DEFAULT_TWEET_ID)
    print(f'[target] tweet_id = {tweet_id}')

    client = await build_client()

    # 1) dump 原始 tweet_detail 响应
    os.makedirs(DUMP_DIR, exist_ok=True)
    raw, _resp = await client.gql.tweet_detail(tweet_id, None)
    dump_path = os.path.join(DUMP_DIR, f'tweet_detail_{tweet_id}.json')
    with open(dump_path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f'[dump] raw response -> {dump_path}')

    if isinstance(raw, dict) and 'errors' in raw:
        print(f'[warn] response has errors: {raw["errors"]}')

    # 2) 走正常解析路径拿 Tweet
    try:
        tweet = await client.get_tweet_by_id(tweet_id)
    except Exception:  # noqa: BLE001
        print('\n[FATAL] get_tweet_by_id() raised before returning a Tweet:')
        traceback.print_exc()
        print(f'\n原始响应已 dump 到 {dump_path}，对照它修字段。')
        return

    print(f'\n[parsed] {tweet!r}')

    # 3) 逐字段探测 Tweet
    tweet_failed = probe_fields(tweet, _tweet_property_names(), 'Tweet fields')

    # 4) 顺带探测作者 User 的字段（字段问题常常也出在 User 上）
    user_failed: list[str] = []
    if tweet.user is not None:
        user_props = sorted(
            name
            for name, member in vars(type(tweet.user)).items()
            if isinstance(member, property) and not name.startswith('_')
        )
        if user_props:
            user_failed = probe_fields(tweet.user, user_props, 'User fields')

    # 5) 汇总
    print('\n===== SUMMARY =====')
    print(f'  raw dump      : {dump_path}')
    print(f'  Tweet fields  : {len(tweet_failed)} failed -> {tweet_failed}')
    print(f'  User fields   : {len(user_failed)} failed -> {user_failed}')
    print(f'  replies       : {len(tweet.replies or [])}')
    print(f'  reply_to      : {len(tweet.reply_to or [])}')
    print(f'  related_tweets: {len(tweet.related_tweets or [])}')


if __name__ == '__main__':
    asyncio.run(main())
