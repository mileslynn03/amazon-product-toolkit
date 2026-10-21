"""亚马逊各国家/地区站点配置。

提供站点域名映射、评论页 URL 构造、星级筛选参数。
注意：亚马逊实际主机统一为 www 前缀（裸域会重定向甚至超时）。
"""

# code -> 站点信息。code 用于内部标识与登录态文件名。
# domain 为完整主机名（含 www.），供 URL 构造与显示。
MARKETPLACES = {
    "us": {"code": "us", "name": "美国", "domain": "www.amazon.com", "currency": "USD"},
    "uk": {"code": "uk", "name": "英国", "domain": "www.amazon.co.uk", "currency": "GBP"},
    "de": {"code": "de", "name": "德国", "domain": "www.amazon.de", "currency": "EUR"},
    "fr": {"code": "fr", "name": "法国", "domain": "www.amazon.fr", "currency": "EUR"},
    "it": {"code": "it", "name": "意大利", "domain": "www.amazon.it", "currency": "EUR"},
    "es": {"code": "es", "name": "西班牙", "domain": "www.amazon.es", "currency": "EUR"},
    "jp": {"code": "jp", "name": "日本", "domain": "www.amazon.co.jp", "currency": "JPY"},
    "ca": {"code": "ca", "name": "加拿大", "domain": "www.amazon.ca", "currency": "CAD"},
    "mx": {"code": "mx", "name": "墨西哥", "domain": "www.amazon.com.mx", "currency": "MXN"},
    "br": {"code": "br", "name": "巴西", "domain": "www.amazon.com.br", "currency": "BRL"},
    "au": {"code": "au", "name": "澳大利亚", "domain": "www.amazon.com.au", "currency": "AUD"},
    "in": {"code": "in", "name": "印度", "domain": "www.amazon.in", "currency": "INR"},
    "nl": {"code": "nl", "name": "荷兰", "domain": "www.amazon.nl", "currency": "EUR"},
    "se": {"code": "se", "name": "瑞典", "domain": "www.amazon.se", "currency": "SEK"},
    "pl": {"code": "pl", "name": "波兰", "domain": "www.amazon.pl", "currency": "PLN"},
    "sg": {"code": "sg", "name": "新加坡", "domain": "www.amazon.sg", "currency": "SGD"},
    "ae": {"code": "ae", "name": "阿联酋", "domain": "www.amazon.ae", "currency": "AED"},
    "tr": {"code": "tr", "name": "土耳其", "domain": "www.amazon.com.tr", "currency": "TRY"},
    "sa": {"code": "sa", "name": "沙特", "domain": "www.amazon.sa", "currency": "SAR"},
    "be": {"code": "be", "name": "比利时", "domain": "www.amazon.com.be", "currency": "EUR"},
}

# 星级筛选参数（对应亚马逊评论页 filterByStar 取值）
STAR_FILTERS = {
    "全部": "all_stars",
    "5 星": "five_star",
    "4 星": "four_star",
    "3 星": "three_star",
    "2 星": "two_star",
    "1 星": "one_star",
    "好评（4-5 星）": "positive",
    "差评（1-3 星）": "critical",
}


def get_domain(code: str) -> str:
    """根据站点 code 返回完整主机名（含 www.）。code 未知时回退到美国站。"""
    return MARKETPLACES.get(code, MARKETPLACES["us"])["domain"]


def get_name(code: str) -> str:
    """返回站点中文名。"""
    return MARKETPLACES.get(code, MARKETPLACES["us"])["name"]


def reviews_url(asin: str, code: str, star_key: str | None = None) -> str:
    """构造某商品在指定站点的评论页 URL。

    star_key 为 STAR_FILTERS 的键（中文），为 None 或「全部」时不带筛选。
    """
    domain = get_domain(code)
    url = f"https://{domain}/product-reviews/{asin}/"
    star_value = STAR_FILTERS.get(star_key) if star_key else None
    if star_value and star_value != "all_stars":
        url += f"?filterByStar={star_value}"
    return url


def detail_url(asin: str, code: str) -> str:
    """商品详情页 URL（免登录可访问，内嵌少量评论）。"""
    return f"https://{get_domain(code)}/dp/{asin}"


def homepage_url(code: str) -> str:
    """站点首页 URL，登录流程用。"""
    return f"https://{get_domain(code)}/"
