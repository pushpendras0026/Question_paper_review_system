from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, Course, FacultyAdvisor, Enrollment, Exam,
    ExamSection, AnswerScript, Mark, Query, TAAssignment
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff')
    list_filter = ('role',)
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Role', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Role', {'fields': ('role',)}),
    )


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'semester', 'professor', 'is_active')
    list_filter = ('is_active', 'semester')


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'status', 'grade')
    list_filter = ('status',)


@admin.register(FacultyAdvisor)
class FacultyAdvisorAdmin(admin.ModelAdmin):
    list_display = ('student', 'advisor')


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'created_at')


@admin.register(ExamSection)
class ExamSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'exam')


@admin.register(AnswerScript)
class AnswerScriptAdmin(admin.ModelAdmin):
    list_display = ('exam', 'student', 'uploaded_by', 'uploaded_at')


@admin.register(Mark)
class MarkAdmin(admin.ModelAdmin):
    list_display = ('exam', 'student', 'section', 'marks', 'old_marks')


@admin.register(Query)
class QueryAdmin(admin.ModelAdmin):
    list_display = ('answer_script', 'raised_by', 'is_resolved', 'created_at')


@admin.register(TAAssignment)
class TAAssignmentAdmin(admin.ModelAdmin):
    list_display = ('ta', 'course', 'can_upload_scripts', 'can_resolve_queries', 'can_update_marks', 'can_assign_grades')
