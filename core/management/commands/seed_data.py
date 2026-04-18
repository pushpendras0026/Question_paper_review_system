from django.core.management.base import BaseCommand
from core.models import User, Course, Enrollment, FacultyAdvisor, Exam, TAAssignment


class Command(BaseCommand):
    help = 'Seed the database with sample data for testing'

    def handle(self, *args, **options):
        self.stdout.write('Creating users...')

        # Common password
        password = 'pass'

        # Admin
        admin = User.objects.create_user(
            username='admin1', password=password, role='admin',
            first_name='Admin', last_name='User'
        )

        # 3 Professors
        professors = []
        for i in range(1, 4):
            prof = User.objects.create_user(
                username=f'prof{i}', password=password, role='professor',
                first_name=f'Professor', last_name=str(i)
            )
            professors.append(prof)
        prof1, prof2, prof3 = professors

        # 5 Students
        students = []
        for i in range(1, 6):
            student = User.objects.create_user(
                username=f'student{i}', password=password, role='student',
                first_name=f'Student', last_name=str(i)
            )
            students.append(student)
        stud1, stud2, stud3, stud4, stud5 = students

        # 2 TAs
        tas = []
        for i in range(1, 3):
            ta = User.objects.create_user(
                username=f'ta{i}', password=password, role='ta',
                first_name=f'TA', last_name=str(i)
            )
            tas.append(ta)
        ta1, ta2 = tas

        self.stdout.write('Creating courses...')

        # Active courses (Spring 2026 = current semester)
        cs101 = Course.objects.create(
            code='CS101', name='Intro to Computer Science',
            semester='Spring 2026', professor=prof1, created_by=admin
        )
        cs201 = Course.objects.create(
            code='CS201', name='Data Structures',
            semester='Spring 2026', professor=prof2, created_by=admin
        )
        # Completed course
        cs100 = Course.objects.create(
            code='CS100', name='Programming Basics',
            semester='Fall 2025', professor=prof1, created_by=admin, is_active=False
        )

        self.stdout.write('Setting up enrollments...')

        # Active enrollments
        Enrollment.objects.create(student=stud1, course=cs101, status='approved')
        Enrollment.objects.create(student=stud2, course=cs101, status='approved')
        Enrollment.objects.create(student=stud4, course=cs101, status='approved')
        
        Enrollment.objects.create(student=stud1, course=cs201, status='approved')
        Enrollment.objects.create(student=stud5, course=cs201, status='approved')

        # Completed enrollment with grade
        Enrollment.objects.create(student=stud1, course=cs100, status='approved')
        Enrollment.objects.create(student=stud2, course=cs100, status='approved')
        Enrollment.objects.create(student=stud4, course=cs100, status='approved')

        # Pending enrollment
        Enrollment.objects.create(student=stud3, course=cs101, status='pending_professor')

        self.stdout.write('Setting up faculty advisors...')
        FacultyAdvisor.objects.create(student=stud1, advisor=prof1)
        FacultyAdvisor.objects.create(student=stud2, advisor=prof2)
        FacultyAdvisor.objects.create(student=stud3, advisor=prof1)
        FacultyAdvisor.objects.create(student=stud4, advisor=prof3)
        FacultyAdvisor.objects.create(student=stud5, advisor=prof2)

        self.stdout.write('Creating exams...')
        exam1 = Exam.objects.create(course=cs101, name='Midterm 1')
        exam2 = Exam.objects.create(course=cs101, name='Final Exam')
        Exam.objects.create(course=cs100, name='Midterm')

        self.stdout.write('Setting up TA assignment...')
        TAAssignment.objects.create(
            ta=ta1, course=cs101,
            can_upload_scripts=True, can_resolve_queries=True,
            can_update_marks=True
        )
        TAAssignment.objects.create(
            ta=ta2, course=cs201,
            can_upload_scripts=True, can_resolve_queries=True,
            can_update_marks=True
        )

        self.stdout.write(self.style.SUCCESS(
            '\nSeed data created successfully!\n'
            '\nLogin credentials (all passwords: "pass"):\n'
            '  Admin:     admin1\n'
            '  Professor: prof1, prof2, prof3\n'
            '  Student:   student1, student2, student3, student4, student5\n'
            '  TA:        ta1, ta2\n'
        ))
