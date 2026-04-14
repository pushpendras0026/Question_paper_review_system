import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

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
print(f"Found {len(course_links)} programme links:")
for link in course_links:
    print(link)

all_courses = set()

for url in course_links:
    res = requests.get(url, verify=False)
    page_soup = BeautifulSoup(res.content, 'html.parser')
    for table in page_soup.find_all('table'):
        for tr in table.find_all('tr'):
            tds = tr.find_all(['td', 'th'])
            row = [td.get_text(strip=True).replace('\n', ' ').replace('\r', '') for td in tds]
            
            # Left course
            if len(row) >= 6:
                code = row[0].strip()
                name = row[1].strip()
                if re.match(r'^[A-Z]{2,3}\s*\d{3}$', code) or ('xx' in code and len(code) <= 7):
                    all_courses.add((code, name))
            
            # Right course
            if len(row) >= 12:
                code = row[6].strip()
                name = row[7].strip()
                if re.match(r'^[A-Z]{2,3}\s*\d{3}$', code) or ('xx' in code and len(code) <= 7):
                    all_courses.add((code, name))

print(f"\nTotal unique courses found: {len(all_courses)}")
for c in list(all_courses)[:10]:
    print(c)
