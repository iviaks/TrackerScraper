from urllib.parse import ParseResult, quote, urlunparse

import bs4
import dateparser
import requests
from django.http import JsonResponse
from django.views import View


class RutrackerView(View):
    """

    View for Rutracker.org website.

    Before starting, you should login to website. For login you should send
    POST request to this endpoint with username and password.

    After successful login, you can make GET request to this endpoint with:
        * sections (1, 184, 6498, etc.)
        * (required) includes (Python, Javascript, GTA, etc.)
        * excludes (2005, EPUB, CAMRip, etc.)
        * filters (2017, PDF, etc.)

    PS. All GET params should be separated by ','.

    """

    _BASE = {
        'scheme': 'https',
        'netloc': 'rutracker.org/forum',
        'path': '',
        'params': '',
        'query': '',
        'fragment': '',
    }
    _session = requests.session()

    def _login(self, request):
        assert request.session.get("payload"), "You should authorize"

        response = self._session.post(
            self._get_url(path='login.php', query='redirect=tracker.php'),
            data=request.session['payload']
        )
        soup = bs4.BeautifulSoup(response.text, 'html.parser')

        if len(soup.select('input[name="login_username"]')) == 2:
            del request.session['payload']
            raise AssertionError("Incorrect credenitials")

        return soup

    def _get_url(self, *args, **kwargs):
        return urlunparse(ParseResult(**dict(self._BASE, **kwargs)))

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

        if not includes:
            return JsonResponse({
                'error': 'Empty search query'
            })

        result = []
        if not sections:
            for include in includes:
                if filters and excludes:
                    query = 'nm={}'.format(quote(
                        " -".join([
                            " & ".join([include] + filters),
                            " -".join(excludes)
                        ])
                    ))
                elif filters:
                    query = 'nm={}'.format(quote(
                        " & ".join([include] + filters)
                    ))
                elif excludes:
                    query = 'nm={}'.format(quote(
                        " -".join([include, " -".join(excludes)])
                    ))
                else:
                    query = 'nm={}'.format(include)

                url = self._get_url(path='tracker.php', query=query)

                response = self._session.get(url)

                soup = bs4.BeautifulSoup(response.text, 'html.parser')
                elements = soup.select(
                    '#tor-tbl > tbody > tr > td.row4.med.tLeft.t-title'
                    ' > div.wbr.t-title > a'
                )
                result += [
                    (
                        self._get_url(path=a.get('href')),
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
                    query = ['f={}'.format(section)]
                    if filters and excludes:
                        query.append('nm={}'.format(quote(
                            " -".join([
                                " & ".join([include] + filters),
                                " -".join(excludes)
                            ])
                        )))
                    elif filters:
                        query.append('nm={}'.format(quote(
                            " & ".join([include] + filters)
                        )))
                    elif excludes:
                        query.append('nm={}'.format(quote(
                            " -".join([include, " -".join(excludes)])
                        )))
                    else:
                        query.append('nm={}'.format(include))

                    url = self._get_url(
                        path='tracker.php',
                        query="&".join(query)
                    )
                    response = self._session.get(url)

                    soup = bs4.BeautifulSoup(response.text, 'html.parser')
                    elements = soup.select(
                        '#tor-tbl > tbody > tr > td.row4.med.tLeft.t-title'
                        ' > div.wbr.t-title > a'
                    )
                    result += [
                        (
                            self._get_url(path=a.get('href')),
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
