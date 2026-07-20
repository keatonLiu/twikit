"""
GuestClient.get_tweet_by_id 离线（无账号，仅 guest token）调试测试。

流程：
    1. GuestClient().activate()  —— 只需 guest token，不用 cookies/登录
    2. dump gql.tweet_result_by_rest_id 的原始响应到 result/
    3. 静态检查 guest Tweet/User.__init__ 需要的所有 key，一次性列出全部缺失
       （guest 的字段是 __init__ 里 eager 直接取键，缺一个就 KeyError，
        所以先静态 diff 出全部问题，再看真实构造）
    4. 真跑 get_tweet_by_id()，抓构造异常并打印 traceback

用法：
    python tests/test_guest_get_tweet.py <tweet_id>
    TWIKIT_PROXY=http://user:pass@host:port python tests/test_guest_get_tweet.py <id>
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from twikit.guest import GuestClient  # noqa: E402
from twikit.utils import find_dict  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DUMP_DIR = os.path.join(REPO_ROOT, 'result')
DEFAULT_TWEET_ID = '1519480761749016577'

# guest Tweet.__init__ 需要的 key（直接取键、没有 .get 的才会 KeyError）
TWEET_REQUIRED = ['rest_id', 'legacy', 'edit_control', 'core']
TWEET_LEGACY_REQUIRED = [
    'created_at', 'full_text', 'lang', 'is_quote_status', 'quote_count',
    'entities', 'reply_count', 'favorite_count', 'favorited', 'retweet_count',
]
# guest User.__init__ 需要的 key
USER_REQUIRED = ['rest_id', 'is_blue_verified', 'legacy']
USER_LEGACY_REQUIRED = [
    'created_at', 'name', 'screen_name', 'profile_image_url_https', 'location',
    'description', 'entities', 'verified', 'possibly_sensitive', 'default_profile',
    'default_profile_image', 'has_custom_timelines', 'followers_count',
    'fast_followers_count', 'normal_followers_count', 'friends_count',
    'favourites_count', 'listed_count', 'media_count', 'statuses_count',
    'is_translator', 'translator_type',
]


def check_keys(d: dict, required: list[str], title: str) -> list[str]:
    present = d.keys() if isinstance(d, dict) else []
    missing = [k for k in required if k not in present]
    print(f'\n--- {title} ---')
    print(f'  实际 top-level keys: {sorted(present)}')
    if missing:
        print(f'  [缺失] {missing}')
    else:
        print('  [OK] 所有必需 key 都在')
    return missing


async def main() -> None:
    tweet_id = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('TWEET_ID', DEFAULT_TWEET_ID)
    print(f'[target] tweet_id = {tweet_id}')

    client = GuestClient(proxy=os.environ.get('TWIKIT_PROXY'))

    # 1) 激活 guest token
    try:
        token = await client.activate()
        print(f'[activate] guest_token = {token}')
    except Exception:  # noqa: BLE001
        print('[FATAL] activate() 失败（网络/代理/被墙）:')
        traceback.print_exc()
        return

    # 2) dump 原始响应
    os.makedirs(DUMP_DIR, exist_ok=True)
    raw, _resp = await client.gql.tweet_result_by_rest_id(tweet_id)
    dump_path = os.path.join(DUMP_DIR, f'guest_tweet_result_{tweet_id}.json')
    with open(dump_path, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)
    print(f'[dump] raw response -> {dump_path}')

    if isinstance(raw, dict) and 'errors' in raw:
        print(f'[warn] response errors: {raw["errors"]}')

    # 3) 静态字段检查
    found = find_dict(raw, 'result', True)
    if not found:
        print('[FATAL] 响应里找不到 result 节点，dump 看结构')
        return
    tweet_data = found[0]
    if 'tweet' in tweet_data:
        tweet_data = tweet_data['tweet']

    check_keys(tweet_data, TWEET_REQUIRED, 'Tweet 顶层')
    check_keys(tweet_data.get('legacy', {}), TWEET_LEGACY_REQUIRED, 'Tweet.legacy')

    user_data = (
        tweet_data.get('core', {})
        .get('user_results', {})
        .get('result', {})
    )
    if user_data:
        check_keys(user_data, USER_REQUIRED, 'User 顶层')
        check_keys(user_data.get('legacy', {}), USER_LEGACY_REQUIRED, 'User.legacy')
        # user 的 name/screen_name 现在可能挪到了 core，顺便看一眼
        if 'core' in user_data:
            print(f'\n--- User.core 内容（字段可能挪到这里）---\n  {user_data["core"]}')
    else:
        print('\n[warn] 没找到 user_results.result，core 结构可能变了')

    # 4) 真跑解析
    print('\n===== 真跑 get_tweet_by_id() =====')
    try:
        tweet = await client.get_tweet_by_id(tweet_id)
    except Exception:  # noqa: BLE001
        print('[FAIL] 构造 Tweet/User 时抛异常（就是字段匹配问题）:')
        traceback.print_exc()
        print(f'\n对照 {dump_path} 和上面的缺失清单改 twikit/guest/tweet.py + user.py')
        return

    if tweet is None:
        print('[warn] get_tweet_by_id 返回 None（tweet_from_data 的守卫拦下了，'
              '多半 core/user_results/legacy 结构变了）')
        return

    print(f'[OK] {tweet!r}')
    print(f'  text        : {tweet.text[:80]!r}')
    print(f'  user        : {tweet.user!r}')
    if tweet.user is not None:
        print(f'  user.name   : {tweet.user.name!r}')
        print(f'  screen_name : {tweet.user.screen_name!r}')
    print(f'  favorite    : {tweet.favorite_count}  retweet: {tweet.retweet_count}')


if __name__ == '__main__':
    asyncio.run(main())
