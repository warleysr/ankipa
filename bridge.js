// JavaScript bridge to extract current sentence from Anki French cards
(function() {
    let cachedElement = null;
    let cacheTimestamp = 0;
    const CACHE_DURATION = 1000;

    window.ankipaGetCurrentSentence = function() {
        const now = Date.now();

        if (cachedElement && (now - cacheTimestamp) < CACHE_DURATION) {
            return extractText(cachedElement);
        }

        const sentencesInner = document.getElementById('sentences-inner');
        if (!sentencesInner) {
            cachedElement = null;
            return null;
        }

        const frenchSentence = sentencesInner.querySelector('.fr');
        if (!frenchSentence) {
            cachedElement = null;
            return null;
        }

        cachedElement = frenchSentence;
        cacheTimestamp = now;
        return extractText(frenchSentence);
    };

    function extractText(element) {
        if (!element) return null;

        let text = element.textContent || element.innerText || '';
        text = text.replace(/\s+/g, ' ').trim();
        text = text.replace(/\*/g, '');

        return text;
    }

    window.ankipaCustomSelectors = null;

    window.ankipaSetSelectors = function(selectorsString) {
        if (selectorsString && typeof selectorsString === 'string') {
            window.ankipaCustomSelectors = selectorsString.split(',').map(s => s.trim()).filter(s => s);
        }
    };

    window.ankipaGetVisibleText = function() {
        let text = window.ankipaGetCurrentSentence();
        if (text) {
            return text;
        }

        const defaultSelectors = [
            '#sentences-inner .fr',
            '.sentence.fr',
            '.fr.sentence',
            '[data-sentence]',
            '.example-sentence'
        ];

        const selectors = window.ankipaCustomSelectors || defaultSelectors;

        for (const selector of selectors) {
            const element = document.querySelector(selector);
            if (element) {
                text = extractText(element);
                if (text) {
                    cachedElement = element;
                    cacheTimestamp = Date.now();
                    return text;
                }
            }
        }

        return null;
    };

    window.ankipaHighlightText = function() {
        const element = cachedElement || document.querySelector('#sentences-inner .fr');
        if (!element) return false;

        const existingHighlight = document.querySelector('.ankipa-highlight-border');
        if (existingHighlight) {
            existingHighlight.classList.remove('ankipa-highlight-border');
        }

        element.classList.add('ankipa-highlight-border');

        return true;
    };

    window.ankipaRemoveHighlight = function() {
        const element = document.querySelector('.ankipa-highlight-border');
        if (element) {
            element.classList.remove('ankipa-highlight-border');
        }
    };

    // Trigger AnkiPA assessment from JavaScript (optionally with specific text or selector)
    window.ankipaStart = function(target) {
        let text = null;
        if (typeof target === 'string' && target.trim()) {
            // Check if target is a CSS selector pointing to an existing DOM element
            try {
                const el = document.querySelector(target);
                if (el) {
                    text = extractText(el);
                    if (text) {
                        cachedElement = el;
                        window.ankipaHighlightText();
                    }
                }
            } catch (e) {
                // Not a valid selector, treat as literal text
            }
            if (!text) {
                text = target.trim();
            }
        } else if (target instanceof HTMLElement) {
            text = extractText(target);
            if (text) {
                cachedElement = target;
                window.ankipaHighlightText();
            }
        }

        const payload = (text !== null && text !== undefined && text !== '')
            ? 'ankipa:start:' + encodeURIComponent(text)
            : 'ankipa:start';

        if (typeof pycmd === 'function') {
            pycmd(payload);
        } else if (typeof bridgeCommand === 'function') {
            bridgeCommand(payload);
        }
    };

    // Auto-bind click events on any button designated for AnkiPA in card templates
    document.addEventListener('click', function(event) {
        const btn = event.target.closest("[data-ankipa='start'], [data-ankipa], .ankipa-start, .ankipa-btn, #ankipa-start");
        if (btn) {
            event.preventDefault();
            const customText = btn.getAttribute('data-ankipa-text') || btn.getAttribute('data-text');
            const customTarget = btn.getAttribute('data-ankipa-target') || btn.getAttribute('data-target');
            window.ankipaStart(customText || customTarget);
        }
    });

    const style = document.createElement('style');
    style.textContent = `
        .ankipa-highlight-border {
            outline: 2px solid #4CAF50 !important;
            outline-offset: 2px !important;
            animation: ankipa-pulse 1s ease-in-out;
        }

        @keyframes ankipa-pulse {
            0%, 100% { outline-color: #4CAF50; }
            50% { outline-color: #81C784; }
        }
    `;
    document.head.appendChild(style);
})();
