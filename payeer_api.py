import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class PayeerAPI:
    def __init__(self, account, api_id, api_pass, language='ru'):
        self.url = 'https://payeer.com/ajax/api/api.php'
        self.agent = 'Mozilla/5.0 (Windows NT 6.1; rv:12.0) Gecko/20100101 Firefox/12.0'
        self.auth = {
            'account': account,
            'apiId': api_id,
            'apiPass': api_pass
        }
        self.language = language
        self.errors = None
        self.output = None

        auth_response = self._get_response(self.auth)
        if auth_response.get('auth_error') != '0':
            raise ValueError("❌ Authentication failed with Payeer API.")

    def _get_response(self, data):
        headers = {
            'User-Agent': self.agent,
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data.update(self.auth)
        data['language'] = self.language

        response = requests.post(self.url, headers=headers, data=data, verify=False)

        json_data = response.json()
        if 'errors' in json_data:
            self.errors = json_data['errors']
        return json_data

    def get_balance(self):
        return self._get_response({'action': 'balance'})

    def get_pay_systems(self):
        return self._get_response({'action': 'getPaySystems'})

    def init_output(self, params):
        params['action'] = 'initOutput'
        response = self._get_response(params)
        if 'errors' not in response or not response['errors']:
            self.output = params
            return True
        return False

    def output(self):
        if not self.output:
            raise ValueError("Output not initialized.")
        self.output['action'] = 'output'
        return self._get_response(self.output).get('historyId', False)

    def get_history_info(self, history_id):
        return self._get_response({'action': 'historyInfo', 'historyId': history_id})

    def transfer(self, params):
        params['action'] = 'transfer'
        return self._get_response(params)

    def get_errors(self):
        return self.errors

    def set_lang(self, language):
        self.language = language

    def get_shop_order_info(self, params):
        params['action'] = 'shopOrderInfo'
        return self._get_response(params)

    def check_user(self, params):
        params['action'] = 'checkUser'
        response = self._get_response(params)
        return 'errors' not in response or not response['errors']

    def get_exchange_rate(self, params):
        params['action'] = 'getExchangeRate'
        return self._get_response(params)

    def merchant(self, params):
        params['action'] = 'merchant'
        params['shop'] = json.dumps(params['shop'])
        params['form'] = json.dumps(params['form'])
        params['ps'] = json.dumps(params['ps'])

        if 'ip' not in params:
            params['ip'] = requests.get('https://api.ipify.org').text

        response = self._get_response(params)
        return response if 'errors' not in response or not response['errors'] else False
