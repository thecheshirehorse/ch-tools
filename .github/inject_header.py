import glob, re

HEADER = (
    '<div style="background:linear-gradient(135deg,#034a31,#056A45 60%,#0e8f5e);'
    'color:#fff;padding:16px 28px;display:flex;align-items:center;gap:10px;'
    'font-family:\'Segoe UI\',Tahoma,Geneva,Verdana,sans-serif;flex-shrink:0">'
    '<img src="/ch-tools/assets/logo-white.svg" alt="Cheshire Horse" style="height:32px;width:auto;display:block">'
    '<span style="opacity:0.4;font-size:13px;font-weight:300;color:#fff">|</span>'
    '<span style="font-size:16px;font-weight:600;color:#fff;letter-spacing:0.2px">Tools</span>'
    '</div>'
)

EXTRA_CSS = """<style>
.staticrypt-page{display:flex;flex-direction:column;min-height:calc(100vh - 64px);align-items:center;justify-content:center;background:#f6f8f6}
.staticrypt-form-wrapper{background:#fff;border:1px solid #dde4e0;border-radius:12px;padding:32px;width:100%;max-width:360px;box-shadow:0 4px 16px rgba(5,106,69,0.08)}
#staticrypt-password{border-color:#dde4e0}
#staticrypt-password:focus{border-color:#056A45;box-shadow:0 0 0 3px rgba(5,106,69,0.1);outline:none}
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
    content = re.sub(r'(<body[^>]*>)', r'\1' + HEADER, content, count=1)
    content = content.replace('</head>', EXTRA_CSS + '</head>', 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f'Branded: {path}')
