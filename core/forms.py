from django import forms
from .models import (
    User, Course, Exam, ExamSection, AnswerScript, Mark, Query,
    TAAssignment, Enrollment
)


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'name', 'semester', 'department', 'professor', 'grade_card_deadline']
        widgets = {
            'grade_card_deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['professor'].queryset = User.objects.filter(role='professor')


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'query_window_start', 'query_window_end']
        widgets = {
            'query_window_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'query_window_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class ExamSectionForm(forms.ModelForm):
    class Meta:
        model = ExamSection
        fields = ['name']


class AnswerScriptUploadForm(forms.Form):
    student = forms.ModelChoiceField(queryset=User.objects.filter(role='student'))
    file = forms.FileField()


class MarkForm(forms.Form):
    marks = forms.DecimalField(max_digits=6, decimal_places=2)
    comment = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 2}))


class QueryForm(forms.ModelForm):
    class Meta:
        model = Query
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe your query...'}),
        }


class QueryResponseForm(forms.Form):
    response = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))


class GradeForm(forms.Form):
    grade = forms.CharField(max_length=5)


class TAAssignmentForm(forms.ModelForm):
    class Meta:
        model = TAAssignment
        fields = ['ta', 'can_upload_scripts', 'can_resolve_queries', 'can_update_marks', 'can_assign_grades']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ta'].queryset = User.objects.filter(role='ta')


class FacultyAdvisorForm(forms.Form):
    ASSIGNMENT_CHOICES = [('single', 'Single Assignment'), ('mass', 'Mass Assignment')]
    assignment_type = forms.ChoiceField(choices=ASSIGNMENT_CHOICES, initial='mass', widget=forms.RadioSelect)
    
    single_roll_number = forms.CharField(max_length=50, required=False)
    
    start_roll_number = forms.CharField(max_length=50, required=False)
    end_roll_number = forms.CharField(max_length=50, required=False)
    advisor = forms.ModelChoiceField(queryset=User.objects.filter(role='professor'))


class AdminAddFacultyForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'faculty_id']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'professor'
        # Default password is the faculty_id
        if user.faculty_id:
            user.set_password(user.faculty_id)
        else:
            user.set_password('password123!')
        if commit:
            user.save()
        return user


class AdminAddStudentForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'roll_number']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'
        # Default password is the roll_number
        if user.roll_number:
            user.set_password(user.roll_number)
        else:
            user.set_password('password123!')
        if commit:
            user.save()
        return user


class AdminCourseGradeDeadlineForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['grade_card_deadline']
        widgets = {
            'grade_card_deadline': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }


class AdminForceEnrollForm(forms.Form):
    roll_number = forms.CharField(max_length=50, label='Student Roll Number')
    course = forms.ModelChoiceField(queryset=Course.objects.filter(is_active=True), label='Select Course')
