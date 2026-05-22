"""修复 detail.html 的编码乱码和HTML错误"""
import os

path = r'c:\Users\Administrator\Desktop\555\pages\detail.html'

with open(path, 'rb') as f:
    raw = f.read()
text = raw.decode('utf-8')

# 1. GBK roundtrip 修复中文乱码
result_bytes = bytearray()
for c in text:
    if ord(c) < 128:
        result_bytes.append(ord(c))
    elif c == '\u20ac':
        result_bytes.append(0x80)
    else:
        try:
            gbk_bytes = c.encode('gbk')
            result_bytes.extend(gbk_bytes)
        except UnicodeEncodeError:
            result_bytes.append(ord('?'))
fixed = result_bytes.decode('gbk')

# 2. 修复已知乱码字符（边界对齐问题）
replacements = {
    '杩斿洖': '返回',
    '鍒嗙被': '分类',
    '资源语言︽儏': '资源详情',
}
for old, new in replacements.items():
    if old in fixed:
        fixed = fixed.replace(old, new)
        print(f'  替换: {old} → {new}')

# 3. 修复 /p> 为 </p>
fixed = fixed.replace('./p>', '</p>')

# 验证
checks = ['返回', '分类', '资源详情', '</p>']
for c in checks:
    print(f'  {"✅" if c in fixed else "❌"} {c}')

with open(path, 'w', encoding='utf-8') as f:
    f.write(fixed)
print(f'\n✅ 已修复 {path}')