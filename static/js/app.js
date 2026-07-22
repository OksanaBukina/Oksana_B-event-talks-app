/* ==========================================================================
   BigQuery Release Radar - Client Application Logic
   ========================================================================== */

document.addEventListener('DOMContentLoaded', () => {
    // --- Application State ---
    const state = {
        items: [],
        categories: {},
        sources: {},
        activeCategory: 'ALL',
        activeSource: 'ALL',
        searchQuery: '',
        sortBy: 'newest',
        selectedIds: new Set(),
        activeModalItem: null,
        activeHashtags: new Set(['#SQL', '#DataEngineering', '#Databases']),
        theme: localStorage.getItem('bq_theme') || 'dark',
        lang: localStorage.getItem('sql_lang') || 'en'
    };

    // Translation Dictionary
    const i18n = {
        ru: {
            Feature: 'Новая функция',
            Changed: 'Изменено',
            Issue: 'Исправление',
            Deprecated: 'Устарело',
            General: 'Общее',
            Announcement: 'Анонс',
            copy: 'Копировать',
            tweet: 'Твит',
            linkedin: 'LinkedIn',
            viewDocs: 'Документация',
            exportCsv: 'Экспорт в CSV'
        },
        pl: {
            Feature: 'Nowa funkcja',
            Changed: 'Zmieniono',
            Issue: 'Poprawka',
            Deprecated: 'Wycofane',
            General: 'Ogólne',
            Announcement: 'Ogłoszenie',
            copy: 'Kopiuj',
            tweet: 'Tweet',
            linkedin: 'LinkedIn',
            viewDocs: 'Dokumentacja',
            exportCsv: 'Eksportuj do CSV'
        }
    };

    // --- DOM Elements ---
    const elements = {
        themeToggle: document.getElementById('themeToggle'),
        langSelector: document.getElementById('langSelector'),
        refreshBtn: document.getElementById('refreshBtn'),
        feedStatusBadge: document.getElementById('feedStatusBadge'),
        
        // Stats
        statTotal: document.getElementById('statTotal'),
        statFeatures: document.getElementById('statFeatures'),
        statChanged: document.getElementById('statChanged'),
        statLastUpdate: document.getElementById('statLastUpdate'),
        
        // Source Counts
        srcCountAll: document.getElementById('srcCountAll'),
        srcCountBQ: document.getElementById('srcCountBQ'),
        srcCountOracle: document.getElementById('srcCountOracle'),
        srcCountTSQL: document.getElementById('srcCountTSQL'),
        srcCountPG: document.getElementById('srcCountPG'),
        srcCountSF: document.getElementById('srcCountSF'),
        
        // Category Counts
        countAll: document.getElementById('countAll'),
        countFeature: document.getElementById('countFeature'),
        countChanged: document.getElementById('countChanged'),
        countIssue: document.getElementById('countIssue'),
        countDeprecated: document.getElementById('countDeprecated'),
        
        // Controls
        searchInput: document.getElementById('searchInput'),
        clearSearchBtn: document.getElementById('clearSearchBtn'),
        sourcePills: document.getElementById('sourcePills'),
        categoryPills: document.getElementById('categoryPills'),
        sortSelect: document.getElementById('sortSelect'),
        exportCsvBtn: document.getElementById('exportCsvBtn'),
        
        // Feed & States
        feedList: document.getElementById('feedList'),
        feedSkeleton: document.getElementById('feedSkeleton'),
        emptyState: document.getElementById('emptyState'),
        resetFiltersBtn: document.getElementById('resetFiltersBtn'),
        
        // Batch Selection Bar
        batchBar: document.getElementById('batchBar'),
        batchCountText: document.getElementById('batchCountText'),
        batchTweetBtn: document.getElementById('batchTweetBtn'),
        deselectAllBtn: document.getElementById('deselectAllBtn'),
        
        // Floating Selection Popover
        selectionPopover: document.getElementById('selectionPopover'),
        popoverTweetBtn: document.getElementById('popoverTweetBtn'),
        
        // Tweet Modal
        tweetModal: document.getElementById('tweetModal'),
        modalSourceNote: document.getElementById('modalSourceNote'),
        modalContextDate: document.getElementById('modalContextDate'),
        modalContextBadge: document.getElementById('modalContextBadge'),
        modalContextSnippet: document.getElementById('modalContextSnippet'),
        tweetTextarea: document.getElementById('tweetTextarea'),
        charCountText: document.getElementById('charCountText'),
        charRingProgress: document.getElementById('charRingProgress'),
        autoFormatBtn: document.getElementById('autoFormatBtn'),
        modalCloseBtn: document.getElementById('modalCloseBtn'),
        modalCancelBtn: document.getElementById('modalCancelBtn'),
        copyTweetBtn: document.getElementById('copyTweetBtn'),
        postXBtn: document.getElementById('postXBtn'),
        
        // Toast
        toastContainer: document.getElementById('toastContainer')
    };

    // --- Initialize Theme & Language ---
    document.documentElement.setAttribute('data-theme', state.theme);

    elements.themeToggle.addEventListener('click', () => {
        state.theme = state.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', state.theme);
        localStorage.setItem('bq_theme', state.theme);
        showToast(`Switched to ${state.theme} mode`, 'info');
    });

    if (elements.langSelector) {
        document.querySelectorAll('.lang-btn').forEach(btn => {
            btn.classList.toggle('active', btn.getAttribute('data-lang') === state.lang);
        });

        elements.langSelector.addEventListener('click', (e) => {
            const btn = e.target.closest('.lang-btn');
            if (!btn) return;
            document.querySelectorAll('.lang-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.lang = btn.getAttribute('data-lang');
            localStorage.setItem('sql_lang', state.lang);
            renderFeed();
            const names = { en: 'English 🇬🇧', ru: 'Русский 🇷🇺', pl: 'Polski 🇵🇱' };
            showToast(`Language changed to ${names[state.lang] || state.lang}`, 'info');
        });
    }

    // --- Fetch Release Notes ---
    async function loadReleaseNotes(forceRefresh = false) {
        setLoadingState(true);
        if (forceRefresh) {
            elements.refreshBtn.classList.add('spinning');
        }

        try {
            const url = forceRefresh ? '/api/release-notes?refresh=true' : '/api/release-notes';
            const response = await fetch(url);
            const data = await response.json();

            if (data.items) {
                state.items = data.items;
                state.categories = data.categories || {};
                updateStats(data);
                renderFeed();
                
                if (forceRefresh) {
                    showToast('Feed refreshed from Google Cloud!', 'success');
                }
            } else {
                showToast('Failed to load release notes.', 'info');
            }
        } catch (err) {
            console.error('Error fetching release notes:', err);
            showToast('Network error while fetching feed.', 'info');
        } finally {
            setLoadingState(false);
            elements.refreshBtn.classList.remove('spinning');
        }
    }

    function setLoadingState(isLoading) {
        if (isLoading && state.items.length === 0) {
            elements.feedSkeleton.classList.remove('hidden');
            elements.feedList.innerHTML = '';
        } else {
            elements.feedSkeleton.classList.add('hidden');
        }
    }

    function updateStats(data) {
        elements.statTotal.textContent = data.total || 0;
        elements.statFeatures.textContent = data.categories['Feature'] || 0;
        elements.statChanged.textContent = (data.categories['Changed'] || 0) + (data.categories['Issue'] || 0);
        
        const sourceKeys = Object.keys(data.sources || {});
        elements.statLastUpdate.textContent = `${sourceKeys.length} SQL Engines`;

        // Source counts
        if (elements.srcCountAll) elements.srcCountAll.textContent = data.total || 0;
        if (elements.srcCountBQ) elements.srcCountBQ.textContent = data.sources['BigQuery'] || 0;
        if (elements.srcCountOracle) elements.srcCountOracle.textContent = data.sources['Oracle'] || 0;
        if (elements.srcCountTSQL) elements.srcCountTSQL.textContent = data.sources['TSQL'] || 0;
        if (elements.srcCountPG) elements.srcCountPG.textContent = data.sources['PostgreSQL'] || 0;
        if (elements.srcCountSF) elements.srcCountSF.textContent = data.sources['Snowflake'] || 0;

        // Category counts
        elements.countAll.textContent = data.total || 0;
        elements.countFeature.textContent = data.categories['Feature'] || 0;
        elements.countChanged.textContent = data.categories['Changed'] || 0;
        elements.countIssue.textContent = data.categories['Issue'] || 0;
        elements.countDeprecated.textContent = data.categories['Deprecated'] || 0;
    }

    // --- Filter & Render Logic ---
    function getFilteredItems() {
        let filtered = state.items.filter(item => {
            // Source Filter
            if (state.activeSource !== 'ALL' && item.source !== state.activeSource) {
                return false;
            }
            // Category Filter
            if (state.activeCategory !== 'ALL' && item.category !== state.activeCategory) {
                return false;
            }
            // Search Query Filter
            if (state.searchQuery) {
                const q = state.searchQuery.toLowerCase();
                const matchText = (item.text || '').toLowerCase();
                const matchDate = (item.date || '').toLowerCase();
                const matchCat = (item.category || '').toLowerCase();
                const matchSrc = (item.source_name || item.source || '').toLowerCase();
                return matchText.includes(q) || matchDate.includes(q) || matchCat.includes(q) || matchSrc.includes(q);
            }
            return true;
        });

        // Sorting
        if (state.sortBy === 'oldest') {
            filtered = [...filtered].reverse();
        }

        return filtered;
    }

    function renderFeed() {
        const filtered = getFilteredItems();

        if (filtered.length === 0) {
            elements.feedList.innerHTML = '';
            elements.emptyState.classList.remove('hidden');
            return;
        }

        elements.emptyState.classList.add('hidden');

        // Group items by release date
        const grouped = {};
        filtered.forEach(item => {
            if (!grouped[item.date]) {
                grouped[item.date] = [];
            }
            grouped[item.date].push(item);
        });

        let html = '';
        for (const [date, items] of Object.entries(grouped)) {
            html += `
                <div class="date-group">
                    <div class="date-header">
                        <span class="date-title">${escapeHtml(date)}</span>
                        <span class="date-badge">${items.length} update${items.length > 1 ? 's' : ''}</span>
                    </div>
                    <div class="date-cards">
                        ${items.map(item => renderNoteCard(item)).join('')}
                    </div>
                </div>
            `;
        }

        elements.feedList.innerHTML = html;
        attachCardEventListeners();
    }

    function renderNoteCard(item) {
        const catClass = `badge-${(item.category || 'general').toLowerCase()}`;
        const srcClass = `src-badge-${(item.source || 'bigquery').toLowerCase()}`;
        const isSelected = state.selectedIds.has(item.id);

        const langDict = i18n[state.lang] || {};
        const catLabel = langDict[item.category] || item.category;
        const copyLabel = langDict['copy'] || 'Copy';
        const tweetLabel = langDict['tweet'] || 'Tweet';
        const linkedinLabel = langDict['linkedin'] || 'LinkedIn';
        const docsLabel = langDict['viewDocs'] || 'View Docs';
        const translateLabel = langDict['translate'] || 'Translate';

        let cardContentHtml = item.html;
        if (state.lang !== 'en' && item.translations && item.translations[state.lang]) {
            cardContentHtml = `<p class="translated-text">🌐 <em>(${state.lang.toUpperCase()}):</em> ${escapeHtml(item.translations[state.lang])}</p>`;
        }

        return `
            <div class="note-card ${isSelected ? 'selected' : ''}" data-id="${item.id}">
                <div class="card-top">
                    <div class="card-badges">
                        <span class="badge ${srcClass}">
                            ${escapeHtml(item.source_name || item.source)}
                        </span>
                        <span class="badge ${catClass}">
                            ${escapeHtml(catLabel)}
                        </span>
                    </div>
                    <div class="card-meta">
                        <input type="checkbox" class="card-checkbox" data-id="${item.id}" ${isSelected ? 'checked' : ''} title="Select item to tweet">
                    </div>
                </div>

                <div class="card-content" id="card-content-${item.id}">
                    ${cardContentHtml}
                </div>

                <div class="card-footer">
                    <a href="${item.link}" target="_blank" rel="noopener" class="link-gcp">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                        ${escapeHtml(docsLabel)}
                    </a>

                    <div class="card-actions">
                        <button class="btn btn-sm btn-secondary btn-translate-single" data-id="${item.id}" title="Translate news card content">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>
                            ${escapeHtml(translateLabel)}
                        </button>
                        <button class="btn btn-sm btn-secondary btn-copy-single" data-id="${item.id}" title="Copy release note text to clipboard">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                            ${escapeHtml(copyLabel)}
                        </button>
                        <button class="btn btn-sm btn-linkedin btn-linkedin-single" data-id="${item.id}" title="Share post to LinkedIn">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.88 8.56a1.68 1.68 0 0 0 1.68-1.68c0-.93-.75-1.69-1.68-1.69a1.69 1.69 0 0 0-1.69 1.69c0 .93.76 1.68 1.69 1.68m1.39 9.94v-8.37H5.5v8.37h2.77z"/></svg>
                            ${escapeHtml(linkedinLabel)}
                        </button>
                        <button class="btn btn-sm btn-card-tweet btn-tweet-single" data-id="${item.id}">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
                            ${escapeHtml(tweetLabel)}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    function attachCardEventListeners() {
        // Checkboxes
        document.querySelectorAll('.card-checkbox').forEach(chk => {
            chk.addEventListener('change', (e) => {
                const id = e.target.getAttribute('data-id');
                if (e.target.checked) {
                    state.selectedIds.add(id);
                } else {
                    state.selectedIds.delete(id);
                }
                updateBatchBar();
                const card = document.querySelector(`.note-card[data-id="${id}"]`);
                if (card) {
                    card.classList.toggle('selected', e.target.checked);
                }
            });
        });

        // Copy Buttons
        document.querySelectorAll('.btn-copy-single').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                const item = state.items.find(i => i.id === id);
                if (item) {
                    const textToCopy = `📌 BigQuery Release Note (${item.date})\nCategory: ${item.category}\n\n${item.text}\n\n🔗 Documentation: ${item.link}`;
                    navigator.clipboard.writeText(textToCopy).then(() => {
                        showToast('Release note text copied to clipboard!', 'success');
                    }).catch(err => {
                        console.error('Copy failed:', err);
                        showToast('Failed to copy text.', 'info');
                    });
                }
            });
        });

        // LinkedIn Share Buttons
        document.querySelectorAll('.btn-linkedin-single').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                const item = state.items.find(i => i.id === id);
                if (item) {
                    const postText = `📌 SQL Release Update: ${item.source_name || item.source}\nCategory: ${item.category}\n\n${item.text}\n\n🔗 Documentation: ${item.link}\n#SQL #DataEngineering #Databases #${item.source}`;
                    navigator.clipboard.writeText(postText);
                    const intentUrl = `https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(item.link)}`;
                    window.open(intentUrl, '_blank', 'noopener,noreferrer');
                    const msg = state.lang === 'ru' ? 'Ссылка открыта! Текст поста скопирован в буфер.' : (state.lang === 'pl' ? 'Link otwarty! Tekst skopiowany do schowka.' : 'LinkedIn opened! Post text copied to clipboard.');
                    showToast(msg, 'success');
                }
            });
        });

        // Translate Card Content Buttons
        document.querySelectorAll('.btn-translate-single').forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                const item = state.items.find(i => i.id === id);
                if (item) {
                    const targetLang = state.lang === 'en' ? 'ru' : state.lang;
                    const contentElem = document.getElementById(`card-content-${id}`);
                    if (contentElem) {
                        contentElem.innerHTML = `<p class="translated-text">⏳ <em>Translating to ${targetLang.toUpperCase()}...</em></p>`;
                    }
                    const translatedText = await translateCardItem(item, targetLang);
                    if (contentElem && translatedText) {
                        contentElem.innerHTML = `<p class="translated-text">🌐 <em>(${targetLang.toUpperCase()}):</em> ${escapeHtml(translatedText)}</p>`;
                        showToast(state.lang === 'ru' ? 'Текст карточки переведен!' : (state.lang === 'pl' ? 'Tekst karty przetłumaczony!' : 'Card text translated!'), 'success');
                    }
                }
            });
        });

        // Single Tweet Buttons
        document.querySelectorAll('.btn-tweet-single').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const id = btn.getAttribute('data-id');
                const item = state.items.find(i => i.id === id);
                if (item) {
                    openTweetModal(item);
                }
            });
        });
    }

    async function translateCardItem(item, targetLang) {
        if (!item || !targetLang || targetLang === 'en') return item ? item.text : '';
        if (!item.translations) item.translations = {};
        if (item.translations[targetLang]) return item.translations[targetLang];

        try {
            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: item.text, target_lang: targetLang })
            });
            const data = await response.json();
            if (data.translated) {
                item.translations[targetLang] = data.translated;
                return data.translated;
            }
        } catch (err) {
            console.error('Translation error:', err);
        }
        return item.text;
    }

    function updateBatchBar() {
        if (state.selectedIds.size > 0) {
            elements.batchBar.classList.remove('hidden');
            elements.batchCountText.textContent = `${state.selectedIds.size} note${state.selectedIds.size > 1 ? 's' : ''} selected`;
        } else {
            elements.batchBar.classList.add('hidden');
        }
    }

    // --- Search & Filter Listeners ---
    elements.searchInput.addEventListener('input', (e) => {
        state.searchQuery = e.target.value.trim();
        elements.clearSearchBtn.style.display = state.searchQuery ? 'block' : 'none';
        renderFeed();
    });

    elements.clearSearchBtn.addEventListener('click', () => {
        elements.searchInput.value = '';
        state.searchQuery = '';
        elements.clearSearchBtn.style.display = 'none';
        renderFeed();
    });

    if (elements.sourcePills) {
        elements.sourcePills.addEventListener('click', (e) => {
            const pill = e.target.closest('.pill-src');
            if (!pill) return;
            
            document.querySelectorAll('.pill-src').forEach(p => p.classList.remove('active'));
            pill.classList.add('active');
            
            state.activeSource = pill.getAttribute('data-source');
            renderFeed();
        });
    }

    elements.categoryPills.addEventListener('click', (e) => {
        const pill = e.target.closest('.pill');
        if (!pill) return;
        
        document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        
        state.activeCategory = pill.getAttribute('data-category');
        renderFeed();
    });

    elements.sortSelect.addEventListener('change', (e) => {
        state.sortBy = e.target.value;
        renderFeed();
    });

    // Export CSV Listener
    if (elements.exportCsvBtn) {
        elements.exportCsvBtn.addEventListener('click', () => {
            const filtered = getFilteredItems();
            if (filtered.length === 0) {
                showToast('No items available to export.', 'info');
                return;
            }

            const headers = ['Source', 'Date', 'Category', 'Summary', 'Documentation Link', 'Updated Timestamp'];
            const csvRows = [headers.join(',')];

            filtered.forEach(item => {
                const row = [
                    `"${(item.source_name || item.source || '').replace(/"/g, '""')}"`,
                    `"${(item.date || '').replace(/"/g, '""')}"`,
                    `"${(item.category || '').replace(/"/g, '""')}"`,
                    `"${(item.text || '').replace(/"/g, '""')}"`,
                    `"${(item.link || '').replace(/"/g, '""')}"`,
                    `"${(item.updated || '').replace(/"/g, '""')}"`
                ];
                csvRows.push(row.join(','));
            });

            const csvContent = 'data:text/csv;charset=utf-8,\uFEFF' + encodeURIComponent(csvRows.join('\n'));
            const link = document.createElement('a');
            link.setAttribute('href', csvContent);
            const todayStr = new Date().toISOString().split('T')[0];
            link.setAttribute('download', `bigquery_release_notes_${todayStr}.csv`);
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);

            showToast(`Exported ${filtered.length} release notes to CSV!`, 'success');
        });
    }

    elements.resetFiltersBtn.addEventListener('click', () => {
        elements.searchInput.value = '';
        state.searchQuery = '';
        elements.clearSearchBtn.style.display = 'none';
        state.activeCategory = 'ALL';
        document.querySelectorAll('.pill').forEach(p => {
            p.classList.toggle('active', p.getAttribute('data-category') === 'ALL');
        });
        renderFeed();
    });

    elements.refreshBtn.addEventListener('click', () => {
        loadReleaseNotes(true);
    });

    elements.deselectAllBtn.addEventListener('click', () => {
        state.selectedIds.clear();
        updateBatchBar();
        renderFeed();
    });

    elements.batchTweetBtn.addEventListener('click', () => {
        const selectedItems = state.items.filter(i => state.selectedIds.has(i.id));
        if (selectedItems.length > 0) {
            // Combine selected items into a single composite tweet item
            const first = selectedItems[0];
            const combinedText = selectedItems.map(i => `• ${i.category}: ${i.text}`).join('\n');
            openTweetModal({
                date: first.date,
                category: 'Summary',
                link: first.link,
                text: combinedText
            });
        }
    });

    // --- Text Selection Popover ---
    let selectedTextSnippet = '';

    document.addEventListener('mouseup', (e) => {
        const selection = window.getSelection();
        const selectedStr = selection.toString().trim();

        if (selectedStr.length > 10) {
            const range = selection.getRangeAt(0);
            const rect = range.getBoundingClientRect();
            
            // Position floating popover right above the selected text
            elements.selectionPopover.style.top = `${window.scrollY + rect.top}px`;
            elements.selectionPopover.style.left = `${window.scrollX + rect.left + (rect.width / 2)}px`;
            elements.selectionPopover.classList.remove('hidden');
            selectedTextSnippet = selectedStr;
        } else {
            if (!elements.selectionPopover.contains(e.target)) {
                elements.selectionPopover.classList.add('hidden');
            }
        }
    });

    elements.popoverTweetBtn.addEventListener('click', () => {
        elements.selectionPopover.classList.add('hidden');
        openTweetModal({
            date: 'Highlight',
            category: 'Snippet',
            link: 'https://docs.cloud.google.com/bigquery/docs/release-notes',
            text: selectedTextSnippet
        });
    });

    // --- Tweet Composer Modal ---
    function openTweetModal(item) {
        state.activeModalItem = item;
        elements.modalContextDate.textContent = item.date || 'Update';
        elements.modalContextBadge.textContent = item.category || 'Feature';
        elements.modalContextSnippet.textContent = (item.text || '').substring(0, 140) + '...';

        formatAndSetTweetText();
        elements.tweetModal.classList.remove('hidden');
        elements.tweetTextarea.focus();
    }

    function closeTweetModal() {
        elements.tweetModal.classList.add('hidden');
        state.activeModalItem = null;
    }

    function formatAndSetTweetText() {
        if (!state.activeModalItem) return;
        
        const item = state.activeModalItem;
        const prefix = `🚀 BigQuery Update (${item.date}) [${item.category}]: `;
        const tags = Array.from(state.activeHashtags).join(' ');
        const link = item.link ? `\n🔗 ${item.link}` : '';

        // Calculate available room for text body
        const reservedLen = prefix.length + link.length + tags.length + 5;
        const availableLen = Math.max(280 - reservedLen, 40);

        let bodyText = item.text || '';
        if (bodyText.length > availableLen) {
            bodyText = bodyText.substring(0, availableLen).rsplit(' ', 1)[0] + '...';
        }

        const fullTweet = `${prefix}${bodyText}${link}\n${tags}`.trim();
        elements.tweetTextarea.value = fullTweet;
        updateCharCounter();
    }

    // Polyfill string rsplit
    String.prototype.rsplit = function(sep, maxsplit) {
        const split = this.split(sep);
        return maxsplit ? [split.slice(0, -maxsplit).join(sep), ...split.slice(-maxsplit)] : split;
    };

    function updateCharCounter() {
        const val = elements.tweetTextarea.value;
        const len = val.length;
        elements.charCountText.textContent = `${len} / 280`;

        // Update progress ring offset (36px SVG circle circumference = 100)
        const percent = Math.min(len / 280, 1);
        const offset = 100 - (percent * 100);
        elements.charRingProgress.style.strokeDashoffset = offset;

        // Color warnings
        elements.charCountText.classList.remove('warning', 'danger');
        if (len > 280) {
            elements.charCountText.classList.add('danger');
            elements.charRingProgress.style.stroke = 'var(--accent-rose)';
        } else if (len > 240) {
            elements.charCountText.classList.add('warning');
            elements.charRingProgress.style.stroke = 'var(--accent-amber)';
        } else {
            elements.charRingProgress.style.stroke = 'var(--accent-blue)';
        }
    }

    elements.tweetTextarea.addEventListener('input', updateCharCounter);

    // Hashtag Chips Click
    document.querySelectorAll('.tag-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const tag = chip.getAttribute('data-tag');
            if (state.activeHashtags.has(tag)) {
                state.activeHashtags.delete(tag);
                chip.classList.remove('active');
            } else {
                state.activeHashtags.add(tag);
                chip.classList.add('active');
            }
            formatAndSetTweetText();
        });
    });

    elements.autoFormatBtn.addEventListener('click', () => {
        formatAndSetTweetText();
        showToast('Formated tweet to fit 280 characters', 'info');
    });

    elements.modalCloseBtn.addEventListener('click', closeTweetModal);
    elements.modalCancelBtn.addEventListener('click', closeTweetModal);

    elements.tweetModal.addEventListener('click', (e) => {
        if (e.target === elements.tweetModal) {
            closeTweetModal();
        }
    });

    // Copy Tweet
    elements.copyTweetBtn.addEventListener('click', () => {
        const text = elements.tweetTextarea.value;
        navigator.clipboard.writeText(text).then(() => {
            showToast('Tweet copied to clipboard!', 'success');
        }).catch(err => {
            console.error('Failed to copy tweet:', err);
        });
    });

    // Post to X / Twitter Intent
    elements.postXBtn.addEventListener('click', () => {
        const text = elements.tweetTextarea.value;
        const intentUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(text)}`;
        window.open(intentUrl, '_blank', 'noopener,noreferrer');
        showToast('Opening X (Twitter) composer...', 'info');
        closeTweetModal();
    });

    // --- Toast Notifications ---
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        
        const icon = type === 'success' 
            ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>`
            : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>`;
            
        toast.innerHTML = `${icon} <span>${escapeHtml(message)}</span>`;
        elements.toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transform = 'translateY(10px)';
            toast.style.transition = 'all 0.25s ease';
            setTimeout(() => toast.remove(), 250);
        }, 3000);
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/[&<>"']/g, match => {
            const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
            return map[match];
        });
    }

    // Load initial feed
    loadReleaseNotes();
});
