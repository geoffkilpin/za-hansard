from django.contrib import admin
from za_hansard.models import Question

class QuestionAdmin(admin.ModelAdmin):
    pass
admin.site.register(Question, QuestionAdmin)
