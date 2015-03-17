# coding: utf-8

import json
from django.http import HttpResponse
from django.views.generic import View
from django.utils.decorators import method_decorator
from django.forms.models import model_to_dict
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from forum.models import Topic, Reply, Pages
from forum.forms.topic import ReplyForm, CreateForm
from forum.views.common import find_mentions
from oauth import login_required


_STATUS_CODE = {
    200: 'OK',
    201: 'CREATED',
    202: 'Accepted',
    204: 'NO CONTENT',
    400: 'INVALID REQUEST',
    401: 'Unauthorized',
    403: 'Forbidden',
    404: 'NOT FOUND',
    406: 'Not Acceptable',
    410: 'Gone',
    422: 'Unprocesable entity',
    500: 'INTERNAL SERVER ERROR',
}


def _status_code(code, json=None):
    if not json:
        json = to_json({
            'code': code,
            'message': _STATUS_CODE.get(code, 'UNKOWN')
        })
    return HttpResponse(json, content_type='application/json; charset=UTF-8', status=code)


class ComplexEncoder(DjangoJSONEncoder):
    def default(self, obj):
        if isinstance(obj, Pages):
            del obj._current
            return obj.__dict__
        return super(ComplexEncoder, self).default(obj)


def to_json(obj):
    return json.dumps(obj, cls=ComplexEncoder, ensure_ascii=False).encode('utf8')


def check_secure(func):
    '''
    装饰器，用于过滤非https的请求直接返回403
    '''
    def _wrapped_view(request, *args, **kwargs):
        if request.is_secure():
            return func(request, *args, **kwargs)
        return _status_code(403)
    return _wrapped_view


class BaseView(View):
    '''
    基类，重写dispatch过滤非https请求
    '''
    # @method_decorator(check_secure)
    def dispatch(self, *args, **kwargs):
        return super(BaseView, self).dispatch(*args, **kwargs)


class TopicsView(BaseView):
    def get(self, request):
        try:
            current_page = int(request.GET.get('p', '1'))
        except ValueError:
            return _status_code(400)
        count = Topic.objects.all().count()
        page = Pages(count, current_page, 20)
        query = Topic.objects.all().values('title', 'content', 'created', 'updated',\
            'node__name', 'author__id', 'author__username', 'author__username',\
            'author__nickname', 'author__avatar').order_by('-last_touched',\
            '-created', '-last_replied_time', '-id')[page.start:page.end]
        l = []
        for v in query:
            v['author'] = {}
            keys = v.keys()
            for k in keys:
                if k.startswith('author__'):
                    v['author'][k[8:]] = v.pop(k)
            l.append(v)
        json = to_json({'topics': l, 'page': page})
        return _status_code(200, json)

    @method_decorator(login_required)
    def post(self, request):
        try:
            params = json.loads(request.body)
        except:
            return _status_code(400)
        form = CreateForm(params)
        if not form.is_valid():
            return _status_code(422, form.errors.as_json())

        user = request.user
        try:
            last_created = user.topic_author.all().order_by('-created')[0]
        except IndexError:
            last_created = None

        if last_created: # 如果用户最后一篇的标题内容与提交的相同
            last_created_fingerprint = hashlib.sha1(last_created.title + \
                last_created.content + str(last_created.node_id)).hexdigest()
            new_created_fingerprint = hashlib.sha1(form.cleaned_data.get('title') + \
                form.cleaned_data.get('content') + str(node.id)).hexdigest()

            if last_created_fingerprint == new_created_fingerprint:
                return _status_code(422)

        now = timezone.now()
        topic = Topic(
            title = form.cleaned_data.get('title'),
            content = form.cleaned_data.get('content'),
            created = now,
            node = node,
            author = user,
            reply_count = 0,
            last_touched = now,
        )
        topic.save()

        reputation = user.reputation or 0
        reputation = reputation - 5 # 每次发布话题扣除用户威望5点
        reputation = 0 if reputation < 0 else reputation
        ForumUser.objects.filter(pk=user.id).update(reputation=reputation)
        query = Topic.objects.filter(pk=topic.id).values('title', 'content', 'created', 'updated',\
            'node__name', 'author__id', 'author__username', 'author__username',\
            'author__nickname', 'author__avatar')
        l = []
        for v in query:
            v['author'] = {}
            keys = v.keys()
            for k in keys:
                if k.startswith('author__'):
                    v['author'][k[8:]] = v.pop(k)
            l.append(v)
        json = to_json(l[0])
        return _status_code(201, json)


class TopicView(BaseView):
    def get(self, request, id):
        query = Topic.objects.filter(pk=id).values('title', 'content', 'created', 'updated',\
            'node__name', 'author__id', 'author__username', 'author__username',\
            'author__nickname', 'author__avatar')
        if not query:
            return _status_code(404)
        l = []
        for v in query:
            v['author'] = {}
            keys = v.keys()
            for k in keys:
                if k.startswith('author__'):
                    v['author'][k[8:]] = v.pop(k)
            l.append(v)
        json = to_json(l[0])
        return _status_code(200, json)

    @method_decorator(login_required)
    def put(self, request):
        try:
            topic = Topic.objects.get(pk=id)
        except Topic.DoesNotExist:
            return _status_code(404)

        try:
            params = json.loads(request.body)
        except:
            return _status_code(400)
        form = CreateForm(params)
        if not form.is_valid():
            return _status_code(422, form.errors.as_json())

        user = request.user
        if topic.author_id != user.id:
            return _status_code(401)

        now = timezone.now()
        Topic.objects.filter(pk=topic.id).update(updated=now, last_touched=now, **form.cleaned_data)

        reputation = user.reputation or 0
        reputation = reputation - 2 # 每次修改回复扣除用户威望2点
        reputation = 0 if reputation < 0 else reputation
        ForumUser.objects.filter(pk=user.id).update(reputation=reputation)

        query = Topic.objects.filter(pk=topic.id).values('title', 'content', 'created', 'updated',\
            'node__name', 'author__id', 'author__username', 'author__username',\
            'author__nickname', 'author__avatar')
        l = []
        for v in query:
            v['author'] = {}
            keys = v.keys()
            for k in keys:
                if k.startswith('author__'):
                    v['author'][k[8:]] = v.pop(k)
            l.append(v)
        json = to_json(l[0])
        return _status_code(201, json)


class ReplysView(BaseView):
    def get(self, request, id):
        if not Topic.objects.filter(pk=id).exists():
            return _status_code(404)
        try:
            current_page = int(request.GET.get('p', '1'))
        except ValueError:
            return _status_code(400)
        count = Reply.objects.filter(topic__id=id).count()
        page = Pages(count, current_page, 20)
        query = Reply.objects.filter(topic__id=id).values('content', 'created', 'updated',\
            'author__id', 'author__username', 'author__username',\
            'author__nickname', 'author__avatar').order_by('-id')[page.start:page.end]
        l = []
        for v in query:
            v['author'] = {}
            keys = v.keys()
            for k in keys:
                if k.startswith('author__'):
                    v['author'][k[8:]] = v.pop(k)
            l.append(v)
        json = to_json({'replies': l, 'page': page})
        return _status_code(200, json)

    @method_decorator(login_required)
    def post(self, request, id):
        try:
            topic = Topic.objects.select_related('author').get(pk=id)
        except Topic.DoesNotExist:
            return _status_code(404)
        try:
            params = json.loads(request.body)
        except:
            return _status_code(400)
        form = ReplyForm(params)
        if not form.is_valid():
            return _status_code(422, form.errors.as_json())

        user = request.user
        try:
            last_reply = topic.reply_set.all().order_by('-created')[0]
        except IndexError:
            last_reply = None
        if last_reply:
            last_replied_fingerprint = hashlib.sha1(str(topic.id) + str(last_reply.author_id) + last_reply.content).hexdigest()
            new_replied_fingerprint = hashlib.sha1(str(topic.id) + str(user.id) + form.cleaned_data.get('content')).hexdigest()
            if last_replied_fingerprint == new_replied_fingerprint:
                return _status_code(422)

        now = timezone.now()
        reply = Reply(
            topic = topic,
            author = user,
            content = form.cleaned_data.get('content'),
            created = now,
        )
        reply.save()
        Topic.objects.filter(pk=topic.id).update(last_replied_by=user, last_replied_time=now, last_touched=now)

        notifications = []
        if user.id != topic.author.id:
            notification = Notification(
                content = form.cleaned_data.get('content'),
                status = 0,
                involved_type = 1, # 0: mention, 1: reply
                involved_user = topic.author,
                involved_topic = topic,
                trigger_user = user,
                occurrence_time = now,
            )
            notifications.append(notification)

        mentions = find_mentions(form.cleaned_data.get('content'))
        if user.username in mentions:
            mentions.remove(user.username)
        if topic.author.username in mentions:
            mentions.remove(topic.author.username)
        if mentions:
            mention_users = ForumUser.objects.filter(username__in=mentions)
            if mention_users:
                for mention_user in mention_users:
                    notification = Notification(
                        content = form.cleaned_data.get('content'),
                        status = 0,
                        involved_type = 0, # 0: mention, 1: reply
                        involved_user = mention_user,
                        involved_topic = topic,
                        trigger_user = user,
                        occurrence_time = now,
                    )
                    notifications.append(notification)
        if notifications:
            Notification.objects.bulk_create(notifications)

        if user.id != topic.author.id:
            topic_time_diff = timezone.now() - topic.created
            reputation = topic.author.reputation or 0
            reputation = reputation + 2 * math.log(user.reputation or 0 + topic_time_diff.days + 10, 10)
            ForumUser.objects.filter(pk=topic.author.id).update(reputation=reputation)
        return self.get(request)
