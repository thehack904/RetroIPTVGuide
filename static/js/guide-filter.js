(function() {
  'use strict';

  const searchInput = document.getElementById('channelSearch');
  const clearBtn = document.getElementById('clearSearch');
  const resultCount = document.getElementById('searchResultCount');

  if (!searchInput) return;

  function filterGuide() {
    const query = searchInput.value.toLowerCase().trim();
    const rows = Array.from(document.querySelectorAll('.guide-row'));
    
    // Don't filter the time header row
    const channelRows = rows.filter(row => {
      return row.querySelector('.chan-col') && 
             !row.classList.contains('hide-in-grid');
    });

    if (!query) {
      // Show all rows
      channelRows.forEach(row => row.classList.remove('hidden-by-search'));
      resultCount.textContent = '';
      return;
    }

    let visibleCount = 0;

    channelRows.forEach(row => {
      const chanName = row.querySelector('.chan-name');
      const programs = Array.from(row.querySelectorAll('.programme, .program'));
      
      let matchFound = false;

      // Check channel name
      if (chanName && chanName.textContent.toLowerCase().includes(query)) {
        matchFound = true;
      }

      // Check program titles
      if (!matchFound) {
        for (const prog of programs) {
          const title = prog.dataset.title || prog.textContent;
          if (title && title.toLowerCase().includes(query)) {
            matchFound = true;
            break;
          }
        }
      }

      if (matchFound) {
        row.classList.remove('hidden-by-search');
        visibleCount++;
      } else {
        row.classList.add('hidden-by-search');
      }
    });

    resultCount.textContent = `${visibleCount} of ${channelRows.length} channels`;
  }

  function clearSearch() {
    searchInput.value = '';
    filterGuide();
    searchInput.focus();
  }

  // Event listeners
  searchInput.addEventListener('input', filterGuide);
  searchInput.addEventListener('keyup', (e) => {
    if (e.key === 'Escape') clearSearch();
  });
  
  if (clearBtn) {
    clearBtn.addEventListener('click', clearSearch);
  }

  // Initial state
  filterGuide();
})();
