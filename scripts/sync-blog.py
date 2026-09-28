#!/usr/bin/env python3
"""Mirror the Wix blog into src/data/posts.json + public/images/blog.

Usage: python3 scripts/sync-blog.py
Reads the public Wix blog feed, downloads each post's SSR HTML, converts the
Ricos body to clean HTML and downloads every image locally.
"""
import re, json, os, html as H, urllib.request, subprocess, sys
from html.parser import HTMLParser

WIX = 'https://impactcollective.wixsite.com/rishi'
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(REPO, 'public/images/blog')
OUT = os.path.join(REPO, 'src/data/posts.json')
UA = {'User-Agent': 'Mozilla/5.0 (Macintosh) Chrome/126'}
VOID = {'br', 'img', 'hr', 'input', 'meta', 'link', 'source', 'path'}
KEEP = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'li', 'strong', 'em', 'u', 'blockquote', 'a', 'figure', 'figcaption', 'hr'}

os.makedirs(IMG_DIR, exist_ok=True)

def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA)).read()

def fetch_img(uri, w=None, h=None):
    """Download a wixstatic image once; large PNGs are re-encoded as JPEG."""
    name = uri.replace('~mv2', '')
    base, ext = os.path.splitext(name)
    for cand in (name, base + '.jpg'):
        if os.path.exists(os.path.join(IMG_DIR, cand)):
            return '/images/blog/' + cand
    url = f'https://static.wixstatic.com/media/{uri}'
    if w and h:
        s = min(1.0, 1200 / float(w))
        url += f'/v1/fill/w_{int(w*s)},h_{int(h*s)},al_c,q_85/{uri}'
    dest = os.path.join(IMG_DIR, name)
    open(dest, 'wb').write(get(url))
    if ext == '.png' and os.path.getsize(dest) > 400_000:
        jpg = os.path.join(IMG_DIR, base + '.jpg')
        subprocess.run(['sips', '-s', 'format', 'jpeg', '-s', 'formatOptions', '82', dest, '--out', jpg], capture_output=True)
        os.remove(dest)
        return '/images/blog/' + base + '.jpg'
    return '/images/blog/' + name

class Conv(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0; self.on = False; self.out = []; self.stack = []; self.skip = 0
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if not self.on:
            if a.get('data-id') == 'content-viewer': self.on = True; self.depth = 1
            return
        if tag not in VOID: self.depth += 1
        if self.skip:
            if tag not in VOID: self.skip += 1
            return
        if tag in ('button', 'svg', 'script', 'style'):
            self.skip = 1; return
        if tag == 'wow-image':
            info = json.loads(a.get('data-image-info', '{}')).get('imageData', {})
            if info.get('uri'):
                src = fetch_img(info['uri'], info.get('width'), info.get('height'))
                self.out.append(f'<img src="{src}" alt="" width="{info.get("width", "")}" height="{info.get("height", "")}" loading="lazy" />')
            return
        if tag == 'br': return
        if tag in KEEP:
            if tag == 'a':
                self.out.append(f'<a href="{H.escape(a.get("href", ""))}" target="_blank" rel="noopener">')
            else:
                self.out.append(f'<{tag}>')
        if tag not in VOID: self.stack.append(tag)
    def handle_endtag(self, tag):
        if not self.on or tag in VOID: return
        self.depth -= 1
        if self.depth == 0: self.on = False; return
        if self.skip:
            self.skip -= 1; return
        if self.stack:
            t = self.stack.pop()
            if t in KEEP: self.out.append(f'</{t}>')
    def handle_data(self, d):
        if self.on and not self.skip: self.out.append(H.escape(d, quote=False))

feed = get(WIX + '/blog-feed.xml').decode()
slugs = re.findall(r'<link>[^<]*/post/([^<]+)</link>', feed)
old = {p['slug']: p for p in json.load(open(OUT))} if os.path.exists(OUT) else {}

posts = []
for slug in slugs:
    h = get(f'{WIX}/post/{slug}').decode()
    ld = next(json.loads(m.group(1)) for m in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', h, re.S) if 'BlogPosting' in m.group(1))
    c = Conv(); c.feed(h)
    body = re.sub(r'<(p|h\d|li|strong|em|u)>\s*</\1>', '', ''.join(c.out))
    cover = None
    img = ld.get('image', {}).get('url')
    if img:
        uri = img.split('/media/')[1].split('/')[0]
        cover = fetch_img(uri, float(ld['image']['width']), float(ld['image']['height']))
    text = H.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body))).strip()
    words = len(text.split())
    read = old.get(slug, {}).get('readTime') or max(1, round(words / 200))
    posts.append({'slug': slug, 'title': ld['headline'].strip(), 'author': ld['author']['name'], 'date': ld['datePublished'],
                  'cover': cover, 'excerpt': text[:220].rsplit(' ', 1)[0] + '…', 'readTime': read, 'html': body})
    flag = 'NEW' if slug not in old else ('cover changed' if old[slug].get('cover') != cover else 'ok')
    print(f'{flag:14} {words:4}w  {slug[:60]}')

json.dump(posts, open(OUT, 'w'), ensure_ascii=False, indent=2)
print(f'{len(posts)} posts written to {os.path.relpath(OUT, REPO)}')
