from django.contrib import admin

from . import models

admin.site.register(models.ScormPackage)
admin.site.register(models.Course)
admin.site.register(models.UserCourseRegistration)
admin.site.register(models.SCORMAttempt)
admin.site.register(models.SCORMElement)
admin.site.register(models.APIKeys)
admin.site.register(models.SCORMStandard)
