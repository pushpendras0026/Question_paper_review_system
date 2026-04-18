from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Avg, Count
from django.utils import timezone
from decimal import Decimal
import statistics
import csv
import io

from .models import (
    User, Course, Enrollment, FacultyAdvisor, Exam, ExamSection,
    AnswerScript, Mark, Query, TAAssignment, Notification
)
from .forms import (
    LoginForm, CourseForm, ExamForm, ExamSectionForm, AnswerScriptUploadForm,
    MarkForm, QueryForm, QueryResponseForm, TAAssignmentForm,
    FacultyAdvisorForm, AdminAddFacultyForm, AdminAddStudentForm,
    AdminForceEnrollForm
)


def role_required(role):
    """Decorator to restrict views to a specific role."""
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.role != role and not (request.user.is_superuser and role == 'admin'):
                messages.error(request, 'Access denied.')
                return redirect('login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


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
            role = form.cleaned_data['role']
            user = authenticate(request, username=username, password=password)
            if user is not None and (user.role == role or (user.is_superuser and role == 'admin')):
                login(request, user)
                return redirect(f'{role}_dashboard')
            else:
                messages.error(request, 'Invalid credentials or role mismatch.')
    else:
        form = LoginForm()
    return render(request, 'core/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')




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
    
    # Filter courses by student department if set and keep open catalog
    courses_query = Course.objects.filter(is_active=True)
    if request.user.department:
        courses_query = courses_query.filter(department=request.user.department)

    enrolled_course_ids = Enrollment.objects.filter(student=request.user).values_list('course_id', flat=True)
    available_courses = courses_query.exclude(id__in=enrolled_course_ids)
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
    marks = Mark.objects.filter(exam=exam, student=request.user)
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
    active_courses = Course.objects.filter(professor=request.user, is_active=True)
    completed_courses = Course.objects.filter(professor=request.user, is_active=False)

    # Pending requests as professor
    prof_requests = Enrollment.objects.filter(
        course__professor=request.user, status='pending_professor'
    ).select_related('student', 'course')

    # Pending requests as faculty advisor
    advisor_requests = Enrollment.objects.filter(
        student__faculty_advisor__advisor=request.user, status='pending_advisor'
    ).select_related('student', 'course')

    return render(request, 'core/professor/dashboard.html', {
        'active_courses': active_courses,
        'completed_courses': completed_courses,
        'prof_requests': prof_requests,
        'advisor_requests': advisor_requests,
    })


@login_required
@role_required('professor')
def professor_course_detail(request, course_id):
    course = get_object_or_404(Course, id=course_id, professor=request.user)
    exams = course.exams.all()
    tas = TAAssignment.objects.filter(course=course).select_related('ta')
    enrolled_students = Enrollment.objects.filter(
        course=course, status='approved'
    ).select_related('student')

    return render(request, 'core/professor/course_detail.html', {
        'course': course,
        'exams': exams,
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
        'form': form, 'course': course
    })


@login_required
@role_required('professor')
def professor_add_section(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, course__professor=request.user)
    if request.method == 'POST':
        form = ExamSectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.exam = exam
            section.save()
            messages.success(request, f'Section "{section.name}" added.')
            return redirect('professor_course_detail', course_id=exam.course_id)
    else:
        form = ExamSectionForm()
    return render(request, 'core/professor/add_section.html', {
        'form': form, 'exam': exam
    })


@login_required
@role_required('professor')
def professor_upload_scripts(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id, course__professor=request.user)
    enrolled_students = Enrollment.objects.filter(
        course=exam.course, status='approved'
    ).select_related('student')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        student = get_object_or_404(User, id=student_id, role='student')
        if 'file' in request.FILES:
            script, created = AnswerScript.objects.update_or_create(
                exam=exam, student=student,
                defaults={'file': request.FILES['file'], 'uploaded_by': request.user}
            )
            messages.success(request, f'Answer script uploaded for {student.username}.')
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
    sections = exam.sections.all()

    if request.method == 'POST':
        for enrollment in enrolled_students:
            student = enrollment.student
            if sections.exists():
                for section in sections:
                    marks_val = request.POST.get(f'marks_{student.id}_{section.id}')
                    if marks_val:
                        Mark.objects.update_or_create(
                            exam=exam, student=student, section=section,
                            defaults={'marks': Decimal(marks_val)}
                        )
            # Total marks (no section)
            total_marks = request.POST.get(f'marks_{student.id}_total')
            if total_marks:
                Mark.objects.update_or_create(
                    exam=exam, student=student, section=None,
                    defaults={'marks': Decimal(total_marks)}
                )
        messages.success(request, 'Marks saved.')
        return redirect('professor_course_detail', course_id=exam.course_id)

    # Get existing marks
    existing_marks = {}
    for mark in Mark.objects.filter(exam=exam):
        key = f'{mark.student_id}_{mark.section_id or "total"}'
        existing_marks[key] = mark.marks

    return render(request, 'core/professor/enter_marks.html', {
        'exam': exam,
        'enrolled_students': enrolled_students,
        'sections': sections,
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
            
        data_set = csv_file.read().decode('UTF-8')
        io_string = io.StringIO(data_set)
        
        next(io_string)  # skip header
        count = 0
        for row in csv.reader(io_string, delimiter=',', quotechar='"'):
            if len(row) >= 2:
                roll_no = row[0].strip()
                marks_val = row[1].strip()
                
                try:
                    student = User.objects.get(role='student', roll_number=roll_no)
                    
                    if Enrollment.objects.filter(student=student, course=exam.course, status='approved').exists():
                        Mark.objects.update_or_create(
                            exam=exam, student=student, section=None,
                            defaults={'marks': Decimal(marks_val)}
                        )
                        count += 1
                except (User.DoesNotExist, ValueError, TypeError):
                    continue
                    
        messages.success(request, f'Successfully parsed and saved {count} student marks from CSV.')
        
    return redirect('professor_enter_marks', exam_id=exam.id)


@login_required
@role_required('professor')
def professor_approve_requests(request):
    prof_requests_qs = Enrollment.objects.filter(
        course__professor=request.user, status='pending_professor'
    ).select_related('student', 'course').order_by('course__department', 'course__semester', 'course__code')

    advisor_requests_qs = Enrollment.objects.filter(
        student__faculty_advisor__advisor=request.user, status='pending_advisor'
    ).select_related('student', 'course').order_by('course__department', 'course__semester', 'course__code')

    # Group prof_requests by department → semester → course
    prof_groups = {}
    for e in prof_requests_qs:
        dept = e.course.department or 'Unknown'
        sem = e.course.semester
        ckey = e.course.code
        prof_groups.setdefault(dept, {}).setdefault(sem, {}).setdefault(ckey, {'course': e.course, 'enrollments': []})
        prof_groups[dept][sem][ckey]['enrollments'].append(e)

    # Group advisor_requests by department → semester → course
    advisor_groups = {}
    for e in advisor_requests_qs:
        dept = e.course.department or 'Unknown'
        sem = e.course.semester
        ckey = e.course.code
        advisor_groups.setdefault(dept, {}).setdefault(sem, {}).setdefault(ckey, {'course': e.course, 'enrollments': []})
        advisor_groups[dept][sem][ckey]['enrollments'].append(e)

    return render(request, 'core/professor/approve_requests.html', {
        'prof_groups': prof_groups,
        'advisor_groups': advisor_groups,
        'total_prof': prof_requests_qs.count(),
        'total_advisor': advisor_requests_qs.count(),
    })


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

    return redirect('professor_approve_requests')


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
    return redirect('professor_approve_requests')


@login_required
@role_required('professor')
def professor_bulk_enrollment_action(request):
    """Handle bulk approve or bulk reject with common reason."""
    if request.method != 'POST':
        return redirect('professor_approve_requests')

    action = request.POST.get('action')          # 'approve' or 'reject'
    approval_type = request.POST.get('type', 'professor')  # 'professor' or 'advisor'
    enrollment_ids = request.POST.getlist('enrollment_ids')
    reason = request.POST.get('reason', '').strip()

    if not enrollment_ids:
        messages.warning(request, 'No enrollments selected.')
        return redirect('professor_approve_requests')

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
                return redirect('professor_approve_requests')
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
    return redirect('professor_approve_requests')


@login_required
@role_required('professor')
def professor_manage_tas(request, course_id):

    course = get_object_or_404(Course, id=course_id, professor=request.user, is_active=True)
    ta_assignments = TAAssignment.objects.filter(course=course).select_related('ta')

    if request.method == 'POST':
        form = TAAssignmentForm(request.POST)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.course = course
            # Check if TA already assigned
            if TAAssignment.objects.filter(ta=assignment.ta, course=course).exists():
                messages.warning(request, 'TA already assigned to this course.')
            else:
                assignment.save()
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
    course.is_active = False
    course.save()
    messages.success(request, f'Course {course.code} ended.')
    return redirect('admin_dashboard')





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
    assignments = TAAssignment.objects.filter(
        ta=request.user, course__is_active=True
    ).select_related('course')
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
            return redirect('admin_dashboard')
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
            return redirect('admin_dashboard')
    else:
        form = AdminAddStudentForm()
    return render(request, 'core/admin/add_user.html', {'form': form, 'title': 'Add Student'})


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
        
    return render(request, 'core/admin/view_grades.html', {
        'course': course,
        'enrollments': enrollments
    })

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
    assignment = get_object_or_404(
        TAAssignment, id=assignment_id, ta=request.user, can_upload_scripts=True
    )
    exam = get_object_or_404(Exam, id=exam_id, course=assignment.course)
    enrolled_students = Enrollment.objects.filter(
        course=assignment.course, status='approved'
    ).select_related('student')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        student = get_object_or_404(User, id=student_id, role='student')
        if 'file' in request.FILES:
            script, created = AnswerScript.objects.update_or_create(
                exam=exam, student=student,
                defaults={'file': request.FILES['file'], 'uploaded_by': request.user}
            )
            messages.success(request, f'Answer script uploaded for {student.username}.')
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
    assignment = get_object_or_404(
        TAAssignment, id=assignment_id, ta=request.user, can_resolve_queries=True
    )
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
    assignment = get_object_or_404(
        TAAssignment, ta=request.user, course=query.answer_script.exam.course,
        can_resolve_queries=True
    )
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
    assignment = get_object_or_404(
        TAAssignment, id=assignment_id, ta=request.user, can_update_marks=True
    )
    exam = get_object_or_404(Exam, id=exam_id, course=assignment.course)
    enrolled_students = Enrollment.objects.filter(
        course=assignment.course, status='approved'
    ).select_related('student')
    sections = exam.sections.all()

    if request.method == 'POST':
        for enrollment in enrolled_students:
            student = enrollment.student
            if sections.exists():
                for section in sections:
                    marks_val = request.POST.get(f'marks_{student.id}_{section.id}')
                    comment = request.POST.get(f'comment_{student.id}_{section.id}', '')
                    if marks_val:
                        old_mark = Mark.objects.filter(
                            exam=exam, student=student, section=section
                        ).first()
                        old_val = old_mark.marks if old_mark else None
                        Mark.objects.update_or_create(
                            exam=exam, student=student, section=section,
                            defaults={
                                'marks': Decimal(marks_val),
                                'old_marks': old_val,
                                'comment': comment or None,
                            }
                        )
            total_marks = request.POST.get(f'marks_{student.id}_total')
            comment = request.POST.get(f'comment_{student.id}_total', '')
            if total_marks:
                old_mark = Mark.objects.filter(
                    exam=exam, student=student, section=None
                ).first()
                old_val = old_mark.marks if old_mark else None
                Mark.objects.update_or_create(
                    exam=exam, student=student, section=None,
                    defaults={
                        'marks': Decimal(total_marks),
                        'old_marks': old_val,
                        'comment': comment or None,
                    }
                )
        messages.success(request, 'Marks updated.')
        return redirect('ta_course_detail', assignment_id=assignment.id)

    existing_marks = {}
    for mark in Mark.objects.filter(exam=exam):
        key = f'{mark.student_id}_{mark.section_id or "total"}'
        existing_marks[key] = {
            'marks': mark.marks,
            'old_marks': mark.old_marks,
            'comment': mark.comment,
        }

    return render(request, 'core/ta/update_marks.html', {
        'assignment': assignment,
        'exam': exam,
        'enrolled_students': enrolled_students,
        'sections': sections,
        'existing_marks': existing_marks,
    })


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
