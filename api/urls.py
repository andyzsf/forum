from django.conf.urls import patterns, include, url
from forum.forms.user import LoginForm

from views import oauth, topic

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'xp.views.home', name='home'),
    # url(r'^xp/', include('xp.foo.urls')),

    # Uncomment the admin/doc line below to enable admin documentation:
    # url(r'^admin/doc/', include('django.contrib.admindocs.urls')),

    # Uncomment the next line to enable the admin:
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^authorize$', oauth.OauthView.as_view()),
    url(r'^topics$', topic.TopicsView.as_view()),
    url(r'^topics/(\d+)$', topic.TopicView.as_view()),
    url(r'^topics/(\d+)/replies$', topic.ReplysView.as_view()),
)
