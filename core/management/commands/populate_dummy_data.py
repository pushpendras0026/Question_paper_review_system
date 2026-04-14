import os
import random
import string
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.contrib.auth.hashers import make_password
from core.models import User, Course, FacultyAdvisor, Enrollment, Exam, ExamSection, AnswerScript, Mark, Query, TAAssignment

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class Command(BaseCommand):
    help = 'Scrape IITG courses and populate database with robust dummy data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Clearing existing non-superuser data...')
        
        # Keep superusers, delete the rest
        User.objects.filter(is_superuser=False).delete()
        Course.objects.all().delete()
        
        self.stdout.write('Scraping IITG course structures...')
        courses_data = self.scrape_courses()
        self.stdout.write(f'Found {len(courses_data)} unique courses.')

        # ----------------------------------------------------
        # 1. Create Users
        # ----------------------------------------------------
        self.stdout.write('Generating sample users...')
        password = make_password('password123')
        
        professors = []
        for i in range(1, 11):
            prof = User.objects.create(
                username=f'prof{i}', roll_number=f'P{i:03d}', email=f'prof{i}@example.com', role='professor', password=password,
                first_name=f'Prof{i}', last_name='Test'
            )
            professors.append(prof)
            
        tas = []
        for i in range(1, 21):
            ta = User.objects.create(
                username=f'ta{i}', roll_number=f'T{i:03d}', email=f'ta{i}@example.com', role='ta', password=password,
                first_name=f'TA{i}', last_name='User'
            )
            tas.append(ta)
            
        students = []
        for i in range(1, 101):
            student = User.objects.create(
                username=f'student{i}', roll_number=f'220101{i:03d}', email=f'student{i}@example.com', role='student', password=password,
                first_name=f'Student{i}', last_name='Test'
            )
            students.append(student)

        # ----------------------------------------------------
        # 2. Populate Courses & Faculty Advisors
        # ----------------------------------------------------
        self.stdout.write('Populating courses...')
        semesters = [str(i) for i in range(1, 9)]
        created_courses = []
        
        # Deduplicate by code
        unique_codes = {}
        for code, name in courses_data:
            if code not in unique_codes:
                unique_codes[code] = name
        
        for code, name in unique_codes.items():
            course = Course(
                code=code,
                name=name,
                semester=random.choice(semesters),
                is_active=True,
                professor=random.choice(professors)
            )
            created_courses.append(course)
        
        # Bulk create for speed
        Course.objects.bulk_create(created_courses)
        saved_courses = list(Course.objects.all())

        # Faculty Advisors
        advisor_objects = []
        for student in students:
            advisor_objects.append(FacultyAdvisor(student=student, advisor=random.choice(professors)))
        FacultyAdvisor.objects.bulk_create(advisor_objects)

        # ----------------------------------------------------
        # 3. Enrollments & TA Assignments
        # ----------------------------------------------------
        self.stdout.write('Creating Enrollments and TA Assignments...')
        enrollments = []
        ta_assignments = []
        
        for course in saved_courses:
            # Assign 1-3 TAs per course (only for a subset of courses to save time, or all)
            if random.random() > 0.5:
                assigned_tas = random.sample(tas, random.randint(1, 3))
                for ta in assigned_tas:
                    ta_assignments.append(TAAssignment(
                        ta=ta,
                        course=course,
                        can_upload_scripts=random.choice([True, False]),
                        can_resolve_queries=random.choice([True, False]),
                        can_update_marks=random.choice([True, False])
                    ))
            
            # Enroll 5-20 students
            enrolled_students = random.sample(students, random.randint(5, 20))
            for student in enrolled_students:
                status = random.choice(['pending_professor', 'pending_advisor', 'approved', 'rejected'])
                enrollments.append(Enrollment(student=student, course=course, status=status))

        TAAssignment.objects.bulk_create(ta_assignments)
        Enrollment.objects.bulk_create(enrollments)

        # ----------------------------------------------------
        # 4. Exams, Answers, and Marks
        # ----------------------------------------------------
        self.stdout.write('Generating Exams, Scripts, Marks, and Queries...')
        
        # Generate dummy pdf content
        dummy_file_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n"
        
        # Select 20 random courses to have exams to prevent huge DB size
        exam_courses = random.sample(saved_courses, min(20, len(saved_courses)))
        
        for course in exam_courses:
            for exam_name in ['Mid Sem Exam', 'End Sem Exam']:
                exam = Exam.objects.create(course=course, name=exam_name)
                
                sec_a = ExamSection.objects.create(exam=exam, name='Section A (Objective)')
                sec_b = ExamSection.objects.create(exam=exam, name='Section B (Subjective)')
                
                # Get approved students
                course_students = [e.student for e in Enrollment.objects.filter(course=course, status='approved')]
                
                for student in course_students:
                    # Upload script
                    script = AnswerScript(exam=exam, student=student, uploaded_by=course.professor)
                    script.file.save(f'{course.code}_{student.username}_{exam_name.replace(" ", "_")}.pdf', ContentFile(dummy_file_content))
                    script.save()
                    
                    # Marks
                    mark_a = random.randint(10, 50)
                    mark_b = random.randint(10, 50)
                    Mark.objects.create(exam=exam, student=student, section=sec_a, marks=mark_a)
                    Mark.objects.create(exam=exam, student=student, section=sec_b, marks=mark_b)
                    
                    # Random query
                    if random.random() > 0.7:
                        query = Query.objects.create(
                            answer_script=script,
                            raised_by=student,
                            text=f"Please recheck my evaluation in {exam_name}.",
                            is_resolved=random.choice([True, False])
                        )
                        if query.is_resolved:
                            query.response = "Rechecked and verified. No change."
                            query.resolved_by = course.professor
                            query.save()

        self.stdout.write(self.style.SUCCESS('Successfully populated dummy data and scraped courses!'))

    def scrape_courses(self):
        base_url = 'https://iitg.ac.in/acad/CourseStructure/Btech2018/'
        main_url = 'https://iitg.ac.in/acad/CourseStructure/Btech2018/BTechProgrammes.htm'
        response = requests.get(main_url, verify=False)
        soup = BeautifulSoup(response.content, 'html.parser')

        course_links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.endswith('.htm') and 'http' not in href:
                full_url = urljoin(base_url, href)
                course_links.append(full_url)
            elif href.startswith('https://iitg.ac.in/acad/CourseStructure/Btech2018/') and href.endswith('.htm'):
                course_links.append(href)

        course_links = list(set(course_links))
        all_courses = set()

        for url in course_links:
            try:
                res = requests.get(url, verify=False, timeout=10)
                page_soup = BeautifulSoup(res.content, 'html.parser')
                for table in page_soup.find_all('table'):
                    for tr in table.find_all('tr'):
                        tds = tr.find_all(['td', 'th'])
                        row = [td.get_text(strip=True).replace('\n', ' ').replace('\r', '') for td in tds]
                        
                        if len(row) >= 6:
                            code = row[0].strip()
                            name = row[1].strip()
                            if re.match(r'^[A-Z]{2,3}\s*\d{3}$', code) or ('xx' in code and len(code) <= 7):
                                all_courses.add((code, name))
                        
                        if len(row) >= 12:
                            code = row[6].strip()
                            name = row[7].strip()
                            if re.match(r'^[A-Z]{2,3}\s*\d{3}$', code) or ('xx' in code and len(code) <= 7):
                                all_courses.add((code, name))
            except Exception as e:
                pass # ignore fetch errors for specific links

        return list(all_courses)
