import glob, re

LOGO_BLOCK = (
    '<div style="text-align:center;margin-bottom:24px">'
    '<img src="/ch-tools/assets/logo-green.svg" alt="Cheshire Horse" '
    'style="height:44px;width:auto;display:inline-block">'
    '</div>'
)

EXTRA_CSS = """<style>
.staticrypt-page{background:#f6f8f6}
.staticrypt-form-wrapper{border:1px solid #dde4e0;border-radius:12px;
  box-shadow:0 4px 16px rgba(5,106,69,0.08)}
#staticrypt-password:focus{border-color:#056A45;
  box-shadow:0 0 0 3px rgba(5,106,69,0.1);outline:none}
</style>
"""

files = glob.glob('**/*.html', recursive=True) + glob.glob('*.html')
seen = set()
for path in files:
    if path in seen:
        continue
    seen.add(path)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'staticrypt-html' not in content:
        continue
    # inject logo above the login card
    content = content.replace(
        '<div class="staticrypt-form-wrapper">',
        LOGO_BLOCK + '<div class="staticrypt-form-wrapper">',
        1
    )
    # fix button label
    content = re.sub(r'(?i)>decrypt<', '>LOGIN<', content)
    # inject extra CSS
    content = content.replace('</head>', EXTRA_CSS + '</head>', 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Branded: {path}')
