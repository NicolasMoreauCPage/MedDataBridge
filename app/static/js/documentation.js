/* Navigation et utilitaires des pages de documentation. */
"use strict";

// Highlight code blocks
document.addEventListener('DOMContentLoaded', function() {
    // La documentation reste lisible même si la coloration optionnelle n'est pas chargée.
    if (window.hljs) {
        document.querySelectorAll('pre code').forEach((block) => {
            window.hljs.highlightElement(block);
        });
    }
    
    // Smooth scroll to anchors
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Collapsible categories state persistence
    document.querySelectorAll('details[data-category]').forEach((detailsEl) => {
        const cat = detailsEl.getAttribute('data-category');
        const key = `doccat:${cat}`;
        const saved = localStorage.getItem(key);
        if (saved === 'open') detailsEl.setAttribute('open', 'open');
        if (saved === 'closed') detailsEl.removeAttribute('open');
        detailsEl.addEventListener('toggle', () => {
            localStorage.setItem(key, detailsEl.open ? 'open' : 'closed');
        });
    });

    // Add copy buttons to code blocks
    document.querySelectorAll('.markdown-content pre').forEach((pre) => {
        const code = pre.querySelector('code');
        if (!code) return;
        const btn = document.createElement('button');
        btn.className = 'copy-btn';
        btn.type = 'button';
        btn.textContent = 'Copier';
        btn.addEventListener('click', async () => {
            try {
                await navigator.clipboard.writeText(code.innerText);
                const old = btn.textContent;
                btn.textContent = 'Copié';
                btn.classList.add('copied');
                setTimeout(() => { btn.textContent = old; btn.classList.remove('copied'); }, 1200);
            } catch (e) {
                console.error('Copy failed', e);
            }
        });
        pre.appendChild(btn);
    });

    // Format last updated timestamp
    document.querySelectorAll('[data-last-updated]').forEach((el) => {
        const ts = parseFloat(el.getAttribute('data-last-updated')) * 1000;
        if (!isNaN(ts)) {
            const d = new Date(ts);
            const fmt = new Intl.DateTimeFormat('fr-FR', { dateStyle: 'medium', timeStyle: 'short' });
            el.textContent = fmt.format(d);
        }
    });
});
