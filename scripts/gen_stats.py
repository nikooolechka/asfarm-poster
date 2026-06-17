"""Сборщик РЕАЛЬНОЙ статистики соцсетей АС Фарм → docs/stats.json.

Только факты из API; чего нет — помечаем null (в календаре не показываем).
Запускается раз в сутки из publish.py перед генерацией календаря.

- ВКонтакте: подписчики, постов на стене, сумма просмотров (token из env VK_TOKEN
  или /Users/nikol/Desktop/files/vk_token.txt). Источник правды — VK API.
- Дзен: число наших статей в ленте (из очереди). Подписчики/просмотры публичного
  API не имеют — оставляем null.
- VC.ru: число наших публикаций (из очереди). Просмотры/подписчики best-effort.
"""
import os, json, ssl, urllib.request, urllib.parse

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO_ROOT, "docs", "stats.json")
QUEUE = os.path.join(REPO_ROOT, "content", "queue.json")
CTX = ssl._create_unverified_context()

VK_GROUP_ID = "239602265"      # owner_id = -239602265
VK_SCREEN = "asfarm_ru"
DZEN_URL = "https://dzen.ru/asfarm_ru"
VC_URL = "https://vc.ru/id6010646"


def _vk_token():
    t = os.environ.get("VK_TOKEN", "").strip()
    if t:
        return t
    p = "/Users/nikol/Desktop/files/vk_token.txt"
    if os.path.exists(p):
        return open(p).read().strip()
    return ""


def vk_stats():
    tok = _vk_token()
    if not tok:
        return None
    def call(method, **params):
        params.update(access_token=tok, v="5.199")
        url = f"https://api.vk.com/method/{method}?" + urllib.parse.urlencode(params)
        return json.load(urllib.request.urlopen(url, context=CTX, timeout=30))
    try:
        g = call("groups.getById", group_id=VK_GROUP_ID, fields="members_count")
        grp = g["response"]["groups"][0] if "groups" in g.get("response", {}) else g["response"][0]
        members = grp.get("members_count")
        screen = grp.get("screen_name", VK_SCREEN)
        w = call("wall.get", owner_id=f"-{VK_GROUP_ID}", count=100)
        items = w["response"]["items"]
        total = w["response"]["count"]
        views = sum(it.get("views", {}).get("count", 0) for it in items)
        return dict(subscribers=members, posts=total, views=views or None,
                    url=f"https://vk.com/{screen}")
    except Exception as e:
        print("vk_stats error:", e)
        return dict(url=f"https://vk.com/{VK_SCREEN}")


def dzen_stats(posts):
    # ВАЖНО: released_at = статья отдана в RSS-ленту, а НЕ опубликована на Дзене.
    # Лента ещё на модерации Дзена; реально опубликованных статей пока 0.
    # Публичного API подтверждённых публикаций у канала нет → показываем 0.
    return dict(subscribers=None, posts=0, views=None, url=DZEN_URL)


def vc_stats(posts):
    published = len([p for p in posts if p["channels"].get("vc", {}).get("posted_at")])
    return dict(subscribers=None, posts=published, views=None, url=VC_URL)


def collect():
    posts = json.load(open(QUEUE, encoding="utf-8"))
    return {
        "vk": vk_stats() or dict(url=f"https://vk.com/{VK_SCREEN}"),
        "dzen": dzen_stats(posts),
        "vc": vc_stats(posts),
    }


def main():
    data = collect()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("stats ->", OUT)
    print(json.dumps(data, ensure_ascii=False))


if __name__ == "__main__":
    main()
