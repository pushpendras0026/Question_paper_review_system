import os
import django
import random
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "QuestionReviewSystem.settings")
django.setup()

from core.models import User, Course
from django.contrib.auth.hashers import make_password

DEPARTMENTS = ['CSE', 'ECE', 'ME', 'CE', 'EEE', 'MNC', 'PH', 'CH']

def scrape_courses():
    base_url = 'https://iitg.ac.in/acad/CourseStructure/Btech2018/'
    main_url = 'https://iitg.ac.in/acad/CourseStructure/Btech2018/BTechProgrammes.htm'
    try:
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
                res = requests.get(url, verify=False)
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
                pass
        return list(all_courses)
    except Exception as e:
        print(f"Scraping failed: {e}")
        return []

def main():
    print("Scraping courses from IITG site...")
    courses = scrape_courses()
    print(f"Found {len(courses)} courses.")

    print("Generating Professors...")
    professors = []
    for i in range(1, 11):
        username = f"prof{i}"
        dept = random.choice(DEPARTMENTS)
        user, _ = User.objects.get_or_create(username=username, defaults={
            'role': 'professor',
            'department': dept,
            'faculty_id': f"FAC{i}",
            'first_name': f"Prof {i}",
            'email': f"{username}@iitg.ac.in"
        })
        user.set_password('password123')
        user.save()
        professors.append(user)

    print("Generating Students and TAs...")
    for dept in DEPARTMENTS:
        for i in range(1, 21):
            username = f"{dept.lower()}_student{i}"
            user, _ = User.objects.get_or_create(username=username, defaults={
                'role': 'student',
                'department': dept,
                'roll_number': f"2101{dept}{i:03d}",
                'first_name': f"Student {i}",
                'email': f"{username}@iitg.ac.in"
            })
            user.set_password('password123')
            user.save()
            
        for i in range(1, 6):
            username = f"{dept.lower()}_ta{i}"
            user, _ = User.objects.get_or_create(username=username, defaults={
                'role': 'ta',
                'department': dept,
                'first_name': f"TA {i}",
                'email': f"{username}@iitg.ac.in"
            })
            user.set_password('password123')
            user.save()

    print("Saving Courses...")
    admin_user = User.objects.filter(role='admin').first()
    for code, name in courses:
        dept = ''.join([c for c in code if c.isalpha()])
        if dept not in DEPARTMENTS and len(dept) > 0:
            dept = random.choice(DEPARTMENTS)
        elif len(dept) == 0:
            dept = random.choice(DEPARTMENTS)

        Course.objects.get_or_create(code=code, defaults={
            'name': name[:200],
            'professor': random.choice(professors),
            'department': dept,
            'semester': random.randint(1, 8),
            'created_by': admin_user
        })

    print("Database seeding completed successfully.")

if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    main()
