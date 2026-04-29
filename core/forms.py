from django import forms
from django.utils import timezone
from .models import (
    User, Course, Exam, AnswerScript, Mark, Query,
    TAAssignment, Enrollment
)


DEPARTMENT_CHOICES = [
    ('', 'Select Department'),
    ('CSE', 'CSE'),
    ('DSAI', 'DSAI'),
    ('ECE', 'ECE'),
    ('EEE', 'EEE'),
    ('ME', 'ME'),
    ('CE', 'CE'),
    ('Chemical', 'Chemical'),
    ('Biosciences', 'Biosciences'),
    ('Mathematics', 'Mathematics'),
    ('Physics', 'Physics'),
    ('Chemistry', 'Chemistry'),
    ('Humanities', 'Humanities'),
]


def get_semester_choices():
    current_year = timezone.now().year
    years = [current_year - 1, current_year, current_year + 1, current_year + 2]
    terms = ['Spring', 'Summer', 'Fall']
    choices = [('', 'Select Semester')]
    for year in years:
        for term in terms:
            value = f'{term} {year}'
            choices.append((value, value))
    return choices


class LoginForm(forms.Form):
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'name', 'semester', 'department', 'professor']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['professor'].queryset = User.objects.filter(role='professor')
        self.fields['semester'] = forms.ChoiceField(choices=get_semester_choices())
        self.fields['department'] = forms.ChoiceField(choices=DEPARTMENT_CHOICES)


class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ['name', 'weightage', 'max_marks', 'query_window_start', 'query_window_end']
        widgets = {
            'weightage': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'max_marks': forms.NumberInput(attrs={'step': '0.01', 'min': '0.01'}),
            'query_window_start': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'query_window_end': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }



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
            'text': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe your query'}),
        }


class QueryResponseForm(forms.Form):
    response = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}))


class TAAssignmentForm(forms.ModelForm):
    class Meta:
        model = TAAssignment
        fields = ['ta', 'can_upload_scripts', 'can_resolve_queries', 'can_update_marks']

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
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES)
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'faculty_id', 'password']

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email.endswith('@iitg.ac.in'):
            raise forms.ValidationError('Email must end with @iitg.ac.in')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'professor'
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class AdminAddStudentForm(forms.ModelForm):
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES)
    faculty_advisor = forms.ModelChoiceField(
        queryset=User.objects.filter(role='professor'),
        required=True,
        label="Faculty Advisor"
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'roll_number']

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email.endswith('@iitg.ac.in'):
            raise forms.ValidationError('Email must end with @iitg.ac.in')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'
        if user.roll_number:
            user.set_password(user.roll_number)
        else:
            user.set_password('password')
        if commit:
            user.save()
            advisor = self.cleaned_data.get('faculty_advisor')
            if advisor:
                from .models import FacultyAdvisor
                FacultyAdvisor.objects.update_or_create(student=user, defaults={'advisor': advisor})
        return user


class AdminAddTAForm(forms.ModelForm):
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES)
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'roll_number', 'password']

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email.endswith('@iitg.ac.in'):
            raise forms.ValidationError('Email must end with @iitg.ac.in')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'ta'
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class StudentSignupForm(forms.ModelForm):
    department = forms.ChoiceField(choices=DEPARTMENT_CHOICES)
    faculty_advisor = forms.ModelChoiceField(
        queryset=User.objects.filter(role='professor'),
        required=True,
        label="Faculty Advisor"
    )
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Password")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'department', 'roll_number', 'password']

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email.endswith('@iitg.ac.in'):
            raise forms.ValidationError('Email must end with @iitg.ac.in')
        # Check if email is already taken
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email is already registered')
        return email

    def clean_roll_number(self):
        roll = self.cleaned_data.get('roll_number')
        if User.objects.filter(roll_number=roll).exists():
            raise forms.ValidationError('Roll number is already registered')
        return roll

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'student'
        user.status = 'pending'
        user.is_active = False  # Needs admin approval
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
            advisor = self.cleaned_data.get('faculty_advisor')
            if advisor:
                from .models import FacultyAdvisor
                FacultyAdvisor.objects.update_or_create(student=user, defaults={'advisor': advisor})
        return user

class AdminForceEnrollForm(forms.Form):
    roll_number = forms.CharField(max_length=50, label='Student Roll Number')
    course = forms.ModelChoiceField(queryset=Course.objects.filter(is_active=True), label='Select Course')
