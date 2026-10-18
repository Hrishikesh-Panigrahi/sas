"""Defaulter lists: students below the attendance threshold, as data and as PDFs.

`defaulters()` gathers the figures (always through `attendance.stats`, so the
rules for what counts as attended live in one place); `defaulter_list_pdf()`
and `warning_letters_pdf()` turn them into printable documents.
"""
import io
from xml.sax.saxutils import escape

from django.conf import settings
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (HRFlowable, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from sas.permissions import in_department
from .models import Assign_cls
from .stats import assignment_report, lectures_needed, student_summary

MIN_THRESHOLD, MAX_THRESHOLD = 50, 100


def clean_threshold(value):
    """A threshold from user input: an integer clamped to 50-100, else the setting."""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return settings.ATTENDANCE_THRESHOLD
    return max(MIN_THRESHOLD, min(MAX_THRESHOLD, value))


def needed_for(present, total, threshold):
    """Lectures in a row needed to reach `threshold`; None when it can't be reached."""
    if threshold == settings.ATTENDANCE_THRESHOLD:
        return lectures_needed(present, total)
    # Same formula as stats.lectures_needed, in whole numbers to avoid float error
    # (e.g. 80%: 2 / 0.2 comes out as 10.000000000000002).
    if not total or present * 100 >= threshold * total:
        return 0
    if threshold >= 100:
        return None
    return -(-(threshold * total - 100 * present) // (100 - threshold))


def _student_order(entry):
    stu = entry['student']
    return (entry['cls'].class_name.lower(), stu.roll_no is None, stu.roll_no or 0,
            (stu.user.first_name or '').lower(), (stu.user.last_name or '').lower(), stu.id)


def defaulters(user, cls=None, threshold=None):
    """Students below the threshold in at least one course.

    Covers the user's department, or only `cls` when given (the caller checks
    that the class is one the user may see). Returns a dict with:
    - `sections`: one per class + course (`Assign_cls`), ordered by class name
      and course code, each with the `assignment_report` rows below the
      threshold (worst first) under `students`;
    - `students`: one entry per student listed, in class and roll order, with
      their `student_summary` and the `courses` they are short in;
    - `counts`: students listed, courses (class + course pairs) affected, and
      classes affected.
    """
    threshold = settings.ATTENDANCE_THRESHOLD if threshold is None else clean_threshold(threshold)
    if cls is not None:
        assignments = Assign_cls.objects.filter(cls=cls)
    else:
        assignments = in_department(Assign_cls.objects.all(), user, 'cls__department')
    assignments = assignments.select_related(
        'cls__class_teacher__user', 'course', 'teacher__user',
    ).order_by('cls__class_name', 'course__code', 'id')

    sections, by_student = [], {}
    for assign in assignments:
        rows, lectures = assignment_report(assign)
        below = [r for r in rows
                 if r['total'] >= 1 and r['percent'] is not None and r['percent'] < threshold]
        below.sort(key=lambda r: r['percent'])   # stable, so ties stay in roll order
        sections.append({'assign': assign, 'cls': assign.cls, 'course': assign.course,
                         'teacher': assign.teacher.user, 'lectures': lectures, 'students': below})
        for row in below:
            stu = row['student']
            entry = by_student.setdefault(stu.id, {'student': stu, 'cls': assign.cls, 'courses': []})
            entry['courses'].append({
                'assign': assign, 'code': assign.course.code, 'name': assign.course.name,
                'present': row['present'], 'total': row['total'], 'percent': row['percent'],
                'needed': needed_for(row['present'], row['total'], threshold),
            })

    students = sorted(by_student.values(), key=_student_order)
    for entry in students:
        summary = student_summary(entry['student'])
        entry['summary'] = summary
        entry['overall_short'] = summary['percent'] is not None and summary['percent'] < threshold

    affected = [s for s in sections if s['students']]
    if cls is not None:
        department = cls.department or user.department or ''
    else:
        department = user.department or ''
    return {
        'threshold': threshold,
        'cls': cls,
        'department': department,
        'date': timezone.localdate(),
        'sections': sections,
        'affected_sections': affected,
        'students': students,
        'counts': {
            'students': len(students),
            'courses': len(affected),
            'classes': len({s['cls'].id for s in affected}),
            'classes_in_scope': len({s['cls'].id for s in sections}),
        },
    }


# ---------------------------------------------------------------------------
# PDF building blocks
# ---------------------------------------------------------------------------

INK = colors.HexColor('#0f172a')
ACCENT = colors.HexColor('#4f46e5')
MUTED = colors.HexColor('#64748b')
GRID = colors.HexColor('#cbd5e1')
HEAD_BG = colors.HexColor('#f1f5f9')

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm
FRAME_PAD = 6   # SimpleDocTemplate's frame pads its content by 6pt on each side
LEFT, RIGHT = MARGIN + FRAME_PAD, PAGE_W - MARGIN - FRAME_PAD
CONTENT_W = RIGHT - LEFT

_base = ParagraphStyle('base', fontName='Helvetica', fontSize=9.5, leading=13.5, textColor=INK)
STYLES = {
    'body': _base,
    'letter': ParagraphStyle('letter', parent=_base, fontSize=10.5, leading=15.5, spaceAfter=8),
    'small': ParagraphStyle('small', parent=_base, fontSize=8.5, leading=11.5, textColor=MUTED),
    'eyebrow': ParagraphStyle('eyebrow', parent=_base, fontName='Helvetica-Bold', fontSize=8.5,
                              leading=11, textColor=ACCENT),
    'title': ParagraphStyle('title', parent=_base, fontName='Helvetica-Bold', fontSize=17,
                            leading=21, spaceBefore=2, spaceAfter=4),
    'letterhead': ParagraphStyle('letterhead', parent=_base, fontName='Helvetica-Bold',
                                 fontSize=14, leading=18, textColor=ACCENT),
    'h2': ParagraphStyle('h2', parent=_base, fontName='Helvetica-Bold', fontSize=11.5, leading=15,
                         textColor=ACCENT, spaceBefore=12, spaceAfter=1, keepWithNext=1),
    'meta': ParagraphStyle('meta', parent=_base, fontSize=8.5, leading=11.5, textColor=MUTED,
                           spaceAfter=5, keepWithNext=1),
    'cell': ParagraphStyle('cell', parent=_base, fontSize=9, leading=11.5),
    'cell_bold': ParagraphStyle('cell_bold', parent=_base, fontName='Helvetica-Bold',
                                fontSize=9, leading=11.5),
    'right': ParagraphStyle('right', parent=_base, alignment=TA_RIGHT),
    'sig': ParagraphStyle('sig', parent=_base, fontSize=9, leading=12),
    'sig_muted': ParagraphStyle('sig_muted', parent=_base, fontSize=8.5, leading=11, textColor=MUTED),
}


def _p(text, style='body'):
    return Paragraph(text, STYLES[style])


def _esc(value):
    return escape(str(value if value is not None else ''))


def _name(stu):
    return stu.user.full_name or stu.user.email


def _date(day):
    return '%d %s' % (day.day, day.strftime('%B %Y'))


def _department_heading(department):
    return 'Department of %s' % department if department else 'All departments'


def _table(data, widths, numeric_from=None, extra=()):
    """A table with a light grey header row, thin grid lines and numbers right-aligned."""
    style = [
        ('FONT', (0, 0), (-1, 0), 'Helvetica-Bold', 8.5),
        ('FONT', (0, 1), (-1, -1), 'Helvetica', 9),
        ('TEXTCOLOR', (0, 0), (-1, -1), INK),
        ('BACKGROUND', (0, 0), (-1, 0), HEAD_BG),
        ('GRID', (0, 0), (-1, -1), 0.4, GRID),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]
    if numeric_from is not None:
        style.append(('ALIGN', (numeric_from, 0), (-1, -1), 'RIGHT'))
    style.extend(extra)
    table = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    table.setStyle(TableStyle(style))
    return table


def _signatures(left, right):
    """Two signature lines side by side; each side is a list of lines under the rule."""
    gap = 24 * mm
    col = (CONTENT_W - gap) / 2

    def block(lines):
        return [_p(_esc(lines[0]), 'sig')] + [_p(_esc(line), 'sig_muted') for line in lines[1:]]

    table = Table([['', '', ''], [block(left), '', block(right)]],
                  colWidths=[col, gap, col], rowHeights=[16 * mm, None], hAlign='LEFT')
    table.setStyle(TableStyle([
        ('LINEABOVE', (0, 1), (0, 1), 0.6, INK),
        ('LINEABOVE', (2, 1), (2, 1), 0.6, INK),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 1), (-1, 1), 4),
    ]))
    return table


def _rule(width=1.2, space_after=8):
    return HRFlowable(width='100%', thickness=width, color=ACCENT, spaceBefore=4,
                      spaceAfter=space_after)


def _canvas_maker(footer='', numbered=True):
    """A canvas that draws a footer with "Page X of Y" once the page count is known."""

    class FooterCanvas(canvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            count = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._footer(count)
                super().showPage()
            super().save()

        def _footer(self, count):
            if not (footer or numbered):
                return
            self.saveState()
            self.setStrokeColor(GRID)
            self.setLineWidth(0.4)
            self.line(LEFT, 13 * mm, RIGHT, 13 * mm)
            self.setFont('Helvetica', 7.5)
            self.setFillColor(MUTED)
            if footer:
                self.drawString(LEFT, 9 * mm, footer)
            if numbered:
                self.drawRightString(RIGHT, 9 * mm,
                                     'Page %d of %d' % (self._pageNumber, count))
            self.restoreState()

    return FooterCanvas


def _build(flowables, title, author, footer, numbered=True):
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4, leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16 * mm, bottomMargin=20 * mm,
        title=title, author=author, subject=title, creator='SAS',
        invariant=1,   # fixed metadata date and document id, so output only varies with the data
    )
    doc.build(flowables, canvasmaker=_canvas_maker(footer, numbered))
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Defaulter list
# ---------------------------------------------------------------------------

def defaulter_list_pdf(report):
    """The department's (or one class's) defaulter list as PDF bytes."""
    threshold = report['threshold']
    cls = report['cls']
    department = _department_heading(report['department'])
    scope = cls.class_name if cls else 'All classes'
    when = _date(report['date'])

    story = [
        _p(_esc(department.upper()), 'eyebrow'),
        _p('Attendance defaulter list', 'title'),
        _p('<b>Class:</b> %s &nbsp;&nbsp;&middot;&nbsp;&nbsp; <b>Threshold:</b> %d%% '
           '&nbsp;&nbsp;&middot;&nbsp;&nbsp; <b>Generated:</b> %s'
           % (_esc(scope), threshold, when), 'body'),
        _rule(),
    ]

    affected = report['affected_sections']
    if affected:
        story.append(_p(
            'The students below have attended fewer than %d%% of the lectures held in the '
            'course named, according to attendance records as of %s. Percentages are rounded '
            'to the nearest whole number.' % (threshold, when), 'body'))
    else:
        story.append(_p('No student is below %d%% in any course for this selection, according '
                        'to attendance records as of %s.' % (threshold, when), 'body'))

    widths = [16 * mm, CONTENT_W - 78 * mm, 22 * mm, 22 * mm, 18 * mm]
    for section in affected:
        course, teacher = section['course'], section['teacher']
        story.append(_p('%s &middot; %s' % (_esc(course.code), _esc(course.name)), 'h2'))
        story.append(_p('Class %s &nbsp;&middot;&nbsp; Teacher: %s &nbsp;&middot;&nbsp; '
                        '%d lecture%s held' % (
                            _esc(section['cls'].class_name),
                            _esc(teacher.full_name or teacher.email),
                            section['lectures'], '' if section['lectures'] == 1 else 's'), 'meta'))
        data = [['Roll', 'Name', 'Attended', 'Lectures', '%']]
        for row in section['students']:
            stu = row['student']
            data.append([stu.roll_no if stu.roll_no is not None else '-',
                         _p(_esc(_name(stu)), 'cell'),
                         row['present'], row['total'], '%d%%' % row['percent']])
        story.append(_table(data, widths, numeric_from=2, extra=[
            ('FONT', (4, 1), (4, -1), 'Helvetica-Bold', 9),
        ]))

    # Summary of every class + course in scope, including those with nobody below.
    counts = report['counts']
    summary = [_p('Summary', 'h2'), _p(
        '%d student%s below %d%% in at least one course; %d course%s affected across %d class%s.'
        % (counts['students'], '' if counts['students'] == 1 else 's', threshold,
           counts['courses'], '' if counts['courses'] == 1 else 's',
           counts['classes'], '' if counts['classes'] == 1 else 'es'), 'meta')]
    if report['sections']:
        data = [['Course', 'Class', 'Teacher', 'Lectures', 'Below %d%%' % threshold]]
        for section in report['sections']:
            teacher = section['teacher']
            data.append([
                _p('<b>%s</b> %s' % (_esc(section['course'].code), _esc(section['course'].name)), 'cell'),
                _p(_esc(section['cls'].class_name), 'cell'),
                _p(_esc(teacher.full_name or teacher.email), 'cell'),
                section['lectures'], len(section['students']),
            ])
        summary.append(_table(
            data, [CONTENT_W - 116 * mm, 26 * mm, 46 * mm, 20 * mm, 24 * mm], numeric_from=3))
    story.extend(summary)

    class_teacher = cls.class_teacher.user if cls and cls.class_teacher else None
    left = ['Class teacher'] + ([class_teacher.full_name or class_teacher.email] if class_teacher else [])
    story.append(Spacer(1, 14 * mm))
    story.append(KeepTogether([_signatures(left, ['Head of Department', department])]))

    footer = 'Attendance defaulter list  ·  %s  ·  %s  ·  below %d%%' % (
        department, scope, threshold)
    return _build(story, 'Attendance defaulter list', department, footer)


# ---------------------------------------------------------------------------
# Warning letters
# ---------------------------------------------------------------------------

def _letter(entry, threshold, day):
    stu, cls = entry['student'], entry['cls']
    name = _esc(_name(stu))
    first = _esc(stu.user.first_name or _name(stu))
    department = _department_heading(cls.department)
    teacher = cls.class_teacher.user if cls.class_teacher else None
    teacher_name = _esc(teacher.full_name or teacher.email) if teacher else ''
    roll = ', roll no. %s' % stu.roll_no if stu.roll_no is not None else ''
    plural = len(entry['courses']) != 1

    flow = [
        _p(_esc(department), 'letterhead'),
        _p('Student attendance notice', 'small'),
        _rule(space_after=10),
        _p(_date(day), 'right'),
        Spacer(1, 6 * mm),
        _p('To the parent/guardian of <b>%s</b> (%s%s)' % (name, _esc(cls.class_name), roll), 'letter'),
        _p('<b>Subject: Attendance below the required %d%%</b>' % threshold, 'letter'),
        _p('Dear Parent/Guardian,', 'letter'),
        _p('We are writing to keep you informed about %s’s attendance this semester. The '
           'college asks every student to attend at least %d%% of the lectures held in each '
           'course, because regular attendance makes a real difference to how well students '
           'keep up with their coursework.' % (first, threshold), 'letter'),
        _p('According to our records as of %s, %s’s attendance is below this level in the '
           'following course%s:' % (_date(day), first, 's' if plural else ''), 'letter'),
    ]

    data = [['Course', 'Attended', 'Attendance', 'Lectures needed']]
    for course in entry['courses']:
        needed = course['needed']
        data.append([
            _p('<b>%s</b> %s' % (_esc(course['code']), _esc(course['name'])), 'cell'),
            '%d of %d' % (course['present'], course['total']),
            '%d%%' % course['percent'],
            '-' if needed is None else needed,
        ])
    flow.append(_table(data, [CONTENT_W - 96 * mm, 28 * mm, 28 * mm, 40 * mm], numeric_from=1,
                       extra=[('FONT', (2, 1), (2, -1), 'Helvetica-Bold', 9)]))
    flow.append(Spacer(1, 2 * mm))
    note = ('“Lectures needed” is the number of further lectures in a row %s would need '
            'to attend to reach %d%% in that course.' % (first, threshold))
    summary = entry['summary']
    if summary['percent'] is not None:
        note += ' Overall attendance across all courses is %d%% (%d of %d lectures).' % (
            summary['percent'], summary['present'], summary['total'])
    flow.append(_p(note, 'small'))
    flow.append(Spacer(1, 5 * mm))

    contact = 'the class teacher, %s,' % teacher_name if teacher_name else 'the class teacher'
    flow += [
        _p('We would be grateful if you could talk with %s about this and help ensure regular '
           'attendance from now on. If there are circumstances we should know about, such as '
           'illness or a family matter, or if you would like to discuss %s’s progress, '
           'please contact %s who will be glad to help.' % (first, first, contact), 'letter'),
        _p('Thank you for your support.', 'letter'),
        _p('Yours sincerely,', 'letter'),
        Spacer(1, 4 * mm),
        _signatures(
            [teacher.full_name or teacher.email, 'Class teacher, %s' % cls.class_name] if teacher
            else ['Class teacher', cls.class_name],
            ['Head of Department', department]),
    ]
    return flow


def warning_letters_pdf(report, entries=None):
    """One letter per page for each listed student (or just `entries`), as PDF bytes."""
    entries = report['students'] if entries is None else entries
    threshold, day = report['threshold'], report['date']
    department = _department_heading(report['department'])
    story = []
    for i, entry in enumerate(entries):
        if i:
            story.append(PageBreak())
        story.extend(_letter(entry, threshold, day))
    if not story:
        story = [
            _p(_esc(department), 'letterhead'),
            _p('Student attendance notice', 'small'),
            _rule(space_after=10),
            _p('No student is below %d%% in any course for this selection, so there are no '
               'letters to print.' % threshold, 'letter'),
        ]
    return _build(story, 'Attendance warning letters', department, footer='', numbered=False)
