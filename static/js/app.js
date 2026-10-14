/* SAS — page behaviour. Every feature is opt-in through data-* attributes. */
(function ($) {
  'use strict';

  // Mobile sidebar.
  $(document).on('click', '[data-toggle-sidebar]', function () {
    document.body.classList.toggle('sidebar-open');
  });
  $(document).on('keydown', function (e) {
    if (e.key === 'Escape') document.body.classList.remove('sidebar-open');
  });

  // Success messages fade away on their own; errors stay until dismissed.
  setTimeout(function () { $('.alert-success.alert-dismissible').alert('close'); }, 6000);

  // Searchable, sortable tables: <table data-datatable data-order='[[0,"asc"]]'>.
  $('table[data-datatable]').each(function () {
    var $t = $(this);
    $t.DataTable({
      order: $t.data('order') || [],
      pageLength: $t.data('page-length') || 25,
      lengthMenu: [10, 25, 50, 100],
      autoWidth: false,
      columnDefs: [{ targets: 'no-sort', orderable: false, searchable: false }],
      language: {
        search: '',
        searchPlaceholder: $t.data('search') || 'Search…',
        lengthMenu: 'Show _MENU_',
        info: '_START_–_END_ of _TOTAL_',
        infoEmpty: 'Nothing to show',
        infoFiltered: '(filtered from _MAX_)',
        zeroRecords: 'No matches. Try a different search.',
        paginate: { previous: '‹', next: '›' }
      },
      dom: "<'row'<'col-sm-8'f><'col-sm-4'l>>" + "<'row'<'col-12'tr>>" + "<'row'<'col-sm-5'i><'col-sm-7'p>>"
    });
  });

  // Confirm before submitting destructive forms: <form data-confirm="Delete this?">.
  $(document).on('submit', 'form[data-confirm]', function (e) {
    if (!window.confirm(this.getAttribute('data-confirm'))) e.preventDefault();
  });

  // Show / hide password.
  $(document).on('click', '.password-toggle', function () {
    var input = this.parentNode.querySelector('input');
    var show = input.type === 'password';
    input.type = show ? 'text' : 'password';
    this.querySelector('i').className = show ? 'fas fa-eye-slash' : 'fas fa-eye';
    this.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
  });

  // Live filter: <input data-filter="#list"> hides children of #list that
  // don't contain the text (matching against data-search or text content).
  $(document).on('input', '[data-filter]', function () {
    var q = this.value.trim().toLowerCase();
    $(this.getAttribute('data-filter')).children('[data-item]').each(function () {
      var hay = (this.getAttribute('data-search') || this.textContent).toLowerCase();
      this.style.display = hay.indexOf(q) === -1 ? 'none' : '';
    });
  });

  // Checklists: highlight checked rows and keep a count up to date.
  function refreshChecklist(list) {
    var $list = $(list);
    var boxes = $list.find('input[type="checkbox"][data-check]');
    boxes.each(function () { $(this).closest('.check-item').toggleClass('is-checked', this.checked); });
    var count = boxes.filter(':checked').length;
    $('[data-count-for="#' + list.id + '"]').text(count + ' selected');
  }
  $('[data-checklist]').each(function () { refreshChecklist(this); });
  $(document).on('change', '[data-checklist] input[data-check]', function () {
    refreshChecklist($(this).closest('[data-checklist]')[0]);
  });
  // <button data-check-all="#list" data-value="true"> ticks every visible box.
  $(document).on('click', '[data-check-all]', function () {
    var target = this.getAttribute('data-check-all');
    var value = this.getAttribute('data-value') === 'true';
    $(target).children('[data-item]:visible').find('input[data-check]').prop('checked', value).trigger('change');
  });

  // Class form: a course's teacher picker is only active when the course is ticked,
  // and picking a teacher ticks the course.
  $(document).on('change', '.course-row input[data-check]', function () {
    $(this).closest('.course-row').find('select').prop('disabled', !this.checked);
  });
  $(document).on('change', '.course-row select', function () {
    var box = $(this).closest('.course-row').find('input[data-check]');
    if (this.value && !box.prop('checked')) box.prop('checked', true).trigger('change');
  });
  $('.course-row input[data-check]').trigger('change');

  // AI analysis panels load after the page so charts never wait on the AI.
  function loadPanel(panel, refresh) {
    var url = panel.getAttribute('data-url') + (refresh ? '&refresh=1' : '');
    panel.classList.add('is-loading');
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) { panel.innerHTML = html; })
      .catch(function () {
        panel.textContent = '';
        var p = document.createElement('p');
        p.className = 'text-muted small mb-0';
        p.textContent = "Couldn't load the analysis. Reload the page to try again.";
        panel.appendChild(p);
      })
      .then(function () { panel.classList.remove('is-loading'); });
  }
  $('[data-ai-panel][data-url]').each(function () { loadPanel(this, false); });
  $(document).on('click', '[data-ai-refresh]', function () {
    loadPanel($(this).closest('[data-ai-panel]')[0], true);
  });

  // Attendance marking.
  var $mark = $('[data-mark-form]');
  if ($mark.length) {
    var dirty = false;
    var update = function () {
      var present = $mark.find('input.present:checked').length;
      var absent = $mark.find('input.absent:checked').length;
      $('[data-tally-present]').text(present);
      $('[data-tally-absent]').text(absent);
      $mark.find('.mark-row').each(function () {
        $(this).toggleClass('is-absent', $(this).find('input.absent').is(':checked'));
      });
    };
    $mark.on('change', 'input[type="radio"]', function () { dirty = true; update(); });
    $('[data-mark-all]').on('click', function () {
      var cls = this.getAttribute('data-mark-all');
      $mark.find('.mark-row:visible input.' + cls).prop('checked', true);
      dirty = true;
      update();
    });
    $mark.on('submit', function () { dirty = false; });
    window.addEventListener('beforeunload', function (e) {
      if (dirty) { e.preventDefault(); e.returnValue = ''; }
    });
    update();
  }
})(jQuery);
