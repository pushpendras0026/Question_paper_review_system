from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('professor', 'Professor'),
        ('admin', 'Admin'),
        ('ta', 'TA'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    roll_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    faculty_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    department = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        role_display = self.get_role_display() if getattr(self, 'role', None) else (
            "Admin" if self.is_superuser else "Unknown Role"
        )
        return f"{self.roll_number + ' - ' if self.roll_number else ''}{self.username} ({role_display})"


class Course(models.Model):
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=200)
    department = models.CharField(max_length=100, null=True, blank=True)
    semester = models.CharField(max_length=50)
    is_active = models.BooleanField(default=True)
    professor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='courses_teaching',
        limit_choices_to={'role': 'professor'}
    )
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='courses_created'
    )

    class Meta:
        unique_together = ('code', 'semester')

    def __str__(self):
        return f"{self.code} - {self.name} ({self.semester})"


class FacultyAdvisor(models.Model):
    student = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='faculty_advisor',
        limit_choices_to={'role': 'student'}
    )
    advisor = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='advisees',
        limit_choices_to={'role': 'professor'}
    )

    def __str__(self):
        return f"{self.student.username} -> {self.advisor.username}"


class Enrollment(models.Model):
    STATUS_CHOICES = [
        ('pending_professor', 'Pending Professor Approval'),
        ('pending_advisor', 'Pending Advisor Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_professor')
    rejection_reason = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('student', 'course')

    def __str__(self):
        return f"{self.student.username} in {self.course.code} ({self.status})"


class Exam(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='exams')
    name = models.CharField(max_length=100)
    query_window_start = models.DateTimeField(null=True, blank=True)
    query_window_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.course.code} - {self.name}"


class ExamSection(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='sections')
    name = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.exam.name} - {self.name}"


class AnswerScript(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='answer_scripts')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='answer_scripts')
    file = models.FileField(upload_to='answer_scripts/')
    uploaded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name='uploaded_scripts'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('exam', 'student')

    def __str__(self):
        return f"{self.exam} - {self.student.username}"


class Mark(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='marks')
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name='marks')
    section = models.ForeignKey(
        ExamSection, on_delete=models.CASCADE, null=True, blank=True, related_name='marks'
    )
    marks = models.DecimalField(max_digits=6, decimal_places=2)
    old_marks = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    comment = models.TextField(null=True, blank=True, help_text="Comment by TA when updating marks")

    class Meta:
        unique_together = ('exam', 'student', 'section')

    def __str__(self):
        section_str = f" ({self.section.name})" if self.section else ""
        return f"{self.exam} - {self.student.username}{section_str}: {self.marks}"


class Query(models.Model):
    answer_script = models.ForeignKey(AnswerScript, on_delete=models.CASCADE, related_name='queries')
    raised_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='queries_raised')
    text = models.TextField()
    response = models.TextField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='queries_resolved'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    class Meta:
        verbose_name_plural = "Queries"

    def __str__(self):
        return f"Query on {self.answer_script} by {self.raised_by.username}"


class TAAssignment(models.Model):
    ta = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='ta_assignments',
        limit_choices_to={'role': 'ta'}
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='ta_assignments')
    can_upload_scripts = models.BooleanField(default=False)
    can_resolve_queries = models.BooleanField(default=False)
    can_update_marks = models.BooleanField(default=False)

    class Meta:
        unique_together = ('ta', 'course')

    def __str__(self):
        return f"TA {self.ta.username} for {self.course.code}"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"To {self.user.username} - {self.created_at}"
        
