from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count, Q, Sum
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.http import HttpResponseForbidden, FileResponse
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
import statistics
import csv
import io
import re

from .models import (
    User, Course, Enrollment, FacultyAdvisor, Exam, ExamSection,
    AnswerScript, Mark, Query, TAAssignment, Notification
)
from .forms import (
    LoginForm, CourseForm, ExamForm, AnswerScriptUploadForm,
    MarkForm, QueryForm, QueryResponseForm, TAAssignmentForm,
    FacultyAdvisorForm, AdminAddFacultyForm, AdminAddStudentForm, AdminAddTAForm,
    AdminForceEnrollForm, StudentSignupForm
)


def role_required(role):
    """Decorator to restrict views to a specific role."""
    def decorator(view_func):
        @wraps(view_func)
        @never_cache
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role != role and not (request.user.is_superuser and role == 'admin'):
                current_role = request.user.role if getattr(request.user, 'role', None) else (
                    'admin' if request.user.is_superuser else None
                )
                if current_role:
                    messages.warning(request, 'Redirected to your own dashboard.')
                    return redirect(f'{current_role}_dashboard')
                return redirect('login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _normalize_text(value):
    return re.sub(r'[^a-z0-9]+', '', (value or '').lower())


def _course_search_suggestions(courses):
    suggestions = set()
    for course in courses:
        professor_name = f"{course.professor.first_name} {course.professor.last_name}".strip()
        suggestions.add(course.code)
        suggestions.add(course.name)
        suggestions.add(course.professor.username)
        if professor_name:
            suggestions.add(professor_name)
    return sorted(s for s in suggestions if s)


def _filter_courses_by_query(courses, query):
    normalized_query = _normalize_text(query)
    if not normalized_query:
        return courses

    filtered = []
    for course in courses:
        professor_name = f"{course.professor.first_name} {course.professor.last_name}".strip()
        searchable_text = " ".join([
            course.code,
            course.name,
            course.semester,
            course.department or '',
            course.professor.username,
            professor_name,
        ])
        if normalized_query in _normalize_text(searchable_text):
            filtered.append(course)
    return filtered


def _is_allowed_script_file(file_obj):
    allowed_extensions = {
        '.pdf', '.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif', '.tif', '.tiff'
    }
    extension = Path(file_obj.name).suffix.lower()
    return extension in allowed_extensions


def _extract_decimal_from_cell(value):
    cleaned = str(value or '').strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace(',', '')
    if not re.fullmatch(r'-?\d+(?:\.\d+)?%?', cleaned):
        return None

    try:
        return Decimal(cleaned.rstrip('%'))
    except (InvalidOperation, ValueError):
        return None


def _redirect_professor_request_page(request):
    return redirect('professor_dashboard')


def _permission_summary(assignment):
    return (
        f"Upload Scripts: {'Yes' if assignment.can_upload_scripts else 'No'}, "
        f"Resolve Queries: {'Yes' if assignment.can_resolve_queries else 'No'}, "
        f"Update Marks: {'Yes' if assignment.can_update_marks else 'No'}"
    )


def _build_course_student_lookup(course):
    approved_enrollments = Enrollment.objects.filter(
        course=course, status='approved'
    ).select_related('student')

    student_lookup = {}
    for enrollment in approved_enrollments:
        student = enrollment.student
        keys = [
            student.roll_number,
            student.username,
            f"{student.first_name} {student.last_name}".strip(),
            f"{student.last_name} {student.first_name}".strip(),
        ]
        for key in keys:
            normalized_key = _normalize_text(key)
            if normalized_key:
                student_lookup[normalized_key] = student
    return student_lookup


def _import_csv_marks(csv_file, exam):
    data_set = csv_file.read().decode('utf-8-sig', errors='ignore')

    try:
        dialect = csv.Sniffer().sniff(data_set[:2048], delimiters=',;\t|')
    except csv.Error:
        dialect = csv.excel

    rows = list(csv.reader(io.StringIO(data_set), dialect=dialect))
    if not rows:
        return 0, 0, 'The CSV file is empty.'

    student_lookup = _build_course_student_lookup(exam.course)

    header_tokens = [_normalize_text(col) for col in rows[0]]
    has_header = any(token in {
        'roll', 'rollno', 'rollnumber', 'username', 'name', 'student', 'marks', 'score', 'total'
    } for token in header_tokens)

    marks_column_idx = None
    student_column_indexes = []
    if has_header:
        for idx, token in enumerate(header_tokens):
            if token in {'marks', 'mark', 'score', 'totalscore', 'totalmarks'}:
                marks_column_idx = idx
            if token in {'roll', 'rollno', 'rollnumber', 'username', 'student', 'studentname', 'name'}:
                student_column_indexes.append(idx)

    data_rows = rows[1:] if has_header else rows

    saved_count = 0
    skipped_count = 0

    for row in data_rows:
        if not row:
            continue

        raw_cells = [str(cell).strip() for cell in row]
        if not any(raw_cells):
            continue

        matched_student = None
        matched_idx = None

        if has_header and student_column_indexes:
            for idx in student_column_indexes:
                if idx >= len(raw_cells):
                    continue
                matched_student = student_lookup.get(_normalize_text(raw_cells[idx]))
                if matched_student:
                    matched_idx = idx
                    break

        if not matched_student:
            for idx, cell in enumerate(raw_cells):
                matched_student = student_lookup.get(_normalize_text(cell))
                if matched_student:
                    matched_idx = idx
                    break

        parsed_marks = None
        if marks_column_idx is not None and marks_column_idx < len(raw_cells):
            parsed_marks = _extract_decimal_from_cell(raw_cells[marks_column_idx])

        if parsed_marks is None:
            for idx in range(len(raw_cells) - 1, -1, -1):
                if matched_idx is not None and idx == matched_idx:
                    continue
                parsed_marks = _extract_decimal_from_cell(raw_cells[idx])
                if parsed_marks is not None:
                    break

        if (
            not matched_student
            or parsed_marks is None
            or parsed_marks < Decimal('0')
            or parsed_marks > exam.max_marks
        ):
            skipped_count += 1
            continue

        Mark.objects.update_or_create(
            exam=exam,
            student=matched_student,
            section=None,
            defaults={'marks': parsed_marks},
        )
        saved_count += 1

    return saved_count, skipped_count, None


def _student_exam_total(exam, student_id):
    total_mark = Mark.objects.filter(
        exam=exam, student_id=student_id, section__isnull=True
    ).first()
    if total_mark:
        return Decimal(total_mark.marks)

    section_sum = Mark.objects.filter(
        exam=exam, student_id=student_id, section__isnull=False
    ).aggregate(total=Sum('marks'))['total']
    return Decimal(section_sum) if section_sum is not None else None


# ==================== AUTH ====================

def login_view(request):
    if request.user.is_authenticated:
        role = request.user.role if getattr(request.user, 'role', None) else ('admin' if request.user.is_superuser else None)
        if role:
            return redirect(f'{role}_dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            
            # Check user existence and active status first for better error messages
            try:
                user_obj = User.objects.get(username=username)
                if not user_obj.is_active:
                    if user_obj.status == 'pending':
                        messages.error(request, 'Your profile is pending admin approval.')
                    else:
                        messages.error(request, 'Your profile has been disabled by admin.')
                    return render(request, 'core/login.html', {'form': form})
            except User.DoesNotExist:
                pass

            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                role = user.role if getattr(user, 'role', None) else ('admin' if user.is_superuser else None)
                if role:
                    return redirect(f'{role}_dashboard')
                else:
                    return redirect('/')  # Fallback if no role could be determined
            else:
                messages.error(request, 'Invalid credentials or account does not exist.')
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})

def student_signup_view(request):
    if request.method == 'POST':
        form = StudentSignupForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Signup successful! Your profile is pending administrative approval.')
            return redirect('login')
    else:
        form = StudentSignupForm()
    return render(request, 'core/student_signup.html', {'form': form})


def logout_view(request):
    logout(request)
    response = redirect('login')
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Keeps user logged in
            messages.success(request, 'Your password was successfully updated!')
            # Redirect to their appropriate dashboard
            role = request.user.role if getattr(request.user, 'role', None) else ('admin' if request.user.is_superuser else None)
            return redirect(f'{role}_dashboard' if role else 'login')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'core/change_password.html', {'form': form})




# ==================== STUDENT VIEWS ====================

@login_required
@role_required('student')
def student_dashboard(request):
    current_enrollments = Enrollment.objects.filter(
        student=request.user, status='approved', course__is_active=True
    ).select_related('course')
    completed_enrollments = Enrollment.objects.filter(
        student=request.user, status='approved', course__is_active=False
    ).select_related('course')
    
    return render(request, 'core/student/dashboard.html', {
        'current_enrollments': current_enrollments,
        'completed_enrollments': completed_enrollments,
    })


@login_required
@role_required('student')
def student_add_course(request):
    current_semester = _get_current_semester()
    search_query = request.GET.get('q', '').strip()
    
    # Filter courses by student department if set and keep open catalog
    courses_query = Course.objects.filter(is_active=True)
    if request.user.department:
        courses_query = courses_query.filter(department=request.user.department)

    enrolled_course_ids = Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True)
    available_courses = list(
        courses_query.exclude(id__in=enrolled_course_ids).select_related('professor')
    )
    course_search_suggestions = _course_search_suggestions(available_courses)
    if search_query:
        available_courses = _filter_courses_by_query(available_courses, search_query)

    pending_enrollments = Enrollment.objects.filter(
        student=request.user, status__in=['pending_professor', 'pending_advisor']
    ).select_related('course')

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        course = get_object_or_404(Course, id=course_id, is_active=True)
        # Check if already enrolled or pending
        if not Enrollment.objects.filter(student=request.user, course=course).exists():
            Enrollment.objects.create(
                student=request.user, course=course, status='pending_professor'
            )
            messages.success(request, f'Request sent for {course.code}.')
        else:
            messages.warning(request, 'Already enrolled or request pending.')
        return redirect('student_add_course')

    return render(request, 'core/student/add_course.html', {
        'available_courses': available_courses,
        'search_query': search_query,
        'course_search_suggestions': course_search_suggestions,
        'pending_enrollments': pending_enrollments,
        'current_semester': current_semester,
    })


@login_required
@role_required('student')
def student_course_detail(request, course_id):
    enrollment = get_object_or_404(
        Enrollment, student=request.user, course_id=course_id, status='approved'
    )
    course = enrollment.course
    exams = course.exams.all()
    return render(request, 'core/student/course_detail.html', {
        'course': course,
        'exams': exams,
        'enrollment': enrollment,
    })


@login_required
@role_required('student')
def student_view_scripts(request, course_id, exam_id):
    enrollment = get_object_or_404(
        Enrollment, student=request.user, course_id=course_id, status='approved'
    )
    exam = get_object_or_404(Exam, id=exam_id, course_id=course_id)
    script = AnswerScript.objects.filter(exam=exam, student=request.user).first()
    marks = Mark.objects.filter(exam=exam, student=request.user, section=None)
    queries = Query.objects.filter(
        answer_script__exam=exam, answer_script__student=request.user
    ) if script else []

    now = timezone.now()
    can_raise_query = True
    if exam.query_window_start and exam.query_window_end:
        can_raise_query = exam.query_window_start <= now <= exam.query_window_end

    return render(request, 'core/student/view_scripts.html', {
        'course': enrollment.course,
        'exam': exam,
        'script': script,
        'marks': marks,
        'queries': queries,
        'can_raise_query': can_raise_query,
    })


@login_required
@role_required('student')
def student_raise_query(request, script_id):
    script = get_object_or_404(AnswerScript, id=script_id, student=request.user)
    
    exam = script.exam
    now = timezone.now()
    if exam.query_window_start and exam.query_window_end:
        if not (exam.query_window_start <= now <= exam.query_window_end):
            messages.error(request, 'The query window for this exam is currently closed.')
            return redirect('student_view_scripts', course_id=exam.course_id, exam_id=exam.id)

    if request.method == 'POST':
        form = QueryForm(request.POST)
        if form.is_valid():
            query = form.save(commit=False)
            query.answer_script = script
            query.raised_by = request.user
            query.save()
            messages.success(request, 'Query raised successfully.')
            return redirect('student_view_scripts',
                          course_id=script.exam.course_id, exam_id=script.exam_id)
    else:
        form = QueryForm()
    return render(request, 'core/student/raise_query.html', {
        'form': form, 'script': script
    })


@login_required
@role_required('student')
def student_course_stats(request, course_id):
    enrollment = get_object_or_404(
        Enrollment, student=request.user, course_id=course_id, status='approved'
    )
    course = enrollment.course
    exams = course.exams.all()
    exam_stats = []

    for exam in exams:
        all_marks = list(Mark.objects.filter(
            exam=exam, section__isnull=True
        ).values_list('marks', flat=True))

        student_mark = Mark.objects.filter(
            exam=exam, student=request.user, section__isnull=True
        ).first()

        if all_marks:
            all_marks_float = [float(m) for m in all_marks]
            mean = statistics.mean(all_marks_float)
            median = statistics.median(all_marks_float)
            student_marks_val = float(student_mark.marks) if student_mark else None
            if student_marks_val is not None:
                below = sum(1 for m in all_marks_float if m < student_marks_val)
                percentile = (below / len(all_marks_float)) * 100
            else:
                percentile = None
        else:
            mean = median = percentile = None
            student_marks_val = None

        exam_stats.append({
            'exam': exam,
            'mean': round(mean, 2) if mean is not None else '-',
            'median': round(median, 2) if median is not None else '-',
            'percentile': round(percentile, 1) if percentile is not None else '-',
            'student_marks': student_marks_val if student_marks_val is not None else '-',
        })

    # Overall course stats
    total_marks_all = {}
    for exam in exams:
        marks_qs = Mark.objects.filter(exam=exam, section__isnull=True)
        for m in marks_qs:
            total_marks_all.setdefault(m.student_id, 0)
            total_marks_all[m.student_id] += float(m.marks)

    if total_marks_all:
        all_totals = list(total_marks_all.values())
        overall_mean = round(statistics.mean(all_totals), 2)
        overall_median = round(statistics.median(all_totals), 2)
        student_total = total_marks_all.get(request.user.id)
        if student_total is not None:
            below = sum(1 for t in all_totals if t < student_total)
            overall_percentile = round((below / len(all_totals)) * 100, 1)
        else:
            overall_percentile = '-'
            student_total = '-'
    else:
        overall_mean = overall_median = overall_percentile = student_total = '-'

    return render(request, 'core/student/course_stats.html', {
        'course': course,
        'exam_stats': exam_stats,
        'overall_mean': overall_mean,
        'overall_median': overall_median,
        'overall_percentile': overall_percentile,
        'student_total': student_total,
    })


@login_required
@role_required('student')
def student_past_course(request, course_id):
    enrollment = get_object_or_404(
        Enrollment, student=request.user, course_id=course_id,
        status='approved', course__is_active=False
    )
    course = enrollment.course
    exams = course.exams.all()
    scripts = AnswerScript.objects.filter(
        exam__course=course, student=request.user
    ).select_related('exam')

    return render(request, 'core/student/past_course.html', {
        'course': course,
        'enrollment': enrollment,
        'exams': exams,
        'scripts': scripts,
    })


# ==================== PROFESSOR VIEWS ====================

@login_required
@role_required('professor')
def professor_dashboard(request):
    search_query = request.GET.get('q', '').strip()
    request_search_query = request.GET.get('request_q', '').strip()

    active_courses = list(
        Course.objects.filter(professor=request.user, is_active=True).select_related('professor')
    )
    completed_courses = list(
        Course.objects.filter(professor=request.user, is_active=False).select_related('professor')
    )

    course_search_suggestions = _course_search_suggestions(active_courses + completed_courses)
    if search_query:
        active_courses = _filter_courses_by_query(active_courses, search_query)
        completed_courses = _filter_courses_by_query(completed_courses, search_query)

    # Pending requests as professor
    prof_requests = Enrollment.objects.filter(
        course__professor=request.user, status='pending_professor'
    ).select_related('student', 'course')

    # Pending requests as faculty advisor
    advisor_requests = Enrollment.objects.filter(
        student__faculty_advisor__advisor=request.user, status='pending_advisor'
    ).select_related('student', 'course')

    if request_search_query:
        request_terms = request_search_query
        request_filter = (
            Q(student__username__icontains=request_terms)
            | Q(student__first_name__icontains=request_terms)
            | Q(student__last_name__icontains=request_terms)
            | Q(student__roll_number__icontains=request_terms)
            | Q(course__code__icontains=request_terms)
            | Q(course__name__icontains=request_terms)
        )
        prof_requests = prof_requests.filter(request_filter)
        advisor_requests = advisor_requests.filter(request_filter)

    notifications = request.user.notifications.order_by('-created_at')[:8]

    return render(request, 'core/professor/dashboard.html', {
        'active_courses': active_courses,
        'completed_courses': completed_courses,
        'search_query': search_query,
        'request_search_query': request_search_query,
        'course_search_suggestions': course_search_suggestions,
        'prof_requests': prof_requests,
        'advisor_requests': advisor_requests,
        'notifications': notifications,
    })


@login_required
@role_required('professor')
def professor_course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id, professor=request.user)
    exams = course.exams.all()
    total_weightage = sum((exam.weightage for exam in exams), Decimal('0'))
    tas = TAAssignment.objects.filter(course=course).select_related('ta')
    enrolled_students = Enrollment.objects.filter(
        course=course, status='approved'
    ).select_related('student')

    return render(request, 'core/professor/course_detail.html', {
        'course': course,
        'exams': exams,
        'total_weightage': total_weightage,
        'tas': tas,
        'enrolled_students': enrolled_students,
    })


@login_required
@role_required('professor')
def professor_add_exam(request, course_id):
    course = get_object_or_404(Course, id=course_id, professor=request.user, is_active=True)
    if request.method == 'POST':
        form = ExamForm(request.POST)
        if form.is_valid():
            exam = form.save(commit=False)
            exam.course = course
            exam.save()
            messages.success(request, f'Exam "{exam.name}" added.')
            return redirect('professor_course_detail', course_id=course.id)
    else:
        form = ExamForm()
    return render(request, 'core/professor/add_exam.html', {
        'form': form, 'course': course, 'edit_mode': False
    })


@login_required
@role_required('professor')
def professor_edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, course__professor=request.user)
    course = exam.course

    if request.method == 'POST':
        form = ExamForm(request.POST, instance=exam)
        if form.is_valid():
            form.save()
            messages.success(request, f'Exam "{exam.name}" updated successfully.')
            return redirect('professor_course_detail', course_id=course.id)
    else:
        form = ExamForm(instance=exam)

    return render(request, 'core/professor/add_exam.html', {
        'form': form,
        'course': course,
        'exam': exam,
        'edit_mode': True,
    })


@login_required
@role_required('professor')
def professor_upload_scripts(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, course__professor=request.user)
    enrolled_students = Enrollment.objects.filter(
        course=exam.course, status='approved'
    ).select_related('student')

    if request.method == 'POST':
        import os
        student_id = request.POST.get('student_id')
        single_file = request.FILES.get('file')
        multiple_files = request.FILES.getlist('files')

        if student_id and single_file:
            student = get_object_or_404(User, id=student_id, role='student')
            if not Enrollment.objects.filter(course=exam.course, student=student, status='approved').exists():
                messages.error(request, 'Selected student is not enrolled in this course.')
            elif not _is_allowed_script_file(single_file):
                messages.error(request, 'Unsupported file format for single upload.')
            else:
                AnswerScript.objects.update_or_create(
                    exam=exam, student=student,
                    defaults={'file': single_file, 'uploaded_by': request.user}
                )
                messages.success(request, f'Answer script uploaded for {student.username}.')

        elif multiple_files:
            success_count = 0
            failed_msgs = []
            
            for f in multiple_files:
                original_name = f.name
                roll_no = os.path.splitext(original_name)[0].strip()
                
                if not _is_allowed_script_file(f):
                    failed_msgs.append(f"{original_name} (Unsupported format)")
                    continue
                
                student = User.objects.filter(roll_number__iexact=roll_no, role='student', status='approved').first()
                if not student:
                    failed_msgs.append(f"{original_name} (Roll No not found)")
                    continue
                    
                if not Enrollment.objects.filter(course=exam.course, student=student, status='approved').exists():
                    failed_msgs.append(f"{original_name} (Student not enrolled)")
                    continue
                
                AnswerScript.objects.update_or_create(
                    exam=exam, student=student,
                    defaults={'file': f, 'uploaded_by': request.user}
                )
                success_count += 1
            
            if success_count > 0:
                messages.success(request, f'Successfully bulk uploaded {success_count} script(s).')
            for msg in failed_msgs:
                messages.error(request, f'Failed file: {msg}')
        else:
            messages.error(request, 'Please provide valid inputs to upload files.')
        
        return redirect('professor_upload_scripts', exam_id=exam.id)

    existing_scripts = AnswerScript.objects.filter(exam=exam).select_related('student')
    return render(request, 'core/professor/upload_scripts.html', {
        'exam': exam,
        'enrolled_students': enrolled_students,
        'existing_scripts': existing_scripts,
    })


@login_required
@role_required('professor')
def professor_enter_marks(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, course__professor=request.user)
    enrolled_students = Enrollment.objects.filter(
        course=exam.course, status='approved'
    ).select_related('student')

    if request.method == 'POST':
        saved_count = 0
        skipped_count = 0
        for enrollment in enrolled_students:
            student = enrollment.student
            marks_val = request.POST.get(f'marks_{student.id}')
            if marks_val:
                try:
                    parsed_marks = Decimal(marks_val)
                except (InvalidOperation, TypeError):
                    skipped_count += 1
                    continue
                if parsed_marks < 0 or parsed_marks > exam.max_marks:
                    skipped_count += 1
                    continue
                Mark.objects.update_or_create(
                    exam=exam, student=student, section=None,
                    defaults={'marks': parsed_marks}
                )
                saved_count += 1

        if skipped_count:
            messages.warning(request, f'Marks saved for {saved_count} value(s). Skipped {skipped_count} invalid value(s).')
        else:
            messages.success(request, f'Marks saved for {saved_count} value(s).')
        return redirect('professor_enter_marks', exam_id=exam.id)

    # Get existing marks
    existing_marks = {}
    for mark in Mark.objects.filter(exam=exam, section=None):
        existing_marks[str(mark.student_id)] = mark.marks

    return render(request, 'core/professor/enter_marks.html', {
        'exam': exam,
        'enrolled_students': enrolled_students,
        'existing_marks': existing_marks,
    })


@login_required
@role_required('professor')
def professor_upload_csv_marks(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, course__professor=request.user)
    
    if request.method == 'POST' and 'csv_file' in request.FILES:
        csv_file = request.FILES['csv_file']
        
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('professor_enter_marks', exam_id=exam.id)
            
        count, skipped, error = _import_csv_marks(csv_file, exam)
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request,
                f'Saved marks for {count} student(s). Skipped {skipped} row(s) due to missing student match or invalid/out-of-range marks.'
            )
        
    return redirect('professor_enter_marks', exam_id=exam.id)


@login_required
@role_required('professor')
def professor_approve_enrollment(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    approval_type = request.GET.get('type', 'professor')

    if approval_type == 'professor' and enrollment.course.professor == request.user:
        if enrollment.status == 'pending_professor':
            enrollment.status = 'pending_advisor'
            enrollment.save()
            messages.success(request, f'Approved as professor. Pending advisor approval.')
    elif approval_type == 'advisor':
        try:
            fa = FacultyAdvisor.objects.get(student=enrollment.student)
            if fa.advisor == request.user and enrollment.status == 'pending_advisor':
                enrollment.status = 'approved'
                enrollment.save()
                messages.success(request, f'Approved as advisor. Student enrolled.')
        except FacultyAdvisor.DoesNotExist:
            # If no advisor assigned, auto-approve
            enrollment.status = 'approved'
            enrollment.save()
            messages.success(request, 'No advisor assigned. Auto-approved.')

    return _redirect_professor_request_page(request)


@login_required
@role_required('professor')
def professor_reject_enrollment(request, enrollment_id):
    enrollment = get_object_or_404(Enrollment, id=enrollment_id)
    if request.method == 'POST':
        reason = request.POST.get('reason', '').strip()
        if (enrollment.course.professor == request.user or
                FacultyAdvisor.objects.filter(student=enrollment.student, advisor=request.user).exists()):
            enrollment.status = 'rejected'
            enrollment.rejection_reason = reason
            enrollment.save()
            messages.success(request, 'Enrollment request rejected.')
    return _redirect_professor_request_page(request)


@login_required
@role_required('professor')
def professor_bulk_enrollment_action(request):
    """Handle bulk approve or bulk reject with common reason."""
    if request.method != 'POST':
        return _redirect_professor_request_page(request)

    action = request.POST.get('action')          # 'approve' or 'reject'
    approval_type = request.POST.get('type', 'professor')  # 'professor' or 'advisor'
    enrollment_ids = request.POST.getlist('enrollment_ids')
    reason = request.POST.get('reason', '').strip()

    if not enrollment_ids:
        messages.warning(request, 'No enrollments selected.')
        return _redirect_professor_request_page(request)

    enrollments = Enrollment.objects.filter(id__in=enrollment_ids).select_related('student', 'course')
    count = 0

    for enrollment in enrollments:
        if action == 'approve':
            if approval_type == 'professor' and enrollment.course.professor == request.user:
                if enrollment.status == 'pending_professor':
                    enrollment.status = 'pending_advisor'
                    enrollment.save()
                    count += 1
            elif approval_type == 'advisor':
                try:
                    fa = FacultyAdvisor.objects.get(student=enrollment.student)
                    if fa.advisor == request.user and enrollment.status == 'pending_advisor':
                        enrollment.status = 'approved'
                        enrollment.save()
                        count += 1
                except FacultyAdvisor.DoesNotExist:
                    enrollment.status = 'approved'
                    enrollment.save()
                    count += 1
        elif action == 'reject':
            if not reason:
                messages.error(request, 'A rejection reason is required for bulk reject.')
                return _redirect_professor_request_page(request)
            can_reject = (
                (approval_type == 'professor' and enrollment.course.professor == request.user) or
                (approval_type == 'advisor' and FacultyAdvisor.objects.filter(
                    student=enrollment.student, advisor=request.user).exists())
            )
            if can_reject:
                enrollment.status = 'rejected'
                enrollment.rejection_reason = reason
                enrollment.save()
                count += 1

    action_word = 'approved' if action == 'approve' else 'rejected'
    messages.success(request, f'{count} enrollment(s) {action_word} successfully.')
    return _redirect_professor_request_page(request)


@login_required
@role_required('professor')
def professor_manage_tas(request, course_id):

    course = get_object_or_404(Course, id=course_id, professor=request.user, is_active=True)
    ta_assignments = TAAssignment.objects.filter(course=course).select_related('ta')

    if request.method == 'POST':
        action = request.POST.get('action', 'add')

        if action == 'update_access':
            assignment = get_object_or_404(
                TAAssignment,
                id=request.POST.get('assignment_id'),
                course=course,
            )
            assignment.can_upload_scripts = 'can_upload_scripts' in request.POST
            assignment.can_resolve_queries = 'can_resolve_queries' in request.POST
            assignment.can_update_marks = 'can_update_marks' in request.POST
            assignment.save(update_fields=['can_upload_scripts', 'can_resolve_queries', 'can_update_marks'])

            Notification.objects.create(
                user=assignment.ta,
                message=(
                    f"Professor {request.user.username} updated your TA access for {course.code}. "
                    f"{_permission_summary(assignment)}"
                )
            )
            messages.success(request, f'Updated access for TA {assignment.ta.username}.')
            return redirect('professor_manage_tas', course_id=course.id)

        form = TAAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            if TAAssignment.objects.filter(ta=assignment.ta, course=course).exists():
                messages.warning(request, 'TA already assigned to this course. Use update access below.')
            else:
                assignment.save()
                Notification.objects.create(
                    user=assignment.ta,
                    message=(
                        f"Professor {request.user.username} assigned you as TA for {course.code}. "
                        f"{_permission_summary(assignment)}"
                    )
                )
                messages.success(request, f'TA {assignment.ta.username} assigned.')
            return redirect('professor_manage_tas', course_id=course.id)
    else:
        form = TAAssignmentForm()

    return render(request, 'core/professor/manage_tas.html', {
        'course': course,
        'ta_assignments': ta_assignments,
        'form': form,
    })

@login_required
@role_required('professor')
def professor_remove_ta(request, course_id, assignment_id):
    course = get_object_or_404(Course, id=course_id, professor=request.user, is_active=True)
    assignment = get_object_or_404(TAAssignment, id=assignment_id, course=course)

    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided.')
        # Send Notification to the TA
        Notification.objects.create(
            user=assignment.ta,
            message=f"You have been removed as TA from {course.code}. Reason: {reason}"
        )
        assignment.delete()
        messages.success(request, f'TA {assignment.ta.username} removed successfully.')
    return redirect('professor_manage_tas', course_id=course.id)
@login_required
@role_required('professor')
def professor_completed_course(request, course_id):
    course = get_object_or_404(
        Course, id=course_id, professor=request.user, is_active=False
    )
    enrollments = Enrollment.objects.filter(
        course=course, status='approved'
    ).select_related('student')
    exams = course.exams.all()
    scripts = AnswerScript.objects.filter(exam__course=course).select_related('exam', 'student')

    return render(request, 'core/professor/completed_course.html', {
        'course': course,
        'enrollments': enrollments,
        'exams': exams,
        'scripts': scripts,
    })


@login_required
@role_required('professor')
def professor_view_queries(request, course_id):
    course = get_object_or_404(Course, id=course_id, professor=request.user)
    queries = Query.objects.filter(
        answer_script__exam__course=course
    ).select_related('answer_script__exam', 'answer_script__student', 'raised_by', 'resolved_by')

    return render(request, 'core/professor/view_queries.html', {
        'course': course,
        'queries': queries,
    })


@login_required
@role_required('professor')
def professor_respond_query(request, query_id):
    query = get_object_or_404(Query, id=query_id, answer_script__exam__course__professor=request.user)
    if request.method == 'POST':
        form = QueryResponseForm(request.POST)
        if form.is_valid():
            query.response = form.cleaned_data['response']
            query.resolved_by = request.user
            query.is_resolved = True
            query.save()
            messages.success(request, 'Query resolved.')
            return redirect('professor_view_queries', course_id=query.answer_script.exam.course_id)
    else:
        form = QueryResponseForm()
    return render(request, 'core/professor/respond_query.html', {
        'query': query, 'form': form
    })


@login_required
@role_required('professor')
def professor_assign_grades(request, course_id):
    course = get_object_or_404(Course, id=course_id, professor=request.user, is_active=True)
    enrollments = list(Enrollment.objects.filter(course=course, status='approved').select_related('student'))
    exams = list(course.exams.all())
    
    if request.method == 'POST':
        for enrollment in enrollments:
            grade_val = (request.POST.get(f'grade_{enrollment.id}') or '').strip()
            enrollment.grade = grade_val or None
            enrollment.save(update_fields=['grade'])
        messages.success(request, 'Grades saved successfully.')
        return redirect('professor_assign_grades', course_id=course.id)

    grade_rows = []
    for enrollment in enrollments:
        weighted_total = Decimal('0')
        for exam in exams:
            total_mark = _student_exam_total(exam, enrollment.student_id)
            if total_mark is None:
                continue
            if exam.max_marks > 0:
                weighted_total += (total_mark / exam.max_marks) * exam.weightage

        grade_rows.append({
            'enrollment': enrollment,
            'weighted_total': round(weighted_total, 2),
        })

    grade_rows.sort(key=lambda row: row['weighted_total'], reverse=True)
        
    return render(request, 'core/professor/assign_grades.html', {
        'course': course,
        'grade_rows': grade_rows,
        'total_weightage': round(sum((exam.weightage for exam in exams), Decimal('0')), 2),
    })


# ==================== ADMIN VIEWS ====================

@login_required
@role_required('admin')
def admin_dashboard(request):
    return render(request, 'core/admin/dashboard.html')


@login_required
@role_required('admin')
def admin_create_course(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.created_by = request.user
            course.save()
            messages.success(request, f'Course {course.code} created.')
            return redirect('admin_dashboard')
    else:
        form = CourseForm()
    return render(request, 'core/admin/create_course.html', {'form': form})


@login_required
@role_required('admin')
def admin_end_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, is_active=True)
    
    ungraded = Enrollment.objects.filter(course=course, status='approved', grade__isnull=True)
    if ungraded.exists():
        messages.error(request, 'Cannot end course: Not all approved students have been assigned a grade.')
        return redirect('admin_manage_courses')
        
    course.is_active = False
    course.save()
    messages.success(request, f'Course {course.code} ended.')
    return redirect('admin_manage_courses')





@login_required
@role_required('admin')
def admin_manage_courses(request):
    courses = Course.objects.filter(is_active=True).select_related('professor')
    return render(request, 'core/admin/manage_courses.html', {'courses': courses})

@login_required
@role_required('admin')
def admin_ended_courses(request):
    courses = Course.objects.filter(is_active=False).select_related('professor')
    return render(request, 'core/admin/ended_courses.html', {'courses': courses})


# ==================== TA VIEWS ====================

@login_required
@role_required('ta')
def ta_dashboard(request):
    assignments = list(TAAssignment.objects.filter(
        ta=request.user, course__is_active=True
    ).select_related('course'))

    for assignment in assignments:
        assignment.first_exam = assignment.course.exams.order_by('id').first()

    return render(request, 'core/ta/dashboard.html', {
        'assignments': assignments,
    })
@login_required
@role_required('admin')
def admin_add_faculty(request):
    if request.method == 'POST':
        form = AdminAddFacultyForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Faculty {user.username} created successfully.')
            return redirect('admin_manage_faculty')
    else:
        form = AdminAddFacultyForm()
    return render(request, 'core/admin/add_user.html', {'form': form, 'title': 'Add Faculty'})


@login_required
@role_required('admin')
def admin_add_student(request):
    if request.method == 'POST':
        form = AdminAddStudentForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Student {user.username} created successfully.')
            return redirect('admin_manage_students')
    else:
        form = AdminAddStudentForm()
    return render(request, 'core/admin/add_user.html', {'form': form, 'title': 'Add Student'})


@login_required
@role_required('admin')
def admin_add_ta(request):
    if request.method == 'POST':
        form = AdminAddTAForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'TA {user.username} created successfully.')
            return redirect('admin_manage_tas')
    else:
        form = AdminAddTAForm()
    return render(request, 'core/admin/add_user.html', {'form': form, 'title': 'Add TA'})


@login_required
@role_required('admin')
def admin_force_enroll(request):
    if request.method == 'POST':
        form = AdminForceEnrollForm(request.POST)
        if form.is_valid():
            roll_no = form.cleaned_data['roll_number']
            course = form.cleaned_data['course']
            student = User.objects.filter(role='student', roll_number=roll_no).first()
            if student:
                Enrollment.objects.update_or_create(student=student, course=course, defaults={'status': 'approved'})
                messages.success(request, f'Student {student.username} manually enrolled into {course.code}.')
            else:
                messages.error(request, 'Student not found.')
            return redirect('admin_dashboard')
    else:
        form = AdminForceEnrollForm()
    return render(request, 'core/admin/force_enroll.html', {'form': form})


@login_required
@role_required('admin')
def admin_view_course_grades(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    enrollments = Enrollment.objects.filter(course=course, status='approved').select_related('student')
    ungraded_count = enrollments.filter(Q(grade__isnull=True) | Q(grade='')).count()
        
    return render(request, 'core/admin/view_grades.html', {
        'course': course,
        'enrollments': enrollments,
        'ungraded_count': ungraded_count,
    })


@login_required
@role_required('admin')
def admin_notify_grade_pending(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        pending_count = Enrollment.objects.filter(
            course=course,
            status='approved'
        ).filter(Q(grade__isnull=True) | Q(grade='')).count()

        if pending_count:
            Notification.objects.create(
                user=course.professor,
                message=(
                    f"Admin reminder: {pending_count} student(s) in {course.code} still need grades. "
                    "Please complete grade assignment."
                )
            )
            messages.success(request, 'Reminder sent to the course professor.')
        else:
            messages.info(request, 'All grades are already assigned.')

    return redirect('admin_view_course_grades', course_id=course.id)

@login_required
@role_required('ta')
def ta_course_detail(request, assignment_id):
    assignment = get_object_or_404(TAAssignment, id=assignment_id, ta=request.user)
    course = assignment.course
    exams = course.exams.all()

    return render(request, 'core/ta/course_detail.html', {
        'assignment': assignment,
        'course': course,
        'exams': exams,
    })


@login_required
@role_required('ta')
def ta_upload_scripts(request, assignment_id, exam_id):
    assignment = get_object_or_404(TAAssignment, id=assignment_id, ta=request.user)
    if not assignment.can_upload_scripts:
        messages.error(request, 'Upload scripts permission is not granted for this course.')
        return redirect('ta_course_detail', assignment_id=assignment.id)

    exam = get_object_or_404(Exam, id=exam_id, course=assignment.course)
    enrolled_students = Enrollment.objects.filter(
        course=assignment.course, status='approved'
    ).select_related('student')

    if request.method == 'POST':
        import os
        student_id = request.POST.get('student_id')
        single_file = request.FILES.get('file')
        multiple_files = request.FILES.getlist('files')

        if student_id and single_file:
            student = get_object_or_404(User, id=student_id, role='student')
            if not Enrollment.objects.filter(course=assignment.course, student=student, status='approved').exists():
                messages.error(request, 'Selected student is not enrolled in this course.')
            elif not _is_allowed_script_file(single_file):
                messages.error(request, 'Unsupported file format for single upload.')
            else:
                AnswerScript.objects.update_or_create(
                    exam=exam, student=student,
                    defaults={'file': single_file, 'uploaded_by': request.user}
                )
                messages.success(request, f'Answer script uploaded for {student.username}.')

        elif multiple_files:
            success_count = 0
            failed_msgs = []
            
            for f in multiple_files:
                original_name = f.name
                roll_no = os.path.splitext(original_name)[0].strip()
                
                if not _is_allowed_script_file(f):
                    failed_msgs.append(f"{original_name} (Unsupported format)")
                    continue
                
                student = User.objects.filter(roll_number__iexact=roll_no, role='student', status='approved').first()
                if not student:
                    failed_msgs.append(f"{original_name} (Roll No not found)")
                    continue
                    
                if not Enrollment.objects.filter(course=assignment.course, student=student, status='approved').exists():
                    failed_msgs.append(f"{original_name} (Student not enrolled)")
                    continue
                
                AnswerScript.objects.update_or_create(
                    exam=exam, student=student,
                    defaults={'file': f, 'uploaded_by': request.user}
                )
                success_count += 1
            
            if success_count > 0:
                messages.success(request, f'Successfully bulk uploaded {success_count} script(s).')
            for msg in failed_msgs:
                messages.error(request, f'Failed file: {msg}')
        else:
            messages.error(request, 'Please provide valid inputs to upload files.')
        
        return redirect('ta_upload_scripts', assignment_id=assignment.id, exam_id=exam.id)

    existing_scripts = AnswerScript.objects.filter(exam=exam).select_related('student')
    return render(request, 'core/ta/upload_scripts.html', {
        'assignment': assignment,
        'exam': exam,
        'enrolled_students': enrolled_students,
        'existing_scripts': existing_scripts,
    })


@login_required
@role_required('ta')
def ta_view_queries(request, assignment_id):
    assignment = get_object_or_404(TAAssignment, id=assignment_id, ta=request.user)
    if not assignment.can_resolve_queries:
        messages.error(request, 'Resolve queries permission is not granted for this course.')
        return redirect('ta_course_detail', assignment_id=assignment.id)

    queries = Query.objects.filter(
        answer_script__exam__course=assignment.course
    ).select_related('answer_script__exam', 'answer_script__student', 'raised_by')

    return render(request, 'core/ta/view_queries.html', {
        'assignment': assignment,
        'queries': queries,
    })


@login_required
@role_required('ta')
def ta_respond_query(request, query_id):
    query = get_object_or_404(Query, id=query_id)
    assignment = get_object_or_404(TAAssignment, ta=request.user, course=query.answer_script.exam.course)
    if not assignment.can_resolve_queries:
        messages.error(request, 'Resolve queries permission is not granted for this course.')
        return redirect('ta_course_detail', assignment_id=assignment.id)

    if request.method == 'POST':
        form = QueryResponseForm(request.POST)
        if form.is_valid():
            query.response = form.cleaned_data['response']
            query.resolved_by = request.user
            query.is_resolved = True
            query.save()
            messages.success(request, 'Query resolved.')
            return redirect('ta_view_queries', assignment_id=assignment.id)
    else:
        form = QueryResponseForm()
    return render(request, 'core/ta/respond_query.html', {
        'query': query, 'form': form, 'assignment': assignment
    })


@login_required
@role_required('ta')
def ta_update_marks(request, assignment_id, exam_id):
    assignment = get_object_or_404(TAAssignment, id=assignment_id, ta=request.user)
    if not assignment.can_update_marks:
        messages.error(request, 'Update marks permission is not granted for this course.')
        return redirect('ta_course_detail', assignment_id=assignment.id)

    exam = get_object_or_404(Exam, id=exam_id, course=assignment.course)
    enrolled_students = Enrollment.objects.filter(
        course=assignment.course, status='approved'
    ).select_related('student')

    if request.method == 'POST':
        saved_count = 0
        skipped_count = 0
        for enrollment in enrolled_students:
            student = enrollment.student
            marks_val = request.POST.get(f'marks_{student.id}')
            comment = request.POST.get(f'comment_{student.id}', '')
            if marks_val:
                try:
                    parsed_marks = Decimal(marks_val)
                except (InvalidOperation, TypeError):
                    skipped_count += 1
                    continue
                if parsed_marks < 0 or parsed_marks > exam.max_marks:
                    skipped_count += 1
                    continue

                old_mark = Mark.objects.filter(
                    exam=exam, student=student, section=None
                ).first()
                old_val = old_mark.marks if old_mark else None
                Mark.objects.update_or_create(
                    exam=exam, student=student, section=None,
                    defaults={
                        'marks': parsed_marks,
                        'old_marks': old_val,
                        'comment': comment or None,
                    }
                )
                saved_count += 1

        if skipped_count:
            messages.warning(request, f'Marks updated for {saved_count} value(s). Skipped {skipped_count} invalid value(s).')
        else:
            messages.success(request, f'Marks updated for {saved_count} value(s).')
        return redirect('ta_update_marks', assignment_id=assignment.id, exam_id=exam.id)

    existing_marks = {}
    for mark in Mark.objects.filter(exam=exam, section=None):
        existing_marks[str(mark.student_id)] = {
            'marks': mark.marks,
            'old_marks': mark.old_marks,
            'comment': mark.comment,
        }

    history_rows = Mark.objects.filter(exam=exam, section=None).select_related('student').order_by('student__username')

    return render(request, 'core/ta/update_marks.html', {
        'assignment': assignment,
        'exam': exam,
        'enrolled_students': enrolled_students,
        'existing_marks': existing_marks,
        'history_rows': history_rows,
    })


@login_required
@role_required('ta')
def ta_upload_csv_marks(request, assignment_id, exam_id):
    assignment = get_object_or_404(TAAssignment, id=assignment_id, ta=request.user)
    if not assignment.can_update_marks:
        messages.error(request, 'Update marks permission is not granted for this course.')
        return redirect('ta_course_detail', assignment_id=assignment.id)

    exam = get_object_or_404(Exam, id=exam_id, course=assignment.course)

    if request.method == 'POST' and 'csv_file' in request.FILES:
        csv_file = request.FILES['csv_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('ta_update_marks', assignment_id=assignment.id, exam_id=exam.id)

        count, skipped, error = _import_csv_marks(csv_file, exam)
        if error:
            messages.error(request, error)
        else:
            messages.success(
                request,
                f'Saved marks for {count} student(s). Skipped {skipped} row(s) due to missing student match or invalid/out-of-range marks.'
            )

    return redirect('ta_update_marks', assignment_id=assignment.id, exam_id=exam.id)


# ==================== HELPERS ====================

def _get_current_semester():
    """Return current semester string based on current date."""
    from datetime import datetime
    now = datetime.now()
    if now.month <= 5:
        return f"Spring {now.year}"
    elif now.month <= 8:
        return f"Summer {now.year}"
    else:
        return f"Fall {now.year}"
@login_required
def mark_notification_read(request, notif_id):
    from .models import Notification
    notification = get_object_or_404(Notification, id=notif_id, user=request.user)
    notification.is_read = True
    notification.save()
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'login'
    return redirect(next_url)

@login_required
def mark_all_notifications_read(request):
    from .models import Notification
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or 'login'
    return redirect(next_url)

@login_required
@role_required('admin')
def admin_manage_students(request):
    students = User.objects.filter(role='student').order_by('-date_joined')
    pending = students.filter(status='pending')
    active = students.filter(status='approved')
    disabled = students.filter(status='disabled')
    return render(request, 'core/admin/manage_students.html', {
        'pending': pending, 'active': active, 'disabled': disabled
    })

@login_required
@role_required('admin')
def admin_manage_faculty(request):
    faculty = User.objects.filter(role='professor').order_by('department', 'username')
    active = faculty.filter(status='approved')
    disabled = faculty.filter(status='disabled')
    return render(request, 'core/admin/manage_faculty.html', {'active': active, 'disabled': disabled})

@login_required
@role_required('admin')
def admin_manage_tas(request):
    tas = User.objects.filter(role='ta').order_by('department', 'username')
    active = tas.filter(status='approved')
    disabled = tas.filter(status='disabled')
    return render(request, 'core/admin/manage_tas.html', {'active': active, 'disabled': disabled})

@login_required
@role_required('admin')
def admin_user_action(request, user_id, action):
    user_target = get_object_or_404(User, id=user_id)
    ret_role = user_target.role
    uname = user_target.username
    if request.method == 'POST':
        if action == 'approve':
            user_target.is_active = True
            user_target.status = 'approved'
            user_target.save()
            messages.success(request, f'User {uname} approved.')
        elif action == 'reject':
            user_target.delete()
            messages.success(request, f'User {uname} rejected and deleted.')
        elif action == 'disable':
            user_target.is_active = False
            user_target.status = 'disabled'
            user_target.save()
            messages.success(request, f'User {uname} disabled.')
        elif action == 'enable':
            user_target.is_active = True
            user_target.status = 'approved'
            user_target.save()
            messages.success(request, f'User {uname} enabled.')

    if ret_role == 'student':
        return redirect('admin_manage_students')
    elif ret_role == 'professor':
        return redirect('admin_manage_faculty')
    elif ret_role == 'ta':
        return redirect('admin_manage_tas')
    return redirect('admin_dashboard')
@login_required
def serve_answer_script(request, script_id):
    script = get_object_or_404(AnswerScript, id=script_id)
    course = script.exam.course

    is_authorized = False
    if request.user.role == 'student':
        if request.user == script.student and Enrollment.objects.filter(course=course, student=request.user, status='approved').exists():
            is_authorized = True
    elif request.user.role == 'professor':
        if request.user == course.professor:
            is_authorized = True
    elif request.user.role == 'ta':
        if TAAssignment.objects.filter(course=course, ta=request.user).exists():
            is_authorized = True
    elif request.user.role == 'admin':
        is_authorized = True

    if not is_authorized:
        return HttpResponseForbidden("You do not have permission to view this script.")

    try:
        return FileResponse(script.file.open('rb'), content_type='application/pdf')
    except FileNotFoundError:
        return HttpResponseForbidden("File not found.")
