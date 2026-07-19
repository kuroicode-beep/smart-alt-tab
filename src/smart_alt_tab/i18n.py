# src/smart_alt_tab/i18n.py
"""다국어 문자열 (SVIL 표준 5종: 한국어·English·日本語·中文·Tiếng Việt).

글꼴 이름·사람 이름·사용자 데이터는 번역 대상이 아니다(정본: /svil-frontend-design).
"""

from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    "switcher_header": {
        "ko": "창 전환", "en": "Switch Window", "ja": "ウィンドウ切替",
        "zh": "切换窗口", "vi": "Chuyển cửa sổ",
    },
    "switcher_hint": {
        "ko": "Alt 놓기=전환  Esc=취소", "en": "Release Alt=Switch  Esc=Cancel",
        "ja": "Altを離す=切替  Esc=キャンセル", "zh": "松开 Alt=切换  Esc=取消",
        "vi": "Nhả Alt=Chuyển  Esc=Hủy",
    },
    "more_above": {
        "ko": "▲ 위로 {n}개 더", "en": "▲ {n} more above", "ja": "▲ 上に{n}件",
        "zh": "▲ 上方还有 {n} 个", "vi": "▲ Còn {n} ở trên",
    },
    "more_below": {
        "ko": "▼ 아래로 {n}개 더", "en": "▼ {n} more below", "ja": "▼ 下に{n}件",
        "zh": "▼ 下方还有 {n} 个", "vi": "▼ Còn {n} ở dưới",
    },
    "tray_settings": {
        "ko": "설정", "en": "Settings", "ja": "設定", "zh": "设置", "vi": "Cài đặt",
    },
    "tray_history": {
        "ko": "업데이트 내역", "en": "Update History", "ja": "更新履歴",
        "zh": "更新记录", "vi": "Lịch sử cập nhật",
    },
    "tray_quit": {
        "ko": "종료", "en": "Quit", "ja": "終了", "zh": "退出", "vi": "Thoát",
    },
    "settings_title": {
        "ko": "설정", "en": "Settings", "ja": "設定", "zh": "设置", "vi": "Cài đặt",
    },
    "settings_font": {
        "ko": "글꼴", "en": "Font", "ja": "フォント", "zh": "字体", "vi": "Phông chữ",
    },
    "settings_size": {
        "ko": "글자 크기", "en": "Text Size", "ja": "文字サイズ", "zh": "字号", "vi": "Cỡ chữ",
    },
    "size_small": {
        "ko": "작음", "en": "Small", "ja": "小", "zh": "小", "vi": "Nhỏ",
    },
    "size_medium": {
        "ko": "보통", "en": "Medium", "ja": "中", "zh": "中", "vi": "Vừa",
    },
    "size_large": {
        "ko": "큼", "en": "Large", "ja": "大", "zh": "大", "vi": "Lớn",
    },
    "settings_lang": {
        "ko": "언어", "en": "Language", "ja": "言語", "zh": "语言", "vi": "Ngôn ngữ",
    },
    "settings_close": {
        "ko": "닫기", "en": "Close", "ja": "閉じる", "zh": "关闭", "vi": "Đóng",
    },
    "settings_preview": {
        "ko": "미리보기: 창 전환 Aa 0123", "en": "Preview: Switch Window Aa 0123",
        "ja": "プレビュー: ウィンドウ切替 Aa 0123", "zh": "预览: 切换窗口 Aa 0123",
        "vi": "Xem trước: Chuyển cửa sổ Aa 0123",
    },
    "settings_history_title": {
        "ko": "업데이트 내역", "en": "Update History", "ja": "更新履歴",
        "zh": "更新记录", "vi": "Lịch sử cập nhật",
    },
    "settings_saved": {
        "ko": "저장됨 · 바로 적용됩니다", "en": "Saved · applies immediately",
        "ja": "保存済み・即時反映", "zh": "已保存 · 立即生效", "vi": "Đã lưu · áp dụng ngay",
    },
}


def t(key: str, lang: str = "ko", **kwargs) -> str:
    """문자열 키를 언어별로 조회. 없으면 한국어 폴백, 그마저 없으면 키 그대로."""
    table = _STRINGS.get(key)
    if not table:
        return key
    text = table.get(lang) or table.get("ko") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
