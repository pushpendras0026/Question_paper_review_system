from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password, name='change_password'),

    # Student URLs
    path('student/', views.student_dashboard, name='student_dashboard'),
    path('student/add-course/', views.student_add_course, name='student_add_course'),
    path('student/course/<int:course_id>/', views.student_course_detail, name='student_course_detail'),
    path('student/course/<int:course_id>/scripts/<int:exam_id>/', views.student_view_scripts, name='student_view_scripts'),
    path('student/course/<int:course_id>/stats/', views.student_course_stats, name='student_course_stats'),
    path('student/course/<int:course_id>/past/', views.student_past_course, name='student_past_course'),
    path('student/script/<int:script_id>/query/', views.student_raise_query, name='student_raise_query'),

    # Professor URLs
    path('professor/', views.professor_dashboard, name='professor_dashboard'),
    path('professor/course/<int:course_id>/', views.professor_course_detail, name='professor_course_detail'),
    path('professor/course/<int:course_id>/add-exam/', views.professor_add_exam, name='professor_add_exam'),
    path('professor/exam/<int:exam_id>/add-section/', views.professor_add_section, name='professor_add_section'),
    path('professor/exam/<int:exam_id>/upload-scripts/', views.professor_upload_scripts, name='professor_upload_scripts'),
    path('professor/exam/<int:exam_id>/marks/', views.professor_enter_marks, name='professor_enter_marks'),
    path('professor/exam/<int:exam_id>/upload-csv/', views.professor_upload_csv_marks, name='professor_upload_csv_marks'),
    path('professor/approve-requests/', views.professor_approve_requests, name='professor_approve_requests'),
    path('professor/enrollment/<int:enrollment_id>/approve/', views.professor_approve_enrollment, name='professor_approve_enrollment'),
    path('professor/enrollment/<int:enrollment_id>/reject/', views.professor_reject_enrollment, name='professor_reject_enrollment'),
    path('professor/bulk-action/', views.professor_bulk_enrollment_action, name='professor_bulk_enrollment_action'),
    path('professor/course/<int:course_id>/manage-tas/', views.professor_manage_tas, name='professor_manage_tas'),
    path('professor/course/<int:course_id>/remove-ta/<int:assignment_id>/', views.professor_remove_ta, name='professor_remove_ta'),
    path('professor/course/<int:course_id>/completed/', views.professor_completed_course, name='professor_completed_course'),
    path('professor/course/<int:course_id>/queries/', views.professor_view_queries, name='professor_view_queries'),
    path('professor/query/<int:query_id>/respond/', views.professor_respond_query, name='professor_respond_query'),

    # Admin URLs
    path('app-admin/', views.admin_dashboard, name='admin_dashboard'),
    path('app-admin/create-course/', views.admin_create_course, name='admin_create_course'),
    path('app-admin/end-course/<int:course_id>/', views.admin_end_course, name='admin_end_course'),
    path('app-admin/manage-courses/', views.admin_manage_courses, name='admin_manage_courses'),
    path('app-admin/ended-courses/', views.admin_ended_courses, name='admin_ended_courses'),
    path('app-admin/add-faculty/', views.admin_add_faculty, name='admin_add_faculty'),
    path('app-admin/add-student/', views.admin_add_student, name='admin_add_student'),
    path('app-admin/course/<int:course_id>/grades/', views.admin_view_course_grades, name='admin_view_course_grades'),

    # TA URLs
    path('ta/', views.ta_dashboard, name='ta_dashboard'),
    path('ta/course/<int:assignment_id>/', views.ta_course_detail, name='ta_course_detail'),
    path('ta/course/<int:assignment_id>/upload-scripts/<int:exam_id>/', views.ta_upload_scripts, name='ta_upload_scripts'),
    path('ta/course/<int:assignment_id>/queries/', views.ta_view_queries, name='ta_view_queries'),
    path('ta/query/<int:query_id>/respond/', views.ta_respond_query, name='ta_respond_query'),
    path('ta/course/<int:assignment_id>/marks/<int:exam_id>/', views.ta_update_marks, name='ta_update_marks'),
]
