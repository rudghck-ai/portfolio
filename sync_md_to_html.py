#!/usr/bin/env python3
"""
portfolio.md의 내용을 파싱하여 index.html의 어학, 자격증, 분석장비 섹션에 자동 동기화하는 스크립트
"""

import os
import re
import sys
import subprocess

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
MD_PATH = os.path.join(CURRENT_DIR, 'portfolio.md')
HTML_PATH = os.path.join(CURRENT_DIR, 'index.html')

def parse_markdown_tables(md_text):
    data = {
        'lang': [],
        'cert': [],
        'tools': []
    }

    # 1. Section 2: 공인 어학 성적
    m_lang = re.search(r'## 2\. 공인 어학 성적 정리.*?\n(.*?)(?=\n---|\n## |\Z)', md_text, re.DOTALL)
    if m_lang:
        lines = m_lang.group(1).strip().split('\n')
        for line in lines:
            if not line.startswith('|') or '---|' in line or '시험 구분' in line:
                continue
            parts = [p.strip().replace('**', '').replace('`', '') for p in line.strip('|').split('|')]
            if len(parts) >= 3 and (parts[0] or parts[1] or parts[2]):
                data['lang'].append({
                    'name': parts[0],
                    'val': parts[1],
                    'sub': parts[2]
                })

    # 2. Section 3: 국가기술 자격증
    m_cert = re.search(r'## 3\. 국가기술 자격증.*?\n(.*?)(?=\n---|\n## |\Z)', md_text, re.DOTALL)
    if m_cert:
        lines = m_cert.group(1).strip().split('\n')
        for line in lines:
            if not line.startswith('|') or '---|' in line or '자격증명' in line:
                continue
            parts = [p.strip().replace('**', '').replace('`', '') for p in line.strip('|').split('|')]
            if len(parts) >= 4 and (parts[1] or parts[2] or parts[3]):
                data['cert'].append({
                    'no': parts[0],
                    'name': parts[1],
                    'sub': parts[2],
                    'val': parts[3]
                })

    # 3. Section 4: 분석 장비 & 실무 툴
    m_tools = re.search(r'## 4\. 배터리 분석 장비.*?\n(.*?)(?=\n---|\n## |\Z)', md_text, re.DOTALL)
    if m_tools:
        lines = m_tools.group(1).strip().split('\n')
        for line in lines:
            if not line.startswith('|') or '---|' in line or '장비 및 툴' in line:
                continue
            parts = [p.strip().replace('**', '').replace('`', '') for p in line.strip('|').split('|')]
            if len(parts) >= 3 and (parts[1] or parts[2]):
                data['tools'].append({
                    'no': parts[0],
                    'name': parts[1],
                    'desc': parts[2]
                })

    return data

def build_lang_html(lang_items):
    if not lang_items:
        return '          <div class="spec-empty-hint" style="padding: 16px; text-align: center; color: var(--muted); font-size: 13px;">등록된 어학 성적이 없습니다. portfolio.md의 [2. 공인 어학 성적]에 내용을 입력하세요.</div>'
    
    html = []
    for i, item in enumerate(lang_items, 1):
        html.append(f'''          <div class="spec-row-item">
            <div class="spec-item-left">
              <span class="spec-item-name" data-edit="lang{i}_name">{item['name']}</span>
              <span class="spec-item-sub" data-edit="lang{i}_sub">{item['sub']}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="spec-item-badge" data-edit="lang{i}_val">{item['val']}</span>
              <button class="btn-del-spec-item" type="button" onclick="removeSpecRow(this)" title="이 어학 성적 항목 삭제">✕</button>
            </div>
          </div>''')
    return '\n'.join(html)

def build_cert_html(cert_items):
    if not cert_items:
        return '          <div class="spec-empty-hint" style="padding: 16px; text-align: center; color: var(--muted); font-size: 13px;">등록된 자격증이 없습니다. portfolio.md의 [3. 국가기술 자격증]에 내용을 입력하세요.</div>'
    
    html = []
    for i, item in enumerate(cert_items, 1):
        html.append(f'''          <div class="spec-row-item">
            <div class="spec-item-left">
              <span class="spec-item-name" data-edit="cert{i}_name">{item['name']}</span>
              <span class="spec-item-sub" data-edit="cert{i}_sub">{item['sub']}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="spec-item-badge" data-edit="cert{i}_val">{item['val']}</span>
              <button class="btn-del-spec-item" type="button" onclick="removeSpecRow(this)" title="이 자격증 항목 삭제">✕</button>
            </div>
          </div>''')
    return '\n'.join(html)

def build_tools_html(tool_items):
    if not tool_items:
        return '''      <div class="spec-empty-hint" style="grid-column: 1 / -1; padding: 24px; text-align: center; color: var(--muted); font-size: 13.5px; background: rgba(0,0,0,0.02); border-radius: 12px; border: 1px dashed var(--border);">
        등록된 분석 장비 및 툴이 없습니다. portfolio.md의 [4. 배터리 분석 장비 & 실무 툴 스택]에 내용을 입력하세요.
      </div>'''
    
    html = []
    for item in tool_items:
        html.append(f'''      <div class="b-tool-card card-box">
        <div style="display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; width: 100%;">
          <strong class="tool-name" contenteditable="true" style="outline: none; border-bottom: 1px dashed #CBD5E1; flex: 1;">{item['name']}</strong>
          <button class="btn-del-tool-card" type="button" onclick="removeBatteryToolCard(this)" title="이 장비 삭제">✕</button>
        </div>
        <span class="tool-desc" contenteditable="true" style="outline: none; margin-top: 8px; display: block; color: #475569; font-size: 12.5px; line-height: 1.5;">{item['desc']}</span>
      </div>''')
    return '\n'.join(html)

def sync_md_to_html():
    if not os.path.exists(MD_PATH):
        print(f"[오류] {MD_PATH} 파일이 없습니다.", file=sys.stderr)
        return False

    with open(MD_PATH, 'r', encoding='utf-8') as f:
        md_text = f.read()

    data = parse_markdown_tables(md_text)

    with open(HTML_PATH, 'r', encoding='utf-8') as f:
        html_text = f.read()

    # 1. langSpecList 교체
    new_lang_html = build_lang_html(data['lang'])
    html_text = re.sub(
        r'(<div class="spec-table-list" id="langSpecList">)(.*?)(</div>\s*</div>\s*<!-- 자격증 -->)',
        r'\1\n' + new_lang_html + r'\n        \3',
        html_text,
        flags=re.DOTALL
    )

    # 2. certSpecList 교체
    new_cert_html = build_cert_html(data['cert'])
    html_text = re.sub(
        r'(<div class="spec-table-list" id="certSpecList">)(.*?)(</div>\s*</div>\s*</section>)',
        r'\1\n' + new_cert_html + r'\n        \3',
        html_text,
        flags=re.DOTALL
    )

    # 3. batteryToolsGrid 교체
    new_tools_html = build_tools_html(data['tools'])
    html_text = re.sub(
        r'(<section class="battery-tools-grid" id="batteryToolsGrid"[^>]*>)(.*?)(</section>\s*<div class="section-tag-pill">Target Companies)',
        r'\1\n' + new_tools_html + r'\n    \3',
        html_text,
        flags=re.DOTALL
    )

    with open(HTML_PATH, 'w', encoding='utf-8') as f:
        f.write(html_text)

    print(f"✅ [동기화 완료] portfolio.md ➜ index.html 반영 완료!")
    print(f"   - 어학: {len(data['lang'])}개")
    print(f"   - 자격증: {len(data['cert'])}개")
    print(f"   - 분석 장비/툴: {len(data['tools'])}개")
    return True

if __name__ == '__main__':
    sync_md_to_html()
