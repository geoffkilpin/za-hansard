from django.views.generic import ListView, DetailView, TemplateView
from za_hansard.models import Question, QuestionPaper, Answer
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.db.models import Count, Max


class QuestionMonitor(ListView):
    model = QuestionPaper
    template_name = 'admin/monitor.html'

    def get_context_data(self, **kwargs):
       #context = super(PlaceDetailSub, self).get_context_data(**kwargs)
       #context['child_place_grouper'] = self.child_place_grouper
       context={}
       context['QuestionPapers'] = QuestionPaper.objects.all().order_by('-date_published')
       return context

    @method_decorator(login_required(login_url='/admin/'))
    def dispatch(self, *args, **kwargs):
        return super(QuestionMonitor, self).dispatch(*args, **kwargs)

class QuestionMonitorList(ListView):
    model = Question
    template_name = 'admin/monitor-list.html'

    def get_context_data(self, **kwargs):
        #context = super(PlaceDetailSub, self).get_context_data(**kwargs)
        #context['child_place_grouper'] = self.child_place_grouper
        context={'questions': []}
        last_number = None

        parliament = self.request.GET.get('parliament')
        session = self.request.GET.get('session')

        if not parliament:
            parliament = QuestionPaper.objects.all().aggregate(Max('parliament_number'))['parliament_number__max']

        if not session:
            session = QuestionPaper.objects.filter(parliament_number=parliament).aggregate(Max('session_number'))['session_number__max']

        questions = Question.objects.all().filter(paper__parliament_number=parliament,paper__session_number=session).order_by('-house','-written_number')

        for question in questions:
            if last_number and last_number!=question.written_number+1:
               context['questions'].append({
                    'type': 'break'
                })

            context['questions'].append({'type': 'question','question': question})
            last_number=question.written_number



        return context

    @method_decorator(login_required(login_url='/admin/'))
    def dispatch(self, *args, **kwargs):
        return super(QuestionMonitorList, self).dispatch(*args, **kwargs)

class AnswerMonitorList(ListView):
    model = Answer
    template_name = 'admin/answer-monitor-list.html'

    def get_context_data(self, **kwargs):
       #context = super(PlaceDetailSub, self).get_context_data(**kwargs)
       #context['child_place_grouper'] = self.child_place_grouper
       context={}

       context['Total'] = Answer.objects.all().count()

       context['lastyear'] = Answer.objects.all().filter(year=2013).count()

       context['Matched'] = Answer.objects.annotate(num_questions=Count('question')).all().filter(num_questions__gt=0).count()

       context['gtmatch'] = Answer.objects.annotate(num_questions=Count('question')).all().filter(num_questions__gt=1).count()

       context['Answers'] = Answer.objects.all().filter(year=2014).order_by('-house','-year','-written_number')
       #for (key, answer) in enumerate(context['Answers']):
       #    context['Answers'][key]['Questions'] = answer.question.all()
       return context

    @method_decorator(login_required(login_url='/admin/'))
    def dispatch(self, *args, **kwargs):
        return super(AnswerMonitorList, self).dispatch(*args, **kwargs)

