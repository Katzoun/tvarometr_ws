import requests
from requests.auth import HTTPBasicAuth
from .exceptions import RWSException

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)

class RWSClient:

    def __init__(self, host, username, password, port=80):
        proto = "https"
        self.base_url = f"{proto}://{host}:{port}"
        self.session = requests.Session()

        self.session.verify = False
        self.auth_method = HTTPBasicAuth(username, password)
        self.header_typ = {'Accept': 'application/hal+json;v=2.0', 
                       'Content-Type': 'application/x-www-form-urlencoded;v=2.0'}
        self.header_opt = {'Accept': 'application/xhtml+xml;v=2.0'}
        
    def login(self):
        url = f"{self.base_url}"
        resp = self.session.get(url, headers=self.header_typ, auth=self.auth_method)
        #print(f"Login status code: {resp.status_code}")
        if 'ABBCX' not in self.session.cookies.get_dict():
            raise RWSException("Login failed: missing ABBCX cookie")
        #save cookies to a file
        return resp.status_code
    
    def logout(self):
        url = f"{self.base_url}/logout"
        resp = self.session.get(url, headers=self.header_typ)
        print(f"Logout status code: {resp.status_code}")
        
        if resp.status_code != 204:
            raise RWSException(f"Logout failed: {resp.status_code}")
        
        self.session.close()
        return resp.status_code
        
    def is_logged_in(self):
        url = f"{self.base_url}"
        resp = self.session.get(url, headers=self.header_typ)
        #print(f"Login status code: {resp.status_code}")
        if resp.status_code == 200:
            return True
        return False

    def get_request(self, path):
        url = f"{self.base_url}{path}"
        resp = self.session.get(url, headers=self.header_typ)
        #print(f"GET status code: {resp.status_code}")
        #print(f"Cookies: {self.session.cookies.get_dict()}")

        if resp.status_code != 200:
            raise RWSException(f"GET {path} failed: {resp.status_code}")
        return (resp.json() if resp.content else None, resp.status_code)

    def post_request(self, path, dataIn=None):
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, headers=self.header_typ, data=dataIn)
        # print(resp.text)
        #print(f"POST status code: {resp.status_code}")
        if resp.status_code not in (200, 201, 204):
            raise RWSException(f"POST {path} failed: {resp.status_code}")
        return resp.status_code
    
    def dipc_post_request(self, path, dataIn=None):
        url = f"{self.base_url}{path}"
        resp = self.session.post(url, headers=self.header_typ, data=dataIn)
        #print(resp.text)
        #print(f"POST status code: {resp.status_code}")
        if resp.status_code not in (204,500):
            raise RWSException(f"POST {path} failed: {resp.status_code}")
        return resp.status_code

    def options_request(self, path):
        url = f"{self.base_url}{path}"
        resp = self.session.options(url, headers=self.header_opt)
        #print(f"OPTIONS status code: {resp.status_code}")
        if resp.status_code not in (200, 201, 204):
            raise RWSException(f"OPTIONS {path} failed: {resp.status_code}")
        
        return (resp.json() if resp.content else None, resp.status_code)
    
    