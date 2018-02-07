from urllib.parse import quote

import bs4
import dateparser
import requests
from django.http import JsonResponse
from django.views import View


class TorrentMixin:
    _session = requests.session()
    _BASE_URL = None


class RutrackerView(TorrentMixin, View):
    _BASE_URL = 'https://rutracker.org/forum/'

    def _login(self, request):
        assert request.session.get("payload"), "You should authorize"
        response = self._session.post(
            self._BASE_URL + 'login.php?redirect=tracker.php',
            data=request.session['payload']
        )
        soup = bs4.BeautifulSoup(response.text, 'html.parser')
        if len(soup.select('input[name="login_username"]')) == 2:
            del request.session['payload']
            raise AssertionError("Incorrect credenitials")
        return soup

    def post(self, request, *args, **kwargs):
        username = request.POST.get('username')
        password = request.POST.get('password')
        payload = {
            'login_username': username,
            'login_password': password,
            'login': 'Вход'
        }

        request.session['payload'] = payload
        try:
            soup = self._login(request)
        except AssertionError as e:
            return JsonResponse({
                'error': e.args[0]
            })

        sections = [
            (int(option.get('value')), option.string.strip().strip('|- '))
            for option in soup.find(id='fs-main').findAll('option')
        ]
        return JsonResponse(sections, safe=False)

    def get(self, request, *args, **kwargs):
        sections = [
            item.strip()
            for item in request.GET.get('sections', "").split(',') if item
        ]
        includes = [
            item.strip()
            for item in request.GET.get('includes', "").split(',') if item
        ]
        filters = [
            item.strip()
            for item in request.GET.get('filters', "").split(',') if item
        ]
        excludes = [
            item.strip()
            for item in request.GET.get('excludes', "").split(',') if item
        ]

        try:
            self._login(request)
        except AssertionError as e:
            return JsonResponse({
                'error': e.args[0]
            })

        result = []
        if not sections:
            for include in includes:
                url = self._BASE_URL + 'tracker.php'
                if filters and excludes:
                    url += '?nm={}'.format(quote(
                        " -".join([
                            " & ".join([include] + filters),
                            " -".join(excludes)
                        ])
                    ))
                elif filters:
                    url += '?nm={}'.format(quote(
                        " & ".join([include] + filters)
                    ))
                elif excludes:
                    url += '?nm={}'.format(quote(
                        " -".join([include, " -".join(excludes)])
                    ))
                else:
                    url += '?nm={}'.format(include)

                response = self._session.get(url)

                soup = bs4.BeautifulSoup(response.text, 'html.parser')
                elements = soup.select(
                    '#tor-tbl > tbody > tr > td.row4.med.tLeft.t-title'
                    ' > div.wbr.t-title > a'
                )
                print(url)
                result += [
                    (
                        self._BASE_URL + a.get('href'),
                        a.string.strip(),
                        dateparser.parse(
                            a.find_parent('tr').find('p').string
                        )
                    )
                    for a in elements
                ]
        else:
            for section in sections:
                for include in includes:
                    url = self._BASE_URL + 'tracker.php?f={}'.format(section)
                    if filters and excludes:
                        url += '&nm={}'.format(quote(
                            " -".join([
                                " & ".join([include] + filters),
                                " -".join(excludes)
                            ])
                        ))
                    elif filters:
                        url += '&nm={}'.format(quote(
                            " & ".join([include] + filters)
                        ))
                    elif excludes:
                        url += '&nm={}'.format(quote(
                            " -".join([include, " -".join(excludes)])
                        ))
                    else:
                        url += '&nm={}'.format(include)

                    response = self._session.get(url)

                    soup = bs4.BeautifulSoup(response.text, 'html.parser')
                    elements = soup.select(
                        '#tor-tbl > tbody > tr > td.row4.med.tLeft.t-title'
                        ' > div.wbr.t-title > a'
                    )
                    result += [
                        (
                            self._BASE_URL + a.get('href'),
                            a.string.strip(),
                            dateparser.parse(
                                a.find_parent('tr').find('p').string
                            )
                        )
                        for a in elements
                    ]

        return JsonResponse(
            sorted(result, key=lambda x: x[2], reverse=True),
            safe=False
        )
