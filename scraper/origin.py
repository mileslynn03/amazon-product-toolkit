"""从亚马逊 review-date 原文识别评价标注地区，独立于采集站点。"""
from __future__ import annotations
import re
import unicodedata

# 使用完整地区别名匹配，不用字符串包含关系推断；未识别时保持未知。
_ALIASES = {
    "us": "United States|United States of America|USA|U.S.|U.S.A.|美国|美國|アメリカ合衆国|Vereinigte Staaten|États-Unis|Estados Unidos|Stati Uniti",
    "uk": "United Kingdom|UK|U.K.|Great Britain|GB|英国|英國|イギリス|Vereinigtes Königreich|Royaume-Uni|Reino Unido|Regno Unito|Verenigd Koninkrijk",
    "de": "Germany|Deutschland|德国|德國|ドイツ|Allemagne|Alemania|Germania",
    "fr": "France|Frankreich|法国|法國|フランス|Francia|Frankrijk",
    "it": "Italy|Italia|Italien|意大利|義大利|イタリア|Italie|Italië",
    "es": "Spain|España|Spanien|西班牙|スペイン|Espagne|Spagna|Spanje",
    "jp": "Japan|日本|Japon|Japón|Giappone|Japão",
    "ca": "Canada|Kanada|加拿大|カナダ|Canadá",
    "mx": "Mexico|México|Mexiko|墨西哥|メキシコ|Mexique|Messico",
    "br": "Brazil|Brasil|Brasilien|巴西|ブラジル|Brésil|Brasile",
    "au": "Australia|Australien|Australie|澳大利亚|澳大利亞|オーストラリア|Australië",
    "in": "India|Indien|Inde|印度|インド|Índia",
    "nl": "Netherlands|Nederland|Niederlande|Niederlanden|荷兰|荷蘭|オランダ|Pays-Bas|Países Bajos|Paesi Bassi",
    "se": "Sweden|Sverige|Schweden|瑞典|スウェーデン|Suède|Suecia|Svezia",
    "pl": "Poland|Polska|Polsce|Polen|波兰|波蘭|ポーランド|Pologne|Polonia",
    "sg": "Singapore|Singapur|Singapour|新加坡|シンガポール|Singapura",
    "ae": "United Arab Emirates|UAE|U.A.E.|阿联酋|阿聯酋|アラブ首長国連邦|Vereinigte Arabische Emirate|Vereinigten Arabischen Emiraten|Émirats arabes unis|Emiratos Árabes Unidos|Emirati Arabi Uniti|الإمارات العربية المتحدة",
    "tr": "Turkey|Türkiye|Turkiye|Türkei|土耳其|トルコ|Turquie|Turquía|Turchia",
    "sa": "Saudi Arabia|沙特|沙特阿拉伯|サウジアラビア|Saudi-Arabien|Arabie saoudite|Arabia Saudita|المملكة العربية السعودية",
    "be": "Belgium|België|Belgique|Belgien|比利时|比利時|ベルギー|Bélgica|Belgio",
}


def _normalize(value):
    value = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", value)).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = re.sub(r"^the\s+", "", value.strip())
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


_CODES = {_normalize(alias): code for code, names in _ALIASES.items() for alias in names.split("|")}
_PATTERNS = [
    r"^Reviewed\s+in\s+(.+?)\s+on\s+\S",
    r"^Rezension\s+aus\s+(.+?)\s+vom\s+\S",
    r"^Comment[ée]\s+(?:en|au|aux)\s+(.+?)\s+le\s+\S",
    r"^(?:Revisado|Reseñado)\s+en\s+(.+?)\s+el\s+\S",
    r"^Recensito\s+in\s+(.+?)\s+il\s+\S",
    r"^Avaliado\s+(?:no|na|nos|nas|em)\s+(.+?)\s+em\s+\S",
    r"^Beoordeeld\s+in\s+(.+?)\s+op\s+\S",
    r"^Recenserad\s+i\s+(.+?)\s+den\s+\S",
    r"^Opinia\s+napisana\s+w\s+(.+?)\s+dnia\s+\S",
    r"^(.+?)で\s*\d{4}年",
    r"^(.+?)\s*于\s*\d{4}年",
    r"在\s*(.+?)\s*(?:评价|評價|评论|評論)",
    r"^تمت المراجعة في\s+(.+?)\s+في\s+\S",
    r"tarihinde\s+(.+?)[’'](?:de|da)\s+değerlendirildi",
]


def review_origin(date_text):
    """返回 (地区代码, 原文地区名)；未知地区代码为空，绝不回退到采集站点。"""
    text = " ".join(unicodedata.normalize("NFKC", str(date_text or "")).split())
    for pattern in _PATTERNS:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            name = match.group(1).strip()
            return _CODES.get(_normalize(name), ""), name
    return "", ""


def origin_fields(date_text):
    code, name = review_origin(date_text)
    return {"review_country": code, "review_country_name": name}
