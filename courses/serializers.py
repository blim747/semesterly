import re

from django.forms import model_to_dict
from django.db import models
from rest_framework import serializers

from timetable.models import Course, Section, Evaluation,  CourseIntegration, Integration, Semester
import utils


class EvaluationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Evaluation
        fields = '__all__'


class FlatCourseSerializer(serializers.ModelSerializer):
    evals = serializers.SerializerMethodField()
    integrations = serializers.SerializerMethodField()
    related_courses = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    textbooks = serializers.SerializerMethodField()
    regexed_courses = serializers.SerializerMethodField()
    popularity_percent = serializers.SerializerMethodField()
    is_waitlist_only = serializers.SerializerMethodField()

    slots = serializers.SerializerMethodField()
    enrolled_sections = serializers.SerializerMethodField()

    def get_evals(self, course):
        """
        Flag all eval instances s.t. there exists repeated term+year values.
        Return:
          List of modified evaluation dictionaries (added flag 'unique_term_year')
        """
        evals = map(model_to_dict, Evaluation.objects.filter(course=course).order_by('year'))
        years = Evaluation.objects.filter(course=course).values('year').annotate(models.Count('id')) \
            .filter(id__count__gt=1).values_list('year')
        years = {e[0] for e in years}
        for course_eval in evals:
            course_eval['unique_term_year'] = not course_eval['year'] in years
        return evals

    def get_integrations(self, course):
        ids = CourseIntegration.objects.filter(course__id=course.id).values_list("integration",
                                                                                 flat=True)
        return list(Integration.objects.filter(id__in=ids).values_list("name", flat=True))

    def get_related_courses(self, course):
        info = []
        related = course.related_courses.filter(
            section__semester=self.context['semester']).distinct()[:5]
        for course in related:
            info.append(model_to_dict(course, exclude=['related_courses', 'unstopped_description']))
        return info

    def get_reactions(self, course):
        return course.get_reactions(self.context.get('student'))

    def get_textbooks(self, course):
        return list(
            set(tb for section in course.section_set.filter(semester=self.context['semester'])
                for tb in section.get_textbooks()))

    def get_regexed_courses(self, course):
        """
        Given course data, search for all occurrences of a course code in the course description and
        prereq info and return a map from course code to course name for each course code.
        """
        school_to_course_regex = {
            'jhu': r'([A-Z]{2}\.\d{3}\.\d{3})',
            'uoft': r'([A-Z]{3}[A-Z0-9]\d{2}[HY]\d)',
            'vandy': r'([A-Z-&]{2,7}\s\d{4}[W]?)',
            'gw': r'([A-Z]{2,5}\s\d{4}[W]?)',
            'umich': r'([A-Z]{2,8}\s\d{3})',
            'chapman': r'([A-Z]{2,4}\s\d{3})',
            'salisbury': r'([A-Z]{3,4} \d{2,3})',
        }
        course_code_to_name = {}
        if self.context['school'] in school_to_course_regex:
            course_code_matches = re.findall(school_to_course_regex[self.context['school']],
                                             course.description + course.prerequisites)
            # TODO: get all course objects in one db access
            for course_code in course_code_matches:
                try:
                    course = Course.objects.get(school=self.context['school'],
                                                code__icontains=course_code)
                    course_code_to_name[course_code] = course.name
                except (Course.DoesNotExist, Course.MultipleObjectsReturned):
                    pass
        return course_code_to_name

    def get_popularity_percent(self, course):
        """ Return percentage of course capacity that is filled by registered students. """
        tts_with_course = course.personaltimetable_set.filter(semester=self.context['semester'])
        num_students_in_course = tts_with_course.values('student').distinct().count()
        sections = course.section_set.filter(semester=self.context['semester'])
        course_capacity = sum(sections.values_list('size', flat=True)) if sections else 0
        return num_students_in_course / float(course_capacity) if course_capacity else 0

    def get_is_waitlist_only(self, course):
        return utils.is_waitlist_only(course, self.context['semester'])

    # TODO: move in to timetable
    def get_slots(self, course):
        return [dict(get_section_dict(section), **model_to_dict(co))
                    for section in self.context['sections'] for co in section.offering_set.all()]

    def get_enrolled_sections(self, course):
        return [section.meeting_section for section in self.context['sections']]


    class Meta:
        model = Course
        fields = (
            'code',
            'name',
            'id',
            'description',
            'department',
            'num_credits',
            'areas',
            'campus',
            'evals',
            'integrations',
            'related_courses',
            'reactions',
            'textbooks',
            'regexed_courses',
            'popularity_percent',
            'prerequisites',
            'exclusions',
            'areas',
            'is_waitlist_only',
            'slots',
            'enrolled_sections',
        )


class CourseSerializer(serializers.ModelSerializer):
    """
    Serialize a Course into a dictionary with detailed information about the course, and all
    related entities (eg Sections). Used for search results and course modals.
    Takes a context with parameters:
        school: str (required)
        semester: Semester (required)
        student: Student (optional)
    """
    evals = serializers.SerializerMethodField()
    integrations = serializers.SerializerMethodField()
    related_courses = serializers.SerializerMethodField()
    reactions = serializers.SerializerMethodField()
    textbooks = serializers.SerializerMethodField()
    regexed_courses = serializers.SerializerMethodField()
    popularity_percent = serializers.SerializerMethodField()
    is_waitlist_only = serializers.SerializerMethodField()

    sections = serializers.SerializerMethodField()

    def get_evals(self, course):
        """
        Flag all eval instances s.t. there exists repeated term+year values.
        Return:
          List of modified evaluation dictionaries (added flag 'unique_term_year')
        """
        evals = map(model_to_dict, Evaluation.objects.filter(course=course).order_by('year'))
        years = Evaluation.objects.filter(course=course).values('year').annotate(models.Count('id')) \
            .filter(id__count__gt=1).values_list('year')
        years = {e[0] for e in years}
        for course_eval in evals:
            course_eval['unique_term_year'] = not course_eval['year'] in years
        return evals

    def get_integrations(self, course):
        ids = CourseIntegration.objects.filter(course__id=course.id).values_list("integration",
                                                                                 flat=True)
        return list(Integration.objects.filter(id__in=ids).values_list("name", flat=True))

    def get_related_courses(self, course):
        info = []
        related = course.related_courses.filter(
            section__semester=self.context['semester']).distinct()[:5]
        for course in related:
            info.append(model_to_dict(course, exclude=['related_courses', 'unstopped_description']))
        return info

    def get_reactions(self, course):
        return course.get_reactions(self.context.get('student'))

    def get_textbooks(self, course):
        return list(
            set(tb for section in course.section_set.filter(semester=self.context['semester'])
                for tb in section.get_textbooks()))

    def get_regexed_courses(self, course):
        """
        Given course data, search for all occurrences of a course code in the course description and
        prereq info and return a map from course code to course name for each course code.
        """
        school_to_course_regex = {
            'jhu': r'([A-Z]{2}\.\d{3}\.\d{3})',
            'uoft': r'([A-Z]{3}[A-Z0-9]\d{2}[HY]\d)',
            'vandy': r'([A-Z-&]{2,7}\s\d{4}[W]?)',
            'gw': r'([A-Z]{2,5}\s\d{4}[W]?)',
            'umich': r'([A-Z]{2,8}\s\d{3})',
            'chapman': r'([A-Z]{2,4}\s\d{3})',
            'salisbury': r'([A-Z]{3,4} \d{2,3})',
        }
        course_code_to_name = {}
        if self.context['school'] in school_to_course_regex:
            course_code_matches = re.findall(school_to_course_regex[self.context['school']],
                                             course.description + course.prerequisites)
            # TODO: get all course objects in one db access
            for course_code in course_code_matches:
                try:
                    course = Course.objects.get(school=self.context['school'],
                                                code__icontains=course_code)
                    course_code_to_name[course_code] = course.name
                except (Course.DoesNotExist, Course.MultipleObjectsReturned):
                    pass
        return course_code_to_name

    def get_popularity_percent(self, course):
        """ Return percentage of course capacity that is filled by registered students. """
        tts_with_course = course.personaltimetable_set.filter(semester=self.context['semester'])
        num_students_in_course = tts_with_course.values('student').distinct().count()
        sections = course.section_set.filter(semester=self.context['semester'])
        course_capacity = sum(sections.values_list('size', flat=True)) if sections else 0
        return num_students_in_course / float(course_capacity) if course_capacity else 0

    def get_is_waitlist_only(self, course):
        return utils.is_waitlist_only(course, self.context['semester'])

    def get_sections(self, course):
        return [SectionSerializer(section).data
                for section in course.section_set.filter(semester=self.context['semester'])]

    class Meta:
        model = Course
        fields = (
            'code',
            'name',
            'id',
            'description',
            'department',
            'num_credits',
            'areas',
            'campus',
            'evals',
            'integrations',
            'related_courses',
            'reactions',
            'textbooks',
            'regexed_courses',
            'popularity_percent',
            'sections',
            'prerequisites',
            'exclusions',
            'areas',
            'is_waitlist_only'
        )


class SectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Section
        fields = (
            'meeting_section',
            'size',
            'enrolment',
            'waitlist',
            'waitlist_size',
            'section_type',
            'instructors',
            'semester',
            'offering_set'
        )
        depth = 1 # also serializer offerings


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'
        model = Semester


def get_section_dict(section):
    section_data = model_to_dict(section)
    section_data['is_section_filled'] = section.is_full()
    return section_data
