from core4.api.v1.request.main import CoreRequestHandler
from core4.api.v1.application import CoreApiContainer


class TestApi(CoreRequestHandler):

    """
    This is a simple TestApi. The current paragraph is part of the general
    introduction to the request handler class. See [1] about the
    :class:`.CoreRequestHandler`,
    `this is the named link <https://core4os.readthedocs.io/en/latest/core4/api/v1/request/main.html>`_

    General formatting includes **bold** font and *italic* font. For structuring
    the general docstring markup provides headers. Since the *introduction* and
    the different HTTP *methods* are formatted as headline level 4, no further
    headlines are supported. The developer is encouraged to structure the
    documentation without using headlines.

    Markup supports lists like

    * one
    * two
    * three

    Markups supports enumerations like

    #. one
    #. two
    #. three

    Simple and complex tables are supported, too:

    =====  =====  ======
       Inputs     Output
    ------------  ------
      A      B    A or B
    =====  =====  ======
    False  False  False
    True   False  True
    False  True   True
    True   True   True
    =====  =====  ======

    The following table is considered complex:

    +------------+------------+-----------+
    | Header 1   | Header 2   | Header 3  |
    +============+============+===========+
    | body row 1 | column 2   | column 3  |
    +------------+------------+-----------+
    | body row 2 | Cells may span columns.|
    +------------+------------+-----------+
    | body row 3 | Cells may  | - Cells   |
    +------------+ span rows. | - contain |
    | body row 4 |            | - blocks. |
    +------------+------------+-----------+

    Here is something I want to talk about::
    
        def my_fn(foo, bar=True):
            return None


    Footnotes:

    [1] https://core4os.readthedocs.io/en/latest/core4/api/v1/request/main.html

    """
    author = "mra"
    title = "API Test Page Example"

    def get(self):
        """
        This is the general introduction of the help for method ``GET``. Please
        note that the same method support multiple variants. The variants are
        seperated with the ``Method:`` keyword.

        Methods:
            GET /

        Parameters:
            username (str): requesting login
            password (str): requesting login

        Returns:
            data element with

            - **token** (*str*): the created authorization token

        Raises:
            401: Unauthorized
            402: Do not know
            403: Do not want to know

        Examples:
            >>> from requests import get, post
            >>> url = "http://localhost:5001/core4/api/login"
            >>> rv = get(url + "?username=admin&password=hans")
            >>> rv.json()
            {
                '_id': '5bd94d9bde8b6939aa31ad88',
                'code': 200,
                'data': {
                    'token': 'eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9...'
                },
                'message': 'OK',
                'timestamp': '2018-10-31T06:37:15.734609'
            }
            >>> rv.headers
            {
                'Access-Control-Allow-Headers': 'access-control-allow-origin,authorization,content-type',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Origin': '*',
                'Content-Length': '339',
                'Content-Type': 'application/json; charset=UTF-8',
                'Date': 'Wed, 31 Oct 2018 06:37:15 GMT',
                'Etag': '"d62ecba1141f2653ebd4d9a54f677701e3f6337f"',
                'Server': 'TornadoServer/5.1.1',
                'Set-Cookie': 'token="2|1:0|10:1540967835|5:token|280:ZXlK..."; '
                'expires=Fri, 30 Nov 2018 06:37:15 GMT; Path=/',
                'Token': 'eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjo...'
            }
            >>> signin = post(url, json={"username": "admin", "password": "hans"})
            >>> post(url, cookies=signin.cookies)
            <Response [200]>
            >>> h = {"Authorization": "Bearer " + signin.json()["data"]["token"]}
            >>> post(url, headers=h)
            <Response [200]>
            >>> get("http://localhost:5001/core4/api/profile", headers=h)
            <Response [200]>

        Methods:
            GET /<id>

        Parameters:
            id (ObjectId): The unique identifier of the user

        Returns:
            data element with

            - **token1** (*str*): first token
            - **token2** (*str*): second token

        Raises:
            401: Unauthorized
            402: Do not know
            403: Do not want to know

        Examples:
            >>> from requests import get, post
            >>> url = "http://localhost:5001/core4/api/login"
            >>> rv = get(url + "?username=admin&password=hans")
            >>> rv.json()
            {
                '_id': '5bd94d9bde8b6939aa31ad88',
                'code': 200,
                'data': {
                    'token': 'eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9...'
                },
                'message': 'OK',
                'timestamp': '2018-10-31T06:37:15.734609'
            }
            >>> rv.headers
            {
                'Access-Control-Allow-Headers': 'access-control-allow-origin,authorization,content-type',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Origin': '*',
                'Content-Length': '339',
                'Content-Type': 'application/json; charset=UTF-8',
                'Date': 'Wed, 31 Oct 2018 06:37:15 GMT',
                'Etag': '"d62ecba1141f2653ebd4d9a54f677701e3f6337f"',
                'Server': 'TornadoServer/5.1.1',
                'Set-Cookie': 'token="2|1:0|10:1540967835|5:token|280:ZXlK..."; '
                'expires=Fri, 30 Nov 2018 06:37:15 GMT; Path=/',
                'Token': 'eyJhbGciOiJIUzUxMiIsInR5cCI6IkpXVCJ9.eyJuYW1lIjo...'
            }
            >>> signin = post(url, json={"username": "admin", "password": "hans"})
            >>> post(url, cookies=signin.cookies)
            <Response [200]>
            >>> h = {"Authorization": "Bearer " + signin.json()["data"]["token"]}
            >>> post(url, headers=h)
            <Response [200]>
            >>> get("http://localhost:5001/core4/api/profile", headers=h)
            <Response [200]>
        """
        self.reply("OK")


class TestServer(CoreApiContainer):

    rules = [
        ("/api", TestApi)
    ]


if __name__ == '__main__':
    from core4.api.v1.tool.functool import serve
    serve(TestServer, routing="0.0.0.0:5001")
