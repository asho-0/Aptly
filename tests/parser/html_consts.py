DEGEWO_CARD_HTML = """
<article class="article-list__item--immosearch" id="immo-25566">
    <a href="/immosuche/detail/25566">Link</a>
    <div class="article__meta">Musterstraße 1 | Mitte</div>
    <div class="article__title">3-Zimmer-Wohnung</div>
    <div class="article__properties">3 Zimmer | 75,00 m²</div>
    <div class="price">850,00 €</div>
    <div class="article__tags"></div>
</article>
"""

DEGEWO_WBS_CARD_HTML = """
<article class="article-list__item--immosearch" id="immo-25567">
    <a href="/immosuche/detail/25567">Link</a>
    <div class="article__meta">Teststraße 5 | Prenzlauer Berg</div>
    <div class="article__title">2-Zimmer WBS Wohnung</div>
    <div class="article__properties">2 Zimmer | 55,00 m²</div>
    <div class="price">650,00 €</div>
    <div class="article__tags">WBS erforderlich</div>
</article>
"""

DEGEWO_MULTIPLE_HTML = """
<article class="article-list__item--immosearch" id="immo-1">
    <a href="/detail/1">Link</a>
    <div class="article__meta">Str. 1 | Mitte</div>
    <div class="article__title">Wohnung 1</div>
    <div class="article__properties">2 Zimmer | 50,00 m²</div>
    <div class="price">700,00 €</div>
    <div class="article__tags"></div>
</article>
<article class="article-list__item--immosearch" id="immo-2">
    <a href="/detail/2">Link</a>
    <div class="article__meta">Str. 2 | Pankow</div>
    <div class="article__title">Wohnung 2</div>
    <div class="article__properties">3 Zimmer | 70,00 m²</div>
    <div class="price">900,00 €</div>
    <div class="article__tags"></div>
</article>
"""

GEWOBAG_CARD_HTML = """
<article class="gw-offer">
    <a href="/angebote/wohnungen/detail/schoene-wohnung-mitte">Link</a>
    <div class="gw-offer__content">
        <div class="angebot-title">2-Zimmer-Wohnung Mitte</div>
        <address>Unter den Linden 1, Berlin</address>
        <div class="angebot-region">Bezirk Mitte</div>
        <div class="angebot-kosten"><table><tr><td>750,00 €</td></tr></table></div>
        <div class="angebot-area"><table><tr><td>2 Zimmer | 55,00 m²</td></tr></table></div>
    </div>
</article>
"""

GEWOBAG_WBS_CARD_HTML = """
<article class="gw-offer">
    <a href="/angebote/wbs-wohnungen/detail/wbs-wohnung-pankow">Link</a>
    <div class="gw-offer__content">
        <div class="angebot-title">WBS Wohnung Pankow</div>
        <address>Pankower Str. 5, Berlin</address>
        <div class="angebot-region">Bezirk Pankow</div>
        <div class="angebot-kosten"><table><tr><td>600,00 €</td></tr></table></div>
        <div class="angebot-area"><table><tr><td>2 Zimmer | 48,00 m²</td></tr></table></div>
    </div>
</article>
"""

GEWOBAG_NO_HREF_HTML = """
<article class="gw-offer">
    <div class="gw-offer__content">
        <div class="angebot-title">No link apartment</div>
    </div>
</article>
"""

GEWOBAG_MULTIPLE_HTML = GEWOBAG_CARD_HTML + """
<article class="gw-offer">
    <a href="/angebote/wohnungen/detail/wohnung-zwei">Link</a>
    <div class="gw-offer__content">
        <div class="angebot-title">3-Zimmer-Wohnung Pankow</div>
        <address>Pankower Allee 10</address>
        <div class="angebot-region">Bezirk Pankow</div>
        <div class="angebot-kosten"><table><tr><td>900,00 €</td></tr></table></div>
        <div class="angebot-area"><table><tr><td>3 Zimmer | 70,00 m²</td></tr></table></div>
    </div>
</article>
"""

WBM_CARD_HTML = """
<div class="immo-teaser">
    <a href="/wohnen/wohnungen/detail/3-zimmer-wohnung-spandau">Link</a>
    <h3>3-Zimmer-Wohnung in Spandau</h3>
    <span class="main-property-rent">950,00 €</span>
    <span class="main-property-rooms">3</span>
    <span class="main-property-size">72,00 m²</span>
    <span class="address">Spandauer Str. 10, Spandau</span>
</div>
"""

WBM_WBS_CARD_HTML = """
<div class="immo-teaser">
    <a href="/wohnen/wohnungen/detail/wbs-wohnung-treptow">Link</a>
    <h3>WBS 160 Wohnung Treptow</h3>
    <span class="main-property-rent">680,00 €</span>
    <span class="main-property-rooms">2</span>
    <span class="main-property-size">58,00 m²</span>
    <span class="address">Treptower Park 1</span>
</div>
"""
