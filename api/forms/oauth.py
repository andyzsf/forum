# coding: utf-8

from django import forms


class OauthForm(forms.Form):
    response_type = forms.CharField()
    client_id = forms.CharField()
    redirect_uri = forms.URLField()
    state = forms.CharField(required=False)

    def clean_response_type(self):
        response_type = self.cleaned_data.get('response_type')
        if response_type != 'token':
            raise forms.ValidationError('')
        return response_type
