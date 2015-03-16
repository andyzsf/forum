# coding: utf-8

'''
Oauth2.0 认证
'''

import json, hashlib, time, base64, urllib
from django.shortcuts import render_to_response, redirect
from django.http import HttpResponse
from django.views.generic import View
from django.template import RequestContext
from django.conf import settings

from forum.models import ForumUser
from forum.views.user import get_login
from api.forms.oauth import OauthForm
from forum.forms.user import LoginForm


_OAUTH_ERROR = {
    '0001': 'unkown_client_id',
    '0002': 'redirect_uri_mismatch',
    '0003': 'unsupported_response_type',
    '0004': 'expired_token',
    '0005': 'login_failed',
    '0006': 'invalid_access_token'
}


def _oauth_error(code):
    error = {
        'error': code,
        'error_description': _OAUTH_ERROR.get(str(code), 'unkown_error')
    }
    return HttpResponse(json.dumps(error), content_type='application/json')


# 生成access_token
def make_access_token(client_id, id, password, max_age=5184000000):
    expires = str(int(time.time()) + max_age)
    L = [str(client_id), str(id), expires, hashlib.md5('%s-%s-%s-%s-%s' % (client_id, id,\
        password, expires, settings.SECRET_KEY)).hexdigest()]
    return base64.encodestring('-'.join(L)), expires


# 解析access_token
def parse_access_token(cid, token):
    try:
        L = base64.decodestring(token).split('-')
        if len(L) != 4:
            return _oauth_error('0006')
        client_id, id, expires, md5 = L
        if client_id != cid:
            return _oauth_error('0006')
        if int(expires) < time.time():
            return _oauth_error('0004')
        try:
            user = ForumUser.get(pk=id)
        except ForumUser.DoesNotExist:
            user = None
        if not user:
            return _oauth_error('0006')
        if md5 != hashlib.md5('%s-%s-%s-%s-%s' % (client_id, id, user.password, expires, settings.SECRET_KEY)).hexdigest():
            return _oauth_error('0006')
        return user
    except:
        return _oauth_error('0006')


# 装饰器,用于认证access_token,类似于Django自带的login_required使用
def login_required(func):
    def _wrapped_view(request, *args, **kwargs):
        client_id = request.REQUEST.get('client_id', None)
        access_token = request.REQUEST.get('access_token', None)
        if client_id and access_token:
            r = parse_access_token(client_id, access_token)
            if isinstance(r, HttpResponse):
                return r
            request.user = user
            return func(request, *args, **kwargs)
        return _oauth_error('0006')
    return _wrapped_view


class OauthView(View):
    def get(self, request):
        '''
        验证QueryString并返回登录页面
        '''
        form = OauthForm(request.GET)
        if not form.is_valid():
            if form['response_type'].errors:
                return _oauth_error('0003')
            elif form['client_id'].errors:
                return _oauth_error('0001')
            elif form['redirect_uri'].errors:
                return _oauth_error('0002')
        return render_to_response('user/login.html', context_instance=RequestContext(request))

    def post(self, request):
        '''
        登录成功后返回access_token
        '''
        get_form = OauthForm(request.GET)
        if not get_form.is_valid():
            if get_form['response_type'].errors:
                return _oauth_error('0003')
            elif get_form['client_id'].errors:
                return _oauth_error('0001')
            elif get_form['redirect_uri'].errors:
                return _oauth_error('0002')

        post_form = LoginForm(request.POST)
        if not post_form.is_valid():
            return get_login(request, errors=post_form.errors)

        user = post_form.get_user()
        access_token, expires_in = make_access_token(get_form.cleaned_data.get('client_id'), user.id, user.password)
        params = {
            'access_token': access_token,
            'token_type': 'token',
            'expires_in': expires_in,
        }
        if get_form.cleaned_data.get('state', None):
            params['state'] = get_form.cleaned_data.get('state')
        return redirect('%s?%s' % (get_form.cleaned_data.get('redirect_uri'), urllib.urlencode(params)))
